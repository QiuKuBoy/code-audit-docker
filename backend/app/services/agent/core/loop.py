"""ReAct Loop - Core execution loop for the code audit agent (upgraded).

Changes vs original:
- Mode-aware stage tracking (quick/smart/comprehensive).
- Engine scan results (semgrep/sca/custom rules) are collected up-front and
  injected into the system prompt as Triage candidates.
- Coverage-driven termination: finish_audit is validated against minimum
  coverage; the agent is nudged if it finishes too early.
- PoC verification status is captured with each finding.
"""

import json
import asyncio
from typing import Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import async_session
from app.models.models import AuditLog, Finding, Audit
from .state import AgentState, FindingRecord
from .memory import MemoryManager
from .registry import ToolRegistry
from ..tools.agent_tools import CodeAuditTools
from ..skills.manager import SkillManager
from ..prompts.system_prompt import build_system_prompt


# Nudge message templates
NUDGE_MESSAGES = {
    "empty_response": (
        "Your previous response was empty. Please continue the audit by "
        "calling a tool to inspect the next file or search for a vulnerability pattern."
    ),
    "no_tool_no_final": (
        "You did not call any tool or submit a finding. To complete the audit, "
        "you must either: (1) call a tool to continue auditing code, or "
        "(2) call finalize_finding to submit a discovered vulnerability, or "
        "(3) call finish_audit if you have thoroughly checked all attack surfaces."
    ),
    "payload_invalid": (
        "Your finalize_finding submission was rejected. Please fix the issues "
        "and resubmit with all required fields."
    ),
    "stuck_loop": (
        "You appear to be repeatedly checking the same location. "
        "Please move on to a different file or attack surface."
    ),
    "legacy_syntax": (
        "Please use the native tool calling format (function calls) instead of "
        "writing 'Action:' or 'Tool Call:' in text."
    ),
    "low_coverage": (
        "You requested to finish the audit, but coverage is still low: many project "
        "files have not been read. Please audit more of the remaining attack surface "
        "(check list_files / grep for unread entry points) before calling finish_audit. "
        "If the unread files are genuinely irrelevant (docs, tests, assets), call "
        "mark_file_covered on them or confirm finish_audit anyway with "
        "finish_audit(force=true)."
    ),
    "scan_required": (
        "In the current audit mode you should also run the engine scanners "
        "(run_semgrep_scan / run_sca_scan / run_custom_rules) to cover dependency and "
        "pattern-based issues before finishing. If the scanners are not installed "
        "(skipped=true), manual analysis is acceptable."
    ),
}

MAX_STUCK_COUNT = 3  # Max repeated identical tool calls before nudge

# Stages by mode (used for guidance and stage transitions)
MODE_STAGES = {
    "quick": ["recon", "scan", "triage", "finalize"],
    "smart": ["recon", "finding", "verification", "finalize"],
    "comprehensive": ["recon", "scan", "triage", "finding", "verification", "finalize"],
}


