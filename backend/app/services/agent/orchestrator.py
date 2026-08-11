"""Multi-Agent Orchestrator (AutoCVE-style).

Splits a large project into module chunks and runs one audit sub-agent per chunk
in parallel (asyncio.gather). Each sub-agent has its own state/messages/tool
registry, sharing the LLM adapter. Findings from all sub-agents are merged and
deduplicated before persisting.

This gives real parallelism for big projects instead of one serial ReAct loop.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings
from app.services.agent.core.state import AgentState, FindingRecord
from app.services.agent.core.memory import MemoryManager
from app.services.agent.core.registry import ToolRegistry
from app.services.agent.core.loop import ReActLoop
from app.services.agent.tools.agent_tools import CodeAuditTools, SKIP_DIRS, SKIP_EXTENSIONS
from app.services.agent.skills.manager import SkillManager
from app.services.agent.prompts.system_prompt import build_system_prompt
from app.services.agent.tools.mcp_tools import get_mcp_bridge, load_merged_mcp_configs
from app.core.config import settings

MIN_FILES_PER_AGENT = 15      # only split when a chunk has at least this many files
MAX_AGENTS = 4                # cap parallel sub-agents


def _is_skippable(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    if any(d in SKIP_DIRS for d in parts):
        return True
    lower = rel.lower()
    return any(lower.endswith(e) for e in SKIP_EXTENSIONS)


def chunk_project_files(all_files: List[str], max_agents: int = MAX_AGENTS) -> List[List[str]]:
    """Group project files into chunks: top-level dirs first, then flat split."""
    if not all_files:
        return []
    # Prefer top-level directory boundaries
    dirs: dict = {}
    flat = []
    for f in all_files:
        parts = f.replace("\\", "/").split("/")
        if len(parts) >= 2:
            dirs.setdefault(parts[0], []).append(f)
        else:
            flat.append(f)

    chunks: List[List[str]] = []
    for d in sorted(dirs.keys()):
        chunks.append(dirs[d])
    if flat:
        chunks.append(flat)

    # Merge small chunks until each has >= MIN_FILES_PER_AGENT (or agents cap)
    merged: List[List[str]] = []
    current: List[str] = []
    for c in chunks:
        current.extend(c)
        if len(current) >= MIN_FILES_PER_AGENT:
            merged.append(current)
            current = []
    if current:
        merged.append(current)

    # Cap number of agents: merge extras into the first chunk
    if len(merged) > max_agents:
        first = merged[0]
        for extra in merged[max_agents:]:
            first.extend(extra)
        merged = merged[:max_agents]

    return merged


@dataclass
class SubAgentResult:
    chunk_id: int
    files: List[str]
    state: AgentState
    findings: List[FindingRecord] = field(default_factory=list)
    error: str = ""
    # metrics aggregated for the main audit record
    turns: int = 0
    tool_calls: int = 0
    tokens: int = 0


class Orchestrator:
    """Runs parallel sub-agents per module chunk, then merges findings."""

    def __init__(
        self,
        project_path: str,
        project_name: str,
        tech_stack: list,
        audit_id: str,
        mode: str,
        llm_adapter,
        scan_candidates: list,
        skill_briefing: str,
        max_turns: int = None,
    ):
        self.project_path = project_path
        self.project_name = project_name
        self.tech_stack = tech_stack
        self.audit_id = audit_id
        self.mode = mode
        self.llm = llm_adapter
        self.scan_candidates = scan_candidates
        self.skill_briefing = skill_briefing
        self.max_turns = max_turns or 50

    def _build_registry(self, tools: CodeAuditTools) -> ToolRegistry:
        reg = ToolRegistry()
        reg.register(
            name="read_file",
            description="Read a file from the project (size-aware; large files return a head excerpt).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File relative path"},
                    "head_only": {"type": "boolean", "default": False},
                },
                "required": ["path"],
            },
            handler=tools.read_file,
        )
        reg.register(
            name="read_file_range",
            description="Read a specific line range of a file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File relative path"},
                    "start_line": {"type": "integer", "default": 1},
                    "end_line": {"type": "integer", "default": 200},
                },
                "required": ["path"],
            },
            handler=tools.read_file_range,
        )
        reg.register(
            name="list_files",
            description="List files in the project matching a glob pattern.",
            parameters={
                "type": "object",
                "properties": {"pattern": {"type": "string", "default": "**/*"}},
            },
            handler=tools.list_files,
        )
        reg.register(
            name="grep",
            description="Search for a regex pattern in project files.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "context": {"type": "integer", "default": 3},
                },
                "required": ["pattern"],
            },
            handler=tools.grep,
        )
        reg.register(
            name="get_project_structure",
            description="Get the project directory tree structure.",
            parameters={"type": "object", "properties": {}},
            handler=tools.get_project_structure,
        )
        reg.register(
            name="run_semgrep_scan",
            description="Run Semgrep SAST scan over the project.",
            parameters={"type": "object", "properties": {}},
            handler=tools.run_semgrep_scan,
        )
        reg.register(
            name="run_sca_scan",
            description="Run dependency (SCA) scan over the project.",
            parameters={"type": "object", "properties": {}},
            handler=tools.run_sca_scan,
        )
        reg.register(
            name="run_custom_rules",
            description="Run custom YAML detection rules over the project.",
            parameters={"type": "object", "properties": {}},
            handler=tools.run_custom_rules,
        )
        reg.register(
            name="load_skill",
            description="Load the full content of a security skill pack on demand.",
            parameters={
                "type": "object",
                "properties": {"skill_name": {"type": "string"}},
                "required": ["skill_name"],
            },
            handler=tools.load_skill,
        )
        reg.register(
            name="verify_poc",
            description="Statically validate (or sandbox-execute if enabled) a PoC script.",
            parameters={
                "type": "object",
                "properties": {"poc": {"type": "string"}},
                "required": ["poc"],
            },
            handler=tools.verify_poc,
        )
        reg.register(
            name="mark_file_covered",
            description="Explicitly mark a file as audited.",
            parameters={
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
                "required": ["file_path"],
            },
            handler=tools.mark_file_covered,
        )
        reg.register(
            name="finalize_finding",
            description="Submit a confirmed vulnerability finding with complete taint chain.",
            parameters={
                "type": "object",
                "properties": {
                    "vulnerability_type": {"type": "string"},
                    "severity": {"type": "string"},
                    "title": {"type": "string"},
                    "file_path": {"type": "string"},
                    "line_start": {"type": "integer", "default": 0},
                    "line_end": {"type": "integer", "default": 0},
                    "code_snippet": {"type": "string", "default": ""},
                    "description": {"type": "string", "default": ""},
                    "source": {"type": "string"},
                    "sink": {"type": "string"},
                    "exploit_chain": {"type": "string"},
                    "poc": {"type": "string", "default": ""},
                    "suggestion": {"type": "string", "default": ""},
                    "confidence": {"type": "string", "default": "MEDIUM"},
                    "cwe": {"type": "string", "default": ""},
                },
                "required": ["vulnerability_type", "severity", "title", "file_path",
                             "source", "sink", "exploit_chain"],
            },
            handler=tools.finalize_finding,
        )
        reg.register(
            name="finish_audit",
            description="Call this when you have thoroughly audited the assigned files and are done.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: '{"status": "audit_finished"}',
        )
        # ── Register MCP tools for sub-agent ────────────────────
        mcp_configs = load_merged_mcp_configs()
        mcp_bridge = get_mcp_bridge(mcp_configs)
        if mcp_bridge and mcp_bridge._tools:
            for mcp_td in mcp_bridge.get_tool_definitions():
                reg_name = mcp_td["function"]["name"]
                reg_desc = mcp_td["function"]["description"]
                reg_params = mcp_td["function"]["parameters"]
                def _mcp_handler(name=reg_name):
                    async def handler(**kwargs):
                        return await mcp_bridge.call_tool(name, kwargs)
                    return handler
                reg.register(
                    name=reg_name,
                    description=reg_desc,
                    parameters=reg_params,
                    handler=_mcp_handler(),
                )

        return reg

    async def _run_sub_agent(self, chunk_id: int, files: List[str]) -> SubAgentResult:
        state = AgentState(
            audit_id=f"{self.audit_id}_sub{chunk_id}",
            project_path=self.project_path,
            project_name=f"{self.project_name} [chunk {chunk_id}]",
            tech_stack=self.tech_stack,
            mode=self.mode,
            all_files=files,
            scan_candidates=self.scan_candidates,
            skill_briefing=self.skill_briefing,
        )
        state.scanned = True
        state.mark_stage("recon")
        state.mark_stage("scan")

        covered: set = set()
        tools = CodeAuditTools(project_root=self.project_path, on_cover=lambda p: covered.add(p))
        reg = self._build_registry(tools)
        memory = MemoryManager()
        skill_mgr = SkillManager()

        # Inject the chunk's file list as the primary user instruction
        state.add_user_message(
            f"Your assigned scope for this audit chunk: audit the following files "
            f"({len(files)} files). Focus on these; you may read shared files for context.\n"
            f"Files: {', '.join(files[:80])}"
            + (f"\n... and {len(files)-80} more (use list_files to see all)" if len(files) > 80 else "")
        )

        loop = ReActLoop(state, self.llm, reg, memory, skill_mgr, auto_persist=False,
                          max_turns=self.max_turns)
        try:
            await loop.run()
        except Exception as e:  # noqa: BLE001
            return SubAgentResult(chunk_id=chunk_id, files=files, state=state,
                                  findings=state.findings, error=str(e),
                                  turns=state.turn, tool_calls=state.tool_call_count,
                                  tokens=state.total_tokens)
        return SubAgentResult(chunk_id=chunk_id, files=files, state=state, findings=state.findings,
                              turns=state.turn, tool_calls=state.tool_call_count,
                              tokens=state.total_tokens)

    async def run(self, all_files: List[str]) -> dict:
        """Run all sub-agents in parallel, merge findings, return result dict."""
        chunks = chunk_project_files(all_files)
        if len(chunks) <= 1:
            return {"parallel": False, "chunks": 1, "results": [], "merged": []}

        results = await asyncio.gather(*[
            self._run_sub_agent(i, files) for i, files in enumerate(chunks)
        ])

        # Merge + dedupe findings across sub-agents
        merged: List[FindingRecord] = []
        seen = set()
        total_turns = total_tool_calls = total_tokens = 0
        for r in results:
            total_turns += r.turns
            total_tool_calls += r.tool_calls
            total_tokens += r.tokens
            for f in r.findings:
                key = (f.vulnerability_type, f.file_path, f.title, f.sink)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(f)

        return {
            "parallel": True,
            "chunks": len(chunks),
            "results": results,
            "merged": merged,
            "turns_total": total_turns,
            "tool_calls_total": total_tool_calls,
            "tokens_total": total_tokens,
        }
