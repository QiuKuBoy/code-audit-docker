"""MCP (Model Context Protocol) Tool Integration.

Connects to external MCP servers (e.g., src-wiki knowledge base) and exposes
their tools to the code audit agent. MCP tools are discovered at startup and
registered alongside native tools in the ToolRegistry.

Architecture:
  Agent Loop → ToolRegistry → MCPToolBridge → MCP Server (via SSE/stdio)
                                          ↓
                                   Native Tools (read_file, grep, etc.)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

import os as _os

# Runtime MCP server config file (merged with settings.MCP_SERVERS).
# Prefer the Docker data volume so runtime-added servers survive rebuilds.
def _default_config_file() -> str:
    if _os.path.isdir("/data") and _os.access("/data", _os.W_OK):
        return "/data/mcp_servers.json"
    return _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))),
        "mcp_servers.json",
    )

_MCP_CONFIG_FILE = _os.environ.get("MCP_CONFIG_FILE") or _default_config_file()


@dataclass
class MCPServerConfig:
    name: str
    url: str
    headers: dict = field(default_factory=dict)
    timeout: int = 30
    enabled: bool = True
    description: str = ""
    transport: str = "auto"   # auto | sse | streamable_http


def _read_runtime_configs() -> dict:
    """Read runtime MCP configs from JSON file (empty dict if absent)."""
    try:
        if _os.path.isfile(_MCP_CONFIG_FILE):
            with open(_MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception as e:
        logger.warning(f"MCP config file read failed: {e}")
    return {}


def _write_runtime_configs(configs: dict):
    """Persist runtime MCP configs to JSON file."""
    with open(_MCP_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)


def load_merged_mcp_configs() -> list[MCPServerConfig]:
    """Load MCP configs from settings.MCP_SERVERS merged with runtime JSON file.

    Runtime file entries override/add servers without touching config.py.
    A runtime entry with value None or {"deleted": true} acts as a tombstone
    that hides the corresponding built-in server from config.py.
    """
    from app.core.config import settings
    merged = dict(settings.MCP_SERVERS or {})
    runtime = _read_runtime_configs()
    # Apply runtime overrides; tombstones remove built-in entries
    for name, cfg in runtime.items():
        if cfg is None or (isinstance(cfg, dict) and cfg.get("deleted")):
            merged.pop(name, None)
        else:
            merged[name] = cfg
    return load_mcp_configs(merged)


def save_runtime_mcp_server(name: str, cfg: dict) -> list[MCPServerConfig]:
    """Add/update a runtime MCP server config. Returns updated config list."""
    configs = _read_runtime_configs()
    configs[name] = cfg
    _write_runtime_configs(configs)
    return load_merged_mcp_configs()


def delete_runtime_mcp_server(name: str) -> bool:
    """Delete a runtime MCP server config (only if stored in runtime file)."""
    configs = _read_runtime_configs()
    if name in configs:
        del configs[name]
        _write_runtime_configs(configs)
        return True
    return False


def _sanitize_headers(headers: dict) -> dict:
    """Ensure all header values are strings (httpx requirement)."""
    clean = {}
    for k, v in (headers or {}).items():
        if isinstance(v, dict):
            # Nested dict pasted by mistake — flatten only string leaves
            for kk, vv in v.items():
                if isinstance(vv, (str, int, float)):
                    clean[f"{k}-{kk}"] = str(vv)
            continue
        if v is not None:
            clean[k] = str(v)
    return clean


def load_mcp_configs(raw_configs: dict | None) -> list[MCPServerConfig]:
    if not raw_configs:
        return []
    configs = []
    for name, cfg in raw_configs.items():
        if not isinstance(cfg, dict):
            continue
        configs.append(MCPServerConfig(
            name=name,
            url=cfg.get("url", ""),
            headers=cfg.get("headers", {}),
            timeout=cfg.get("timeout", 30),
            enabled=cfg.get("enabled", True),
            description=cfg.get("description", f"MCP server: {name}"),
            transport=cfg.get("transport", "auto"),
        ))
    return configs


@dataclass
class MCPToolDef:
    name: str
    description: str
    parameters: dict
    server_name: str
    server_url: str

    def to_openai_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": f"mcp_{self.server_name}__{self.name}",
                "description": f"[MCP/{self.server_name}] {self.description}",
                "parameters": self.parameters if self.parameters else {
                    "type": "object", "properties": {}
                },
            }
        }


class MCPToolBridge:
    def __init__(self, configs: list[MCPServerConfig] | None = None):
        self._configs = configs or []
        self._tools: dict[str, MCPToolDef] = {}
        self._initialized = False
        self._init_error: str = ""

    @property
    def is_configured(self) -> bool:
        return len(self._configs) > 0

    @property
    def server_names(self) -> list[str]:
        return [c.name for c in self._configs if c.enabled]

    async def initialize(self) -> dict:
        if self._initialized:
            return {"status": "already_initialized", "servers": self.server_names}
        results = {}
        for cfg in self._configs:
            if not cfg.enabled or not cfg.url:
                results[cfg.name] = {"status": "skipped", "reason": "disabled or no url"}
                continue
            try:
                tools_count = await self._connect_server(cfg)
                results[cfg.name] = {"status": "connected", "tools": tools_count}
                logger.info(f"MCP [{cfg.name}]: connected, {tools_count} tools discovered")
            except Exception as e:
                msg = str(e)[:200]
                results[cfg.name] = {"status": "failed", "error": msg}
                logger.warning(f"MCP [{cfg.name}]: connection failed - {msg}")
        self._initialized = True
        return {"status": "initialized", "servers": results}

    async def _connect_server(self, cfg: MCPServerConfig) -> int:
        transport = self._resolve_transport(cfg)
        if transport == "streamable_http":
            return await self._connect_streamable(cfg)
        return await self._connect_sse(cfg)

    @staticmethod
    def _resolve_transport(cfg: MCPServerConfig) -> str:
        """auto: prefer streamable_http (modern standard), fall back to SSE."""
        if cfg.transport in ("sse", "streamable_http"):
            return cfg.transport
        # auto: try streamable first; if the server speaks SSE only, the
        # caller catches and retries with SSE.
        return "streamable_http"

    async def _connect_sse(self, cfg: MCPServerConfig) -> int:
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError:
            raise ImportError("MCP SDK not installed. Run: pip install mcp")

        headers = _sanitize_headers(cfg.headers)
        headers.setdefault("Accept", "application/json, text/event-stream")

        async with sse_client(url=cfg.url, headers=headers, timeout=cfg.timeout) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await self._collect_tools(session, cfg)

    async def _connect_streamable(self, cfg: MCPServerConfig) -> int:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            # older SDK: try streamable_http module path
            try:
                from mcp.client.http import streamable_http_client
            except ImportError:
                raise ImportError("MCP SDK too old for streamable_http. Run: pip install -U mcp")

        headers = _sanitize_headers(cfg.headers)
        headers.setdefault("Accept", "application/json, text/event-stream")

        import httpx
        async with httpx.AsyncClient(headers=headers, timeout=cfg.timeout) as http_client:
            async with streamable_http_client(url=cfg.url, http_client=http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await self._collect_tools(session, cfg)

    async def _collect_tools(self, session, cfg: MCPServerConfig) -> int:
        tools_result = await session.list_tools()
        tools_list = tools_result.tools if hasattr(tools_result, 'tools') else tools_result
        discovered = 0
        for tool in tools_list:
            tool_def = MCPToolDef(
                name=tool.name,
                description=getattr(tool, 'description', ''),
                parameters=getattr(tool, 'inputSchema', {}),
                server_name=cfg.name,
                server_url=cfg.url,
            )
            prefixed = tool_def.to_openai_format()["function"]["name"]
            self._tools[prefixed] = tool_def
            discovered += 1
        return discovered

    def get_tool_definitions(self) -> list[dict]:
        return [t.to_openai_format() for t in self._tools.values()]

    def describe_tools(self) -> str:
        if not self._tools:
            return ""
        lines = ["## External Knowledge Tools (MCP)"]
        by_server: dict = {}
        for tool in self._tools.values():
            by_server.setdefault(tool.server_name, []).append(tool)
        for server, tools in by_server.items():
            cfg = next((c for c in self._configs if c.name == server), None)
            desc = cfg.description if cfg else server
            lines.append(f"\n### {server} - {desc}")
            for t in tools:
                lines.append(f"- **mcp_{server}__{t.name}**: {t.description}")
        return "\n".join(lines)

    async def call_tool(self, prefixed_name: str, arguments: dict) -> str:
        tool_def = self._tools.get(prefixed_name)
        if not tool_def:
            return json.dumps({"error": f"Unknown MCP tool: {prefixed_name}"})
        cfg = next((c for c in self._configs if c.name == tool_def.server_name), None)
        if not cfg:
            return json.dumps({"error": f"MCP server not found: {tool_def.server_name}"})
        try:
            transport = self._resolve_transport(cfg)
            if transport == "streamable_http":
                return await self._call_streamable(cfg, tool_def, arguments)
            return await self._call_sse(cfg, tool_def, arguments)
        except Exception as e:
            logger.error(f"MCP tool call failed [{prefixed_name}]: {e}")
            return json.dumps({
                "error": f"MCP tool call failed: {str(e)[:500]}",
                "server": tool_def.server_name,
                "tool": tool_def.name,
            })

    async def _call_streamable(self, cfg, tool_def, arguments) -> str:
        from mcp import ClientSession
        try:
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            from mcp.client.http import streamable_http_client
        headers = _sanitize_headers(cfg.headers)
        headers.setdefault("Accept", "application/json, text/event-stream")
        import httpx
        async with httpx.AsyncClient(headers=headers, timeout=cfg.timeout) as http_client:
            async with streamable_http_client(url=cfg.url, http_client=http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_def.name, arguments=arguments)
                    return self._format_tool_result(cfg, tool_def, result)

    async def _call_sse(self, cfg, tool_def, arguments) -> str:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
        headers = _sanitize_headers(cfg.headers)
        headers.setdefault("Accept", "application/json, text/event-stream")
        async with sse_client(url=cfg.url, headers=headers, timeout=cfg.timeout) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_def.name, arguments=arguments)
                return self._format_tool_result(cfg, tool_def, result)

    @staticmethod
    def _format_tool_result(cfg, tool_def, result) -> str:
        if hasattr(result, 'content'):
            content_parts = []
            for c in result.content:
                if hasattr(c, 'text'):
                    content_parts.append(c.text)
                elif hasattr(c, 'data'):
                    content_parts.append(str(c.data))
            return json.dumps({
                "server": tool_def.server_name,
                "tool": tool_def.name,
                "result": "\n".join(content_parts),
            })
        return json.dumps({
            "server": tool_def.server_name,
            "tool": tool_def.name,
            "result": str(result),
        })

    async def close(self):
        self._tools.clear()
        self._initialized = False


_mcp_bridge: MCPToolBridge | None = None


def get_mcp_bridge(configs: list[MCPServerConfig] | None = None) -> MCPToolBridge:
    global _mcp_bridge
    if _mcp_bridge is None:
        _mcp_bridge = MCPToolBridge(configs or [])
    elif configs and configs != _mcp_bridge._configs:
        _mcp_bridge = MCPToolBridge(configs)
    return _mcp_bridge


async def init_mcp_bridge(configs: list[MCPServerConfig]) -> dict:
    bridge = get_mcp_bridge(configs)
    if not bridge.is_configured:
        return {"status": "no_mcp_configured"}
    return await bridge.initialize()


async def close_mcp_bridge():
    global _mcp_bridge
    if _mcp_bridge:
        await _mcp_bridge.close()
        _mcp_bridge = None
