"""Code Audit - Pydantic Schemas"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    path: str
    description: str = ""
    language: str = ""   # optional manual language/tech-stack override ("auto" = auto-detect)


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    tech_stack: list = []
    description: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AuditCreate(BaseModel):
    project_id: str
    mode: str = "smart"
    llm_provider: str = "deepseek"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    max_turns: int = 50


class AuditResponse(BaseModel):
    id: str
    project_id: str
    mode: str
    status: str
    llm_provider: str
    llm_model: str = ""
    turns_completed: int = 0
    total_tokens: int = 0
    total_tool_calls: int = 0
    covered_files: list = []
    stage: str = "recon"
    stages_completed: list = []
    scan_candidates_count: int = 0
    error_message: str = ""
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class FindingResponse(BaseModel):
    id: str
    audit_id: str
    vulnerability_type: str
    severity: str
    title: str
    description: str = ""
    file_path: str
    line_start: int = 0
    line_end: int = 0
    code_snippet: str = ""
    source: str = ""
    sink: str = ""
    exploit_chain: str = ""
    poc: str = ""
    suggestion: str = ""
    confidence: str = "MEDIUM"
    cwe: str = ""
    poc_verified: Optional[bool] = None
    needs_verification: bool = True
    created_at: Optional[datetime] = None


class AuditLogResponse(BaseModel):
    id: str
    audit_id: str
    turn: int
    role: str
    content: str = ""
    tool_name: str = ""
    tool_args: dict = {}
    tool_result: str = ""
    tokens_used: int = 0
    timestamp: Optional[datetime] = None


class LLMConfigInfo(BaseModel):
    """Info about available LLM providers and their configuration status"""
    provider: str
    configured: bool
    default_model: str


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_projects: int = 0
    total_audits: int = 0
    total_findings: int = 0
    total_tokens: int = 0
    total_tool_calls: int = 0
    findings_by_severity: dict = {}
    findings_by_type: dict = {}
    audits_by_status: dict = {}
    recent_audits: list = []
    severity_timeline: list = []  # [{audit_id, created_at, critical, high, medium, low}]


class BatchAuditCreate(BaseModel):
    """Create audits for multiple projects at once"""
    project_ids: list[str]
    mode: str = "smart"
    llm_provider: str = "deepseek"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    max_turns: int = 50


class BatchAuditResponse(BaseModel):
    started: list[str] = []
    failed: list[dict] = []  # [{project_id, error}]


class AuditCompare(BaseModel):
    """Compare findings between two audits"""
    audit_a_id: str
    audit_b_id: str
    only_in_a: list[FindingResponse] = []
    only_in_b: list[FindingResponse] = []
    common: list[FindingResponse] = []


# ── API Key Management ───────────────────────────────────

class APIKeyBase(BaseModel):
    provider: str
    api_key: str
    base_url: str = ""
    model: str = ""
    label: str = ""


class APIKeyCreate(APIKeyBase):
    pass


class APIKeyUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    label: Optional[str] = None


class APIKeyResponse(BaseModel):
    id: str
    provider: str
    api_key: str  # returned in full to support editing; the UI should mask it
    base_url: str = ""
    model: str = ""
    label: str = ""
    last_status: str = "unknown"
    last_tested_at: Optional[datetime] = None
    last_error: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class APIKeyTestResult(BaseModel):
    provider: str
    ok: bool
    status: str  # ok / failed
    model: str = ""
    message: str = ""
    latency_ms: int = 0
    tested_at: Optional[datetime] = None
