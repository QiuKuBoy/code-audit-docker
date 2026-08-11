"""Code Audit - Data Models"""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    tech_stack = Column(JSON, default=list)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    audits = relationship("Audit", back_populates="project", cascade="all, delete-orphan")


class Audit(Base):
    __tablename__ = "audits"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    mode = Column(String, default="smart")  # quick / smart / comprehensive
    status = Column(String, default="pending")  # pending / running / completed / failed / aborted / paused
    llm_provider = Column(String, default="deepseek")
    llm_model = Column(String, default="")
    llm_api_key = Column(String, default="")  # encrypted at rest ideally, stored for resume
    llm_base_url = Column(String, default="")
    max_turns = Column(Integer, default=50)
    turns_completed = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_tool_calls = Column(Integer, default=0)
    covered_files = Column(JSON, default=list)  # files already audited
    stage = Column(String, default="recon")    # current audit stage
    stages_completed = Column(JSON, default=list)  # completed stages
    scan_candidates_count = Column(Integer, default=0)  # engine candidates injected
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="audits")
    findings = relationship("Finding", back_populates="audit", cascade="all, delete-orphan")
    logs = relationship("AuditLog", back_populates="audit", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String, primary_key=True, index=True)
    audit_id = Column(String, ForeignKey("audits.id"), nullable=False)
    vulnerability_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)  # CRITICAL / HIGH / MEDIUM / LOW
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    file_path = Column(String, nullable=False)
    line_start = Column(Integer, default=0)
    line_end = Column(Integer, default=0)
    code_snippet = Column(Text, default="")
    source = Column(Text, default="")
    sink = Column(Text, default="")
    exploit_chain = Column(Text, default="")
    poc = Column(Text, default="")
    suggestion = Column(Text, default="")
    confidence = Column(String, default="MEDIUM")
    cwe = Column(String, default="")  # CWE identifier, e.g. CWE-89
    poc_verified = Column(Boolean, nullable=True)  # None=no poc, True/False after check
    needs_verification = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="findings")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    audit_id = Column(String, ForeignKey("audits.id"), nullable=False)
    turn = Column(Integer, default=0)
    role = Column(String, nullable=False)  # system / user / assistant / tool
    content = Column(Text, default="")
    tool_name = Column(String, default="")
    tool_args = Column(JSON, default=dict)
    tool_result = Column(Text, default="")
    tokens_used = Column(Integer, default=0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit = relationship("Audit", back_populates="logs")


class APIKey(Base):
    """User-managed LLM provider API keys (stored in DB, not .env)."""
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, index=True)
    provider = Column(String, nullable=False, unique=True, index=True)
    api_key = Column(String, nullable=False)
    base_url = Column(String, default="")
    model = Column(String, default="")
    label = Column(String, default="")
    last_status = Column(String, default="unknown")  # unknown / ok / failed
    last_tested_at = Column(DateTime, nullable=True)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
