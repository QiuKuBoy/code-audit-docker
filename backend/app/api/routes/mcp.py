"""MCP Servers API routes — list / test / create / delete."""

from fastapi import APIRouter, HTTPException
import time

from app.core.config import settings
from app.services.agent.tools.mcp_tools import (
    load_merged_mcp_configs, get_mcp_bridge, MCPToolBridge,
    save_runtime_mcp_server, delete_runtime_mcp_server,
)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


def _server_info(cfg):
    return {
        "name": cfg.name,
        "url": cfg.url,
        "enabled": cfg.enabled,
        "description": cfg.description,
        "timeout": cfg.timeout,
        "has_auth": bool(cfg.headers),
    }


@router.get("/servers")
async def list_mcp_servers():
    configs = load_merged_mcp_configs()
    return {"servers": [_server_info(c) for c in configs], "total": len(configs)}


@router.post("/servers")
async def create_mcp_server(body: dict):
    """Add an MCP server (persisted to runtime JSON, no restart needed)."""
    name = (body.get("name") or "").strip().lower()
    url = (body.get("url") or "").strip()
    if not name or not re_url(url):
        raise HTTPException(status_code=400, detail="Valid name and url required")
    raw_headers = body.get("headers") or {}
    if not isinstance(raw_headers, dict):
        raise HTTPException(status_code=400, detail="headers must be a JSON object")
    # Reject nested non-string values early
    for k, v in raw_headers.items():
        if not isinstance(v, (str, int, float)):
            raise HTTPException(status_code=400, detail=f"header '{k}' must be a string value")
    cfg = {
        "url": url,
        "headers": {k: str(v) for k, v in raw_headers.items()},
        "timeout": int(body.get("timeout") or 30),
        "enabled": bool(body.get("enabled", True)),
        "description": body.get("description") or f"MCP server: {name}",
    }
    save_runtime_mcp_server(name, cfg)
    return {"status": "created", "name": name}


@router.delete("/servers/{name}")
async def delete_mcp_server(name: str):
    """Delete an MCP server.

    Runtime-added servers are removed from the JSON file.
    Built-in servers (from config.py) are soft-deleted via a tombstone
    entry so they disappear from the list without editing config.py.
    """
    from app.services.agent.tools.mcp_tools import (
        _read_runtime_configs, _write_runtime_configs, load_merged_mcp_configs,
    )
    runtime = _read_runtime_configs()
    builtin_names = {c.name for c in load_merged_mcp_configs()}

    if name in runtime:
        delete_runtime_mcp_server(name)
    else:
        # Soft-delete a built-in server: tombstone entry hides it on load
        runtime[name] = {"deleted": True, "url": ""}
        _write_runtime_configs(runtime)
    return {"status": "deleted", "name": name, "soft": name not in builtin_names}


def re_url(u: str) -> bool:
    return u.startswith("http://") or u.startswith("https://") or u.startswith("ws://") or u.startswith("wss://")


@router.post("/servers/{name}/test")
async def test_mcp_server(name: str):
    configs = load_merged_mcp_configs()
    cfg = next((c for c in configs if c.name == name), None)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"MCP server not found: {name}")
    start = time.time()
    bridge = MCPToolBridge([cfg])
    try:
        result = await bridge.initialize()
        latency_ms = int((time.time() - start) * 1000)
        srv_status = result.get("servers", {}).get(name, {})
        if srv_status.get("status") == "connected":
            return {
                "status": "connected",
                "tools_count": srv_status.get("tools", 0),
                "latency_ms": latency_ms,
                "tools": [t["function"]["name"] for t in bridge.get_tool_definitions()],
            }
        return {"status": "failed", "error": srv_status.get("error", "unknown"), "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "failed", "error": str(e)[:200], "latency_ms": int((time.time() - start) * 1000)}


@router.get("/stats")
async def get_mcp_stats():
    configs = load_merged_mcp_configs()
    total_tools = 0
    for cfg in configs:
        bridge = get_mcp_bridge([cfg])
        if bridge._tools:
            total_tools += len([t for t in bridge._tools.values() if t.server_name == cfg.name])
    return {
        "configured_servers": len(configs),
        "enabled_servers": len([c for c in configs if c.enabled]),
        "registered_tools": total_tools,
        "calls_total": 0,
        "calls_success": 0,
        "calls_failed": 0,
    }