class ReActLoop:
    """The core ReAct (Reason + Act) loop for code audit"""

    def __init__(
        self,
        state: AgentState,
        llm_adapter,
        registry: ToolRegistry,
        memory: MemoryManager,
        skill_manager: SkillManager,
        auto_persist: bool = True,
        max_turns: int = None,
    ):
        self.state = state
        self.llm = llm_adapter
        self.registry = registry
        self.memory = memory
        self.skills = skill_manager
        self.auto_persist = auto_persist  # False => findings collected in state only (orchestrator persists)
        self.max_turns = max_turns or settings.MAX_TURNS
        self._last_tool_calls = []  # For stuck detection
        self._stuck_count = 0

    def _scan_candidates_summary(self) -> str:
        if not self.state.scan_candidates:
            return ""
        lines = []
        for i, c in enumerate(self.state.scan_candidates, 1):
            lines.append(
                f"{i}. [{c.get('engine')}] {c.get('severity')} {c.get('rule_id')} "
                f"@ {c.get('file_path')}:{c.get('line_start', 0)} — {(c.get('message') or '')[:120]}"
            )
        return "\n".join(lines)

    def _coverage_note(self) -> str:
        if not self.state.all_files:
            return ""
        ratio = self.state.coverage_ratio()
        unread = len(self.state.all_files) - len(self.state.covered_files)
        return f"Coverage: {len(self.state.covered_files)}/{len(self.state.all_files)} files read ({ratio*100:.0f}%). Unread: {unread}. Prioritize unread entry points."

    async def run(self) -> AgentState:
        """Run the audit loop until termination"""
        try:
            # Build initial system prompt (with scan candidates injected by caller)
            system_prompt = build_system_prompt(
                project_name=self.state.project_name,
                project_path=self.state.project_path,
                tech_stack=self.state.tech_stack,
                skill_briefing=self.state.skill_briefing,
                mode=self.state.mode,
                scan_candidates_summary=self._scan_candidates_summary(),
                coverage_note=self._coverage_note(),
            )
            self.state.add_system_message(system_prompt)

            # Initial user message
            self.state.add_user_message(
                f"Please audit the project at: {self.state.project_path}\n"
                f"Mode: {self.state.mode}. Start by examining the project structure, "
                f"then systematically check for vulnerabilities following the stage plan."
            )

            while self.state.status == "running":
                if self.state.turn >= self.max_turns:
                    self.state.status = "max_turns"
                    self.state.terminal_reason = f"Reached max turns ({self.max_turns})"
                    break

                # Check global tool call budget (parent state if available, else local)
                global_tc = self.state.parent_state.tool_call_count if self.state.parent_state else self.state.tool_call_count
                if global_tc >= settings.MAX_TOOL_CALLS:
                    self.state.status = "failed"
                    self.state.terminal_reason = f"Exceeded max tool calls ({settings.MAX_TOOL_CALLS})"
                    break

                result = await self.run_turn()

                if result == "terminal":
                    break

            # Save final status
            await self._update_audit_status()
            return self.state

        except asyncio.CancelledError:
            self.state.status = "aborted"
            self.state.terminal_reason = "Task was cancelled"
            await self._update_audit_status()
            return self.state

        except Exception as e:
            self.state.status = "failed"
            self.state.terminal_reason = str(e)
            await self._update_audit_status()
            return self.state

    async def run_turn(self) -> str:
        """Execute a single turn of the ReAct loop"""
        self.state.increment_counters(turns=1)

        # Compress context if needed
        messages = self.state.messages
        if self.memory.needs_compression(messages):
            messages = self.memory.compress(messages, self.llm)
            if self.memory.needs_compression(messages):
                messages = await self.memory.llm_summarize(messages, self.llm)
            self.state.messages = messages

        # Get tool definitions
        tools = self.registry.describe()

        # Call LLM
        try:
            response = await self.llm.chat(messages, tools)
        except Exception as e:
            self.state.status = "failed"
            self.state.terminal_reason = f"LLM error: {str(e)}"
            return "terminal"

        self.state.increment_counters(tokens=response.usage.total)
        self.state.add_assistant_message(
            response.content,
            tool_calls=[
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    }
                }
                for tc in response.tool_calls
            ] if response.tool_calls else None,
        )

        # Log assistant message
        await self._log(turn=self.state.turn, role="assistant", content=response.content,
                        tokens=response.usage.total)

        # Handle tool calls
        if response.has_tool_calls:
            # Check for stuck loop
            if self._is_stuck(response.tool_calls):
                self._stuck_count += 1
                if self._stuck_count >= MAX_STUCK_COUNT:
                    self.state.add_nudge("stuck_loop", NUDGE_MESSAGES["stuck_loop"])
                    self._stuck_count = 0
                    return "continue"
            else:
                self._stuck_count = 0
            self._last_tool_calls = response.tool_calls

            # Execute tools
            for tc in response.tool_calls:
                self.state.increment_counters(tool_calls=1)
                tool_def = self.registry.get(tc.name)

                if not tool_def:
                    result = json.dumps({"error": f"Unknown tool: {tc.name}"})
                else:
                    try:
                        result = await tool_def.handler(**tc.arguments)
                    except Exception as e:
                        result = json.dumps({"error": f"Tool execution error: {str(e)}"})

                self.state.add_tool_result(tc.id, tc.name, result)

                # Log tool call
                await self._log(
                    turn=self.state.turn,
                    role="tool",
                    content=result,
                    tool_name=tc.name,
                    tool_args=tc.arguments,
                    tool_result=result,
                )

                # Check for finalize_finding
                if tc.name == "finalize_finding":
                    parsed = json.loads(result)
                    if parsed.get("status") == "accepted":
                        finding_data = parsed["finding"]
                        finding = FindingRecord(**finding_data)
                        self.state.add_finding(finding)
                        self.state.mark_file_covered(finding.file_path)

                        # Save to database (unless orchestrator collects)
                        if self.auto_persist:
                            await self._save_finding(finding)
                    else:
                        # Rejected - nudge
                        self.state.add_nudge("payload_invalid", NUDGE_MESSAGES["payload_invalid"])

                # Check for finish_audit (with coverage guard)
                if tc.name == "finish_audit":
                    force = bool(tc.arguments.get("force", False))
                    coverage_ok = self._coverage_check()
                    scan_ok = self._scan_check()

                    if not force and not coverage_ok:
                        self.state.add_nudge("low_coverage", NUDGE_MESSAGES["low_coverage"])
                        return "continue"
                    if not force and not scan_ok:
                        self.state.add_nudge("scan_required", NUDGE_MESSAGES["scan_required"])
                        return "continue"

                    self.state.status = "completed"
                    self.state.terminal_reason = "Agent called finish_audit"
                    self.state.mark_stage("finalize")
                    return "terminal"

            return "continue"

        # No tool calls - check if finished or needs nudge
        elif response.content.strip() == "":
            self.state.add_nudge("empty_response", NUDGE_MESSAGES["empty_response"])
            return "continue"

        else:
            # Has text but no tool calls and no finalize
            lower = response.content.lower()
            if any(kw in lower for kw in ["audit complete", "no more vulnerabilities", "audit finished", "finished"]):
                # Coverage-guarded early-exit path
                force = False
                coverage_ok = self._coverage_check()
                scan_ok = self._scan_check()
                if not coverage_ok:
                    self.state.add_nudge("low_coverage", NUDGE_MESSAGES["low_coverage"])
                    return "continue"
                if not scan_ok:
                    self.state.add_nudge("scan_required", NUDGE_MESSAGES["scan_required"])
                    return "continue"
                self.state.status = "completed"
                self.state.terminal_reason = "Agent indicated audit complete"
                self.state.mark_stage("finalize")
                return "terminal"

            # Nudge to continue
            self.state.add_nudge("no_tool_no_final", NUDGE_MESSAGES["no_tool_no_final"])
            return "continue"

    def _coverage_check(self) -> bool:
        """Coverage-driven termination guard."""
        if not self.state.all_files:
            return True
        audited = len([f for f in self.state.all_files if f in self.state.covered_files])
        return audited >= settings.COVERAGE_MIN_FILES

    def _scan_check(self) -> bool:
        """Require engine scan in modes that include a scan stage."""
        stages = MODE_STAGES.get(self.state.mode, [])
        if "scan" not in stages:
            return True
        if not settings.COVERAGE_REQUIRE_SCAN:
            return True
        # Allow finish if scan stage was completed or no scanners available.
        # We treat 'scan' as done if it is in stages_completed OR scanned flag set.
        return ("scan" in self.state.stages_completed) or self.state.scanned

    def _is_stuck(self, tool_calls) -> bool:
        """Detect if agent is making the same tool calls repeatedly"""
        if not self._last_tool_calls or len(tool_calls) != len(self._last_tool_calls):
            return False
        for new_tc, old_tc in zip(tool_calls, self._last_tool_calls):
            if new_tc.name != old_tc.name:
                return False
            if new_tc.arguments != old_tc.arguments:
                return False
        return True

    async def _log(self, turn: int, role: str, content: str, tool_name: str = "",
                   tool_args: dict = None, tool_result: str = "", tokens: int = 0):
        """Log to database. Uses parent audit_id so specialist logs land in the main audit."""
        # Use parent audit_id if available (specialist agents), else own audit_id
        log_audit_id = self.state.parent_state.audit_id if self.state.parent_state else self.state.audit_id
        specialist = self.state.specialist_name
        id_prefix = f"{log_audit_id}_{specialist}_" if specialist else f"{log_audit_id}_"
        try:
            async with async_session() as db:
                log = AuditLog(
                    id=f"{id_prefix}log_{turn}_{role}_{self.state.tool_call_count}",
                    audit_id=log_audit_id,
                    turn=turn,
                    role=role,
                    content=(f"[{specialist}] {content}" if specialist else content)[:5000] if content else "",
                    tool_name=tool_name,
                    tool_args=tool_args or {},
                    tool_result=tool_result[:5000] if tool_result else "",
                    tokens_used=tokens,
                )
                db.add(log)
                await db.commit()
        except Exception:
            pass  # Don't let logging fail the audit

    async def _save_finding(self, finding: FindingRecord):
        """Save finding to database. Uses parent audit_id for specialist agents."""
        log_audit_id = self.state.parent_state.audit_id if self.state.parent_state else self.state.audit_id
        specialist = self.state.specialist_name
        try:
            async with async_session() as db:
                db_finding = Finding(
                    id=f"{log_audit_id}_{'_'.join(specialist.split()) if specialist else ''}_finding_{len(self.state.findings)}".strip('_'),
                    audit_id=log_audit_id,
                    vulnerability_type=finding.vulnerability_type,
                    severity=finding.severity,
                    title=finding.title,
                    description=finding.description,
                    file_path=finding.file_path,
                    line_start=finding.line_start,
                    line_end=finding.line_end,
                    code_snippet=finding.code_snippet,
                    source=finding.source,
                    sink=finding.sink,
                    exploit_chain=finding.exploit_chain,
                    poc=finding.poc,
                    suggestion=finding.suggestion,
                    confidence=finding.confidence,
                    cwe=finding.cwe,
                    poc_verified=finding.poc_verified,
                )
                db.add(db_finding)
                await db.commit()
        except Exception as e:
            pass  # Don't let DB fail the audit

    async def _save_finding_safe(self, findings: list):
        """Batch-save findings (used by the orchestrator after merging)."""
        try:
            async with async_session() as db:
                for i, finding in enumerate(findings):
                    db_finding = Finding(
                        id=f"{self.state.audit_id}_finding_{i}",
                        audit_id=self.state.audit_id,
                        vulnerability_type=finding.vulnerability_type,
                        severity=finding.severity,
                        title=finding.title,
                        description=getattr(finding, "description", "") or "",
                        file_path=finding.file_path,
                        line_start=finding.line_start,
                        line_end=finding.line_end,
                        code_snippet=getattr(finding, "code_snippet", "") or "",
                        source=finding.source,
                        sink=finding.sink,
                        exploit_chain=finding.exploit_chain,
                        poc=getattr(finding, "poc", "") or "",
                        suggestion=getattr(finding, "suggestion", "") or "",
                        confidence=finding.confidence,
                        cwe=getattr(finding, "cwe", "") or "",
                        poc_verified=getattr(finding, "poc_verified", None),
                    )
                    db.add(db_finding)
                await db.commit()
        except Exception:
            pass

    async def _update_audit_status(self):
        """Update audit record in database. Uses parent audit_id for specialist agents."""
        log_audit_id = self.state.parent_state.audit_id if self.state.parent_state else self.state.audit_id
        try:
            async with async_session() as db:
                from sqlalchemy import select
                result = await db.execute(select(Audit).where(Audit.id == log_audit_id))
                audit = result.scalar_one_or_none()
                if audit:
                    audit.status = self.state.status
                    audit.turns_completed = self.state.turn
                    audit.total_tokens = self.state.total_tokens
                    audit.total_tool_calls = self.state.tool_call_count
                    audit.error_message = self.state.terminal_reason
                    audit.covered_files = list(self.state.covered_files)
                    audit.stage = self.state.stage
                    audit.stages_completed = self.state.stages_completed
                    audit.scan_candidates_count = len(self.state.scan_candidates)
                    if self.state.status in ("completed", "max_turns", "aborted", "failed"):
                        audit.completed_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception:
            pass
