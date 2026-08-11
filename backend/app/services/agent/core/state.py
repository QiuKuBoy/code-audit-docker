"""Agent State - Manages conversation state and audit progress"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
import uuid
import time


@dataclass
class FindingRecord:
    """A discovered vulnerability"""
    vulnerability_type: str
    severity: str
    title: str
    file_path: str
    line_start: int
    line_end: int
    code_snippet: str = ""
    description: str = ""
    source: str = ""
    sink: str = ""
    exploit_chain: str = ""
    poc: str = ""
    suggestion: str = ""
    confidence: str = "MEDIUM"
    cwe: str = ""
    poc_verified: Optional[bool] = None


@dataclass
class AgentState:
    """Mutable state of an audit session"""
    audit_id: str
    project_path: str
    project_name: str
    tech_stack: list = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    findings: list[FindingRecord] = field(default_factory=list)
    covered_files: set = field(default_factory=set)
    turn: int = 0
    tool_call_count: int = 0
    total_tokens: int = 0
    status: str = "running"  # running / completed / failed / aborted / max_turns
    terminal_reason: str = ""
    skill_briefing: str = ""
    mode: str = "smart"  # quick / smart / comprehensive
    stage: str = "recon"  # recon / scan / triage / finding / verification / finalize
    stages_completed: list = field(default_factory=list)
    scan_candidates: list = field(default_factory=list)  # engine hits fed to LLM
    scanned: bool = False
    all_files: list = field(default_factory=list)  # discovered project files
    started_at: float = field(default_factory=time.time)
    # ── Multi-agent coordination ──
    parent_state: Optional["AgentState"] = None  # reference to parent for shared counters
    specialist_name: str = ""  # e.g. "SQL_Injection", set for child agents

    def add_system_message(self, content: str):
        self.messages.append({"role": "system", "content": content})

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str, tool_calls: list = None):
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    def add_tool_result(self, tool_call_id: str, tool_name: str, result: str):
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "content": result,
        })

    def add_nudge(self, nudge_type: str, content: str):
        """Inject a nudge as a user message"""
        self.messages.append({
            "role": "user",
            "content": f"[System Guidance - {nudge_type}] {content}",
        })

    def mark_file_covered(self, file_path: str):
        self.covered_files.add(file_path)
        if self.parent_state:
            self.parent_state.covered_files.add(file_path)

    def add_finding(self, finding: FindingRecord):
        self.findings.append(finding)
        # NOTE: findings are NOT auto-propagated to parent_state.
        # They must be verified first (adversarial verification) before
        # service.py adds them manually. Covered files and counters still
        # propagate via mark_file_covered/increment_counters.

    def increment_counters(self, turns: int = 0, tool_calls: int = 0, tokens: int = 0):
        """Increment local + parent counters (for shared MAX_TOOL_CALLS enforcement)."""
        self.turn += turns
        self.tool_call_count += tool_calls
        self.total_tokens += tokens
        if self.parent_state:
            self.parent_state.turn += turns
            self.parent_state.tool_call_count += tool_calls
            self.parent_state.total_tokens += tokens

    def mark_stage(self, stage: str):
        """Advance to a new audit stage, recording the previous one."""
        if self.stage and self.stage != stage and self.stage not in self.stages_completed:
            self.stages_completed.append(self.stage)
        self.stage = stage

    def coverage_ratio(self) -> float:
        if not self.all_files:
            return 0.0
        audited = len([f for f in self.all_files if f in self.covered_files])
        return round(audited / len(self.all_files), 3)

    def to_checkpoint(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "turn": self.turn,
            "tool_call_count": self.tool_call_count,
            "total_tokens": self.total_tokens,
            "covered_files": list(self.covered_files),
            "findings_count": len(self.findings),
            "status": self.status,
            "stage": self.stage,
            "stages_completed": self.stages_completed,
            "timestamp": time.time(),
        }
