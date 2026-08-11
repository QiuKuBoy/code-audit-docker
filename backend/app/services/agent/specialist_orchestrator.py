"""Specialist Orchestrator — dispatch audits by vulnerability class.

Recon scans danger patterns with grep, then launches parallel specialist
agents (SQLi/XSS/Auth/...) each focused on ONE vulnerability class with
its full skill pack. Metrics and findings are aggregated back.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import List

from app.core.config import settings
from app.services.agent.core.state import AgentState, FindingRecord
from app.services.agent.core.memory import MemoryManager
from app.services.agent.core.registry import ToolRegistry
from app.services.agent.core.loop import ReActLoop
from app.services.agent.tools.agent_tools import CodeAuditTools
from app.services.agent.skills.manager import SkillManager
from app.services.agent.prompts.system_prompt import build_system_prompt
from app.services.agent.core.specialists import (
    SPECIALISTS, SpecialistProfile, get_specialists_for_triggers, build_specialist_prompt,
)
from app.services.agent.tools.mcp_tools import get_mcp_bridge, load_merged_mcp_configs

MAX_SPECIALISTS = 4


@dataclass
class SpecialistResult:
    profile_name: str
    files: List[str]
    findings: List[FindingRecord] = field(default_factory=list)
    turns: int = 0
    tool_calls: int = 0
    tokens: int = 0
    error: str = ""
    triggers: List[str] = field(default_factory=list)


class SharedFindingsBus:
    """Cross-agent coordination bus.

    Specialist agents publish findings; peers get a compact summary injected
    into their prompt so the same vulnerability class is not re-discovered
    in every module and global issues (e.g. CSRF disabled) are flagged once.
    """

    def __init__(self):
        self._entries: list[dict] = []
        self._signatures: set = set()

    def publish(self, finding: FindingRecord) -> bool:
        """Publish a finding. Returns True if new (dedupe by signature)."""
        sig = (finding.vulnerability_type, finding.file_path.split("/")[-1],
               finding.sink[:60])
        if sig in self._signatures:
            return False
        self._signatures.add(sig)
        self._entries.append({
            "type": finding.vulnerability_type,
            "file": finding.file_path,
            "sink": finding.sink[:100],
        })
        return True

    def context_for(self, exclude_bug_class: str = "") -> str:
        """Compact peer-finding summary for prompt injection."""
        if not self._entries:
            return ""
        lines = []
        for e in self._entries[:8]:
            lines.append(f"- {e['type']} in {e['file']} (sink: {e['sink']})")
        return "[Peer agents found]\n" + "\n".join(lines) + "\nCheck YOUR scope for the same class of issue."


class SpecialistOrchestrator:
    """Recon -> danger-pattern scan -> parallel specialist agents -> merge."""

    def __init__(
        self,
        project_path: str,
        project_name: str,
        tech_stack: list,
        audit_id: str,
        mode: str,
        llm_adapter,
        skill_briefing: str,
        max_turns: int = None,
    ):
        self.project_path = project_path
        self.project_name = project_name
        self.tech_stack = tech_stack
        self.audit_id = audit_id
        self.mode = mode
        self.llm = llm_adapter
        self.skill_briefing = skill_briefing
        self.max_turns = max_turns or 50

    async def _recon_danger_patterns(self, all_files: List[str]) -> List[str]:
        """Grep danger patterns across source files (cap 60 files)."""
        triggers = []
        sample = [f for f in all_files
                  if not f.startswith((".", "doc", "docs", "test", "tests", "node_modules"))][:60]
        for rel in sample:
            full = self.project_path.replace("\\", "/") + "/" + rel
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()[:200000]
            except Exception:
                continue
            for profile in SPECIALISTS.values():
                for pat in profile.trigger_patterns:
                    try:
                        if re.search(pat, content):
                            triggers.append(pat)
                            break
                    except re.error:
                        continue
        return list(set(triggers))

    async def _run_specialist(self, profile: SpecialistProfile, files: List[str], triggers: List[str],
                             bus: SharedFindingsBus = None, parent_state: AgentState = None):
        state = AgentState(
            audit_id=f"{self.audit_id}_{profile.bug_class}",
            project_path=self.project_path,
            project_name=f"{self.project_name} [{profile.display_name}]",
            tech_stack=self.tech_stack,
            mode=self.mode,
            all_files=files,
            skill_briefing=self.skill_briefing,
            parent_state=parent_state,
            specialist_name=profile.bug_class,
        )
        state.scanned = True
        state.mark_stage("recon")
        state.mark_stage("finding")

        tools = CodeAuditTools(project_root=self.project_path,
                               on_cover=lambda p: state.mark_file_covered(p))
        reg = ToolRegistry()
        reg.register("read_file", "Read a project file (size-aware).",
                     {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
                     tools.read_file)
        reg.register("read_file_range", "Read a line range of a file.",
                     {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, "required": ["path"]},
                     tools.read_file_range)
        reg.register("list_files", "List project files matching a glob.",
                     {"type": "object", "properties": {"pattern": {"type": "string"}}},
                     tools.list_files)
        reg.register("grep", "Regex search in project files.",
                     {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}, "context": {"type": "integer"}}, "required": ["pattern"]},
                     tools.grep)
        reg.register("get_project_structure", "Project directory tree.", {"type": "object", "properties": {}},
                     tools.get_project_structure)
        reg.register("load_skill", "Load full skill pack content on demand.",
                     {"type": "object", "properties": {"skill_name": {"type": "string"}}, "required": ["skill_name"]},
                     tools.load_skill)
        reg.register("verify_poc", "Statically validate a PoC script.",
                     {"type": "object", "properties": {"poc": {"type": "string"}}, "required": ["poc"]},
                     tools.verify_poc)
        reg.register("mark_file_covered", "Mark a file as audited.",
                     {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]},
                     tools.mark_file_covered)
        # Engine scan tools (use CodeAuditTools methods — already bound to project_root)
        reg.register("run_semgrep_scan", "Run Semgrep SAST scan on the project.",
                     {"type": "object", "properties": {"config": {"type": "string"}}},
                     tools.run_semgrep_scan)
        reg.register("run_sca_scan", "Run SCA (dependency vulnerability scan).",
                     {"type": "object", "properties": {}},
                     tools.run_sca_scan)
        reg.register("run_custom_rules", "Run custom YAML detection rules.",
                     {"type": "object", "properties": {}},
                     tools.run_custom_rules)
        reg.register("finalize_finding", "Submit a confirmed vulnerability finding.",
                     {"type": "object",
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
                                   "source", "sink", "exploit_chain"]},
                     tools.finalize_finding)
        reg.register("finish_audit", "Finish when this specialist's scope is thoroughly audited.",
                     {"type": "object", "properties": {}},
                     lambda **kw: '{"status": "audit_finished"}')

        # Register MCP tools if bridge is live
        try:
            mcp_bridge = get_mcp_bridge(load_merged_mcp_configs())
            if mcp_bridge and mcp_bridge._tools:
                for mcp_td in mcp_bridge.get_tool_definitions():
                    rname = mcp_td["function"]["name"]
                    def _mk(n=rname):
                        async def h(**kw):
                            return await mcp_bridge.call_tool(n, kw)
                        return h
                    reg.register(rname, mcp_td["function"]["description"],
                                 mcp_td["function"]["parameters"], _mk())
        except Exception:
            pass

        base_prompt = build_system_prompt(
            project_name=self.project_name,
            project_path=self.project_path,
            tech_stack=self.tech_stack,
            skill_briefing=self.skill_briefing,
            mode=self.mode,
        )
        system_prompt = build_specialist_prompt(profile, base_prompt, files)
        state.add_system_message(system_prompt)
        peer_ctx = bus.context_for(profile.bug_class) if bus else ""
        state.add_user_message(
            f"You are auditing for '{profile.bug_class}' ONLY. "
            f"Assigned files ({len(files)}): {', '.join(files[:60])}"
            + (f"\n... and {len(files)-60} more" if len(files) > 60 else "")
            + f"\nDanger patterns detected in this project: {', '.join(triggers[:8])}"
            + (f"\n\n{peer_ctx}" if peer_ctx else "")
        )

        memory = MemoryManager()
        skill_mgr = SkillManager()
        loop = ReActLoop(state, self.llm, reg, memory, skill_mgr, auto_persist=False,
                         max_turns=self.max_turns)
        try:
            await loop.run()
        except Exception as e:
            for f in state.findings:
                if bus: bus.publish(f)
            return SpecialistResult(
                profile_name=profile.bug_class, files=files, findings=state.findings,
                turns=state.turn, tool_calls=state.tool_call_count, tokens=state.total_tokens,
                error=str(e), triggers=triggers,
            )
        for f in state.findings:
            if bus: bus.publish(f)
        return SpecialistResult(
            profile_name=profile.bug_class, files=files, findings=state.findings,
            turns=state.turn, tool_calls=state.tool_call_count, tokens=state.total_tokens,
            triggers=triggers,
        )

    async def run(self, all_files: List[str], parent_state: AgentState = None) -> dict:
        """Recon -> two-wave specialist dispatch -> merge findings + metrics.

        Wave 1: core specialists (sqli/auth_bypass/xss) run in parallel.
        Wave 2: remaining specialists start AFTER wave 1, receiving a
                peer-findings summary from the shared bus (coordination).
        """
        triggers = await self._recon_danger_patterns(all_files)
        bus = SharedFindingsBus()
        all_profiles = get_specialists_for_triggers(set(triggers))[:MAX_SPECIALISTS]
        if not all_profiles:
            all_profiles = [SPECIALISTS["sqli"], SPECIALISTS["auth_bypass"], SPECIALISTS["xss"]]

        # Wave 1: always-relevant core specialists (match by bug_class)
        core_classes = {"SQL_Injection", "Authentication_Bypass", "XSS"}
        wave1 = [p for p in all_profiles if p.bug_class in core_classes]
        wave2 = [p for p in all_profiles if p.bug_class not in core_classes]
        if not wave1:
            wave1 = all_profiles[:1]
            wave2 = all_profiles[1:]

        results = []
        wave1_results = await asyncio.gather(*[
            self._run_specialist(p, all_files, triggers, bus, parent_state=parent_state) for p in wave1
        ])
        results.extend(wave1_results)

        if wave2:
            wave2_results = await asyncio.gather(*[
                self._run_specialist(p, all_files, triggers, bus, parent_state=parent_state) for p in wave2
            ])
            results.extend(wave2_results)

        merged: List[FindingRecord] = []
        seen = set()
        for r in results:
            for f in r.findings:
                key = (f.vulnerability_type, f.file_path, f.title, f.sink)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(f)

        return {
            "parallel": True,
            "specialists": [r.profile_name for r in results],
            "triggers": triggers,
            "results": results,
            "merged": merged,
            "turns_total": sum(r.turns for r in results),
            "tool_calls_total": sum(r.tool_calls for r in results),
            "tokens_total": sum(r.tokens for r in results),
        }
