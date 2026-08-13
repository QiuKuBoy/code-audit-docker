"""Audits API routes"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sa_delete
from datetime import datetime, timezone
import json

from app.core.database import get_db
from app.models.models import Audit, Finding, AuditLog, Project
from app.models.schemas import (
    AuditCreate, AuditResponse, FindingResponse, AuditLogResponse,
    BatchAuditCreate, BatchAuditResponse, AuditCompare,
)
from app.services.agent.service import start_audit

router = APIRouter(prefix="/api/audits", tags=["audits"])


@router.post("", response_model=dict)
async def create_audit(data: AuditCreate):
    try:
        audit_id = await start_audit(
            project_id=data.project_id,
            mode=data.mode,
            llm_provider=data.llm_provider,
            llm_model=data.llm_model,
            llm_api_key=data.llm_api_key,
            llm_base_url=data.llm_base_url,
            max_turns=data.max_turns,
        )
        return {"audit_id": audit_id, "status": "started"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch", response_model=BatchAuditResponse)
async def create_batch_audits(data: BatchAuditCreate):
    """Start audits for multiple projects"""
    started = []
    failed = []
    for pid in data.project_ids:
        try:
            audit_id = await start_audit(
                project_id=pid,
                mode=data.mode,
                llm_provider=data.llm_provider,
                llm_model=data.llm_model,
                llm_api_key=data.llm_api_key,
                llm_base_url=data.llm_base_url,
                max_turns=data.max_turns,
            )
            started.append(audit_id)
        except Exception as e:
            failed.append({"project_id": pid, "error": str(e)})
    return BatchAuditResponse(started=started, failed=failed)


@router.get("", response_model=list[AuditResponse])
async def list_audits(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Audit).order_by(Audit.created_at.desc()))
    audits = result.scalars().all()
    return [_audit_to_response(a) for a in audits]


@router.delete("/{audit_id}")
async def delete_audit(audit_id: str, db: AsyncSession = Depends(get_db)):
    """Delete an audit with cascade: sub-agent records + findings + logs."""
    # Reject deletion while audit is running/pending
    result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status in ("running", "pending"):
        raise HTTPException(status_code=409, detail="Cannot delete a running audit. Abort it first.")

    prefix = audit_id + "_"

    # Cascade: sub-agent audits (audit_id LIKE 'id_%')
    sub = await db.execute(
        sa_delete(Audit).where(Audit.id.like(prefix + "%"))
    )
    deleted_sub_audits = sub.rowcount or 0

    # Findings (main + sub-agents)
    f_res = await db.execute(
        sa_delete(Finding).where(
            (Finding.audit_id == audit_id) | (Finding.audit_id.like(prefix + "%"))
        )
    )
    deleted_findings = f_res.rowcount or 0

    # Logs (main + sub-agents)
    l_res = await db.execute(
        sa_delete(AuditLog).where(
            (AuditLog.audit_id == audit_id) | (AuditLog.audit_id.like(prefix + "%"))
        )
    )
    deleted_logs = l_res.rowcount or 0

    # Main audit row
    await db.delete(audit)
    await db.commit()

    return {
        "status": "deleted",
        "audit_id": audit_id,
        "deleted_audits": 1 + deleted_sub_audits,
        "deleted_findings": deleted_findings,
        "deleted_logs": deleted_logs,
    }


@router.post("/batch-delete")
async def batch_delete_audits(body: dict, db: AsyncSession = Depends(get_db)):
    """Delete multiple audits. Each is handled independently so one failure
    does not abort the rest."""
    audit_ids = body.get("audit_ids") or []
    if not audit_ids:
        raise HTTPException(status_code=400, detail="audit_ids is required")
    if len(audit_ids) > 100:
        raise HTTPException(status_code=400, detail="Max 100 audits per batch")

    deleted = []
    failed = []
    for aid in audit_ids:
        try:
            result = await db.execute(select(Audit).where(Audit.id == aid))
            audit = result.scalar_one_or_none()
            if not audit:
                failed.append({"audit_id": aid, "error": "not found"})
                continue
            if audit.status in ("running", "pending"):
                failed.append({"audit_id": aid, "error": "running"})
                continue
            prefix = aid + "_"
            await db.execute(sa_delete(Audit).where(Audit.id.like(prefix + "%")))
            await db.execute(sa_delete(Finding).where(
                (Finding.audit_id == aid) | (Finding.audit_id.like(prefix + "%"))
            ))
            await db.execute(sa_delete(AuditLog).where(
                (AuditLog.audit_id == aid) | (AuditLog.audit_id.like(prefix + "%"))
            ))
            await db.delete(audit)
            deleted.append(aid)
        except Exception as e:
            failed.append({"audit_id": aid, "error": str(e)[:120]})
    await db.commit()
    return {"deleted": deleted, "failed": failed, "deleted_count": len(deleted)}


@router.get("/{audit_id}", response_model=AuditResponse)
async def get_audit(audit_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    return _audit_to_response(audit)


@router.post("/{audit_id}/abort", response_model=dict)
async def abort_audit(audit_id: str, db: AsyncSession = Depends(get_db)):
    """Abort a running audit"""
    result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status not in ("running", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot abort audit with status: {audit.status}")
    audit.status = "aborted"
    audit.error_message = "Aborted by user"
    audit.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "aborted"}


@router.post("/{audit_id}/resume", response_model=dict)
async def resume_audit(audit_id: str, db: AsyncSession = Depends(get_db)):
    """Resume a paused/aborted audit"""
    result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status not in ("aborted", "failed", "paused"):
        raise HTTPException(status_code=400, detail=f"Cannot resume audit with status: {audit.status}")

    # Get project info
    proj_result = await db.execute(select(Project).where(Project.id == audit.project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Resume in background
    import asyncio
    from app.services.agent.service import _run_audit_task, _resolve_api_key, _BACKGROUND_TASKS
    from app.core.crypto import decrypt_secret

    # Resolve the API key the same way start_audit does (explicit > DB).
    # audit.llm_api_key is encrypted at rest — decrypt before use.
    stored_key = decrypt_secret(audit.llm_api_key) if audit.llm_api_key else ""
    try:
        resolved_key = await _resolve_api_key(audit.llm_provider, stored_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit.status = "running"
    audit.error_message = ""
    await db.commit()

    task = asyncio.create_task(_run_audit_task(
        audit_id=audit_id,
        project_path=project.path,
        project_name=project.name,
        tech_stack=project.tech_stack,
        llm_provider=audit.llm_provider,
        llm_model=audit.llm_model,
        llm_api_key=resolved_key,
        llm_base_url="",
        max_turns=audit.max_turns,
        mode=audit.mode or "smart",
    ))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return {"status": "resumed"}


@router.get("/{audit_id}/findings", response_model=list[FindingResponse])
async def get_audit_findings(audit_id: str, db: AsyncSession = Depends(get_db)):
    # Match the audit plus any sub-agent records (audit_id_<specialist>)
    prefix = audit_id + "_"
    result = await db.execute(
        select(Finding)
        .where((Finding.audit_id == audit_id) | (Finding.audit_id.like(prefix + "%")))
        .order_by(Finding.severity, Finding.created_at)
    )
    findings = result.scalars().all()
    return [_finding_to_response(f) for f in findings]


@router.get("/{audit_id}/logs", response_model=list[AuditLogResponse])
async def get_audit_logs(audit_id: str, limit: int = 100, db: AsyncSession = Depends(get_db)):
    # Match the audit plus any sub-agent records; sub-agent ids carry
    # specialist suffixes so keep them grouped by (turn, timestamp)
    prefix = audit_id + "_"
    result = await db.execute(
        select(AuditLog)
        .where((AuditLog.audit_id == audit_id) | (AuditLog.audit_id.like(prefix + "%")))
        .order_by(AuditLog.turn, AuditLog.timestamp)
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        AuditLogResponse(
            id=l.id, audit_id=l.audit_id, turn=l.turn, role=l.role,
            content=l.content, tool_name=l.tool_name, tool_args=l.tool_args,
            tool_result=l.tool_result, tokens_used=l.tokens_used,
            timestamp=l.timestamp,
        )
        for l in logs
    ]


@router.get("/{audit_id}/report", response_class=PlainTextResponse)
async def export_audit_report(audit_id: str, db: AsyncSession = Depends(get_db)):
    """Export audit report as Markdown"""
    # Get audit
    audit_result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = audit_result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    # Get project
    proj_result = await db.execute(select(Project).where(Project.id == audit.project_id))
    project = proj_result.scalar_one_or_none()

    # Get findings
    findings_result = await db.execute(
        select(Finding).where(Finding.audit_id == audit_id).order_by(Finding.severity, Finding.created_at)
    )
    findings = findings_result.scalars().all()

    # Build markdown report
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 99))

    from app.services.agent.export.sarif import cwe_for_type, cvss_base_score

    lines = [
        f"# Code Security Audit Report",
        f"",
        f"**Project:** {project.name if project else 'Unknown'}",
        f"**Path:** `{project.path if project else 'N/A'}`",
        f"**Tech Stack:** {', '.join(project.tech_stack) if project and project.tech_stack else 'N/A'}",
        f"**Audit Mode:** {audit.mode}",
        f"**LLM:** {audit.llm_provider} / {audit.llm_model}",
        f"**Status:** {audit.status}",
        f"**Stage:** {audit.stage} (completed: {', '.join(audit.stages_completed or []) or 'none'})",
        f"**Coverage:** {len(audit.covered_files or [])} files read" + (f", {audit.scan_candidates_count or 0} engine candidates" if audit.scan_candidates_count else ""),
        f"**Date:** {audit.created_at.strftime('%Y-%m-%d %H:%M UTC') if audit.created_at else 'N/A'}",
        f"**Duration:** {audit.turns_completed} turns, {audit.total_tool_calls} tool calls, {audit.total_tokens:,} tokens",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Severity | Count |",
        f"|----------|-------|",
    ]

    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    type_counts = {}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
        type_counts[f.vulnerability_type] = type_counts.get(f.vulnerability_type, 0) + 1

    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        lines.append(f"| {sev} | {severity_counts.get(sev, 0)} |")

    lines.append(f"")
    lines.append(f"| Vulnerability Type | Count |")
    lines.append(f"|---------------------|-------|")
    for vtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {vtype} | {count} |")

    lines.append(f"")
    lines.append(f"**Total Findings:** {len(findings)}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    if not sorted_findings:
        lines.append("## No vulnerabilities found.")
    else:
        for i, f in enumerate(sorted_findings, 1):
            lines.append(f"## {i}. [{f.severity}] {f.title}")
            lines.append(f"")
            lines.append(f"- **Type:** {f.vulnerability_type}")
            lines.append(f"- **File:** `{f.file_path}`" + (f":{f.line_start}" if f.line_start else ""))
            lines.append(f"- **Confidence:** {f.confidence}")
            lines.append(f"- **CWE:** {f.cwe or cwe_for_type(f.vulnerability_type)}")
            lines.append(f"- **CVSS 3.1 Base:** {cvss_base_score(f.severity)}")
            lines.append(f"")
            if f.description:
                lines.append(f"### Description")
                lines.append(f"")
                lines.append(f"{f.description}")
                lines.append(f"")
            lines.append(f"### Taint Chain")
            lines.append(f"")
            lines.append(f"- **Source:** `{f.source}`")
            lines.append(f"- **Sink:** `{f.sink}`")
            lines.append(f"")
            if f.exploit_chain:
                lines.append(f"### Exploit Chain")
                lines.append(f"")
                lines.append(f"```")
                lines.append(f"{f.exploit_chain}")
                lines.append(f"```")
                lines.append(f"")
            if f.code_snippet:
                lines.append(f"### Vulnerable Code")
                lines.append(f"")
                lines.append(f"```python")
                lines.append(f"{f.code_snippet}")
                lines.append(f"```")
                lines.append(f"")
            if f.poc:
                lines.append(f"### PoC")
                lines.append(f"")
                lines.append(f"```python")
                lines.append(f"{f.poc}")
                lines.append(f"```")
                lines.append(f"")
                if f.poc_verified is not None:
                    lines.append(f"> PoC verification: {'passed' if f.poc_verified else 'failed/blocked'} (static/sandbox)")
                    lines.append(f"")
            if f.suggestion:
                lines.append(f"### Suggested Fix")
                lines.append(f"")
                lines.append(f"{f.suggestion}")
                lines.append(f"")
            lines.append(f"---")
            lines.append(f"")

    return "\n".join(lines)


@router.get("/{audit_id}/sarif", response_class=PlainTextResponse)
async def export_audit_sarif(audit_id: str, db: AsyncSession = Depends(get_db)):
    """Export audit findings as SARIF 2.1.0 JSON (industry-standard format)."""
    from app.services.agent.export.sarif import build_sarif

    audit_result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = audit_result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    proj_result = await db.execute(select(Project).where(Project.id == audit.project_id))
    project = proj_result.scalar_one_or_none()

    findings_result = await db.execute(
        select(Finding).where(Finding.audit_id == audit_id).order_by(Finding.severity, Finding.created_at)
    )
    findings = findings_result.scalars().all()

    sarif = build_sarif(findings, project_name=project.name if project else "project")
    return json.dumps(sarif, ensure_ascii=False, indent=2)


@router.get("/{audit_id}/compare/{other_audit_id}", response_model=AuditCompare)
async def compare_audits(audit_id: str, other_audit_id: str, db: AsyncSession = Depends(get_db)):
    """Compare findings between two audits"""
    # Fetch findings for both
    a_result = await db.execute(select(Finding).where(Finding.audit_id == audit_id))
    a_findings = a_result.scalars().all()
    b_result = await db.execute(select(Finding).where(Finding.audit_id == other_audit_id))
    b_findings = b_result.scalars().all()

    # Match by (vulnerability_type, file_path, title) as identity
    def finding_key(f):
        return (f.vulnerability_type, f.file_path, f.title)

    a_map = {finding_key(f): f for f in a_findings}
    b_map = {finding_key(f): f for f in b_findings}

    only_a = [f for f in a_findings if finding_key(f) not in b_map]
    only_b = [f for f in b_findings if finding_key(f) not in a_map]
    common = [f for f in a_findings if finding_key(f) in b_map]

    return AuditCompare(
        audit_a_id=audit_id,
        audit_b_id=other_audit_id,
        only_in_a=[_finding_to_response(f) for f in only_a],
        only_in_b=[_finding_to_response(f) for f in only_b],
        common=[_finding_to_response(f) for f in common],
    )


# ── Helpers ──────────────────────────────────────────────

def _audit_to_response(a: Audit) -> AuditResponse:
    return AuditResponse(
        id=a.id, project_id=a.project_id, mode=a.mode, status=a.status,
        llm_provider=a.llm_provider, llm_model=a.llm_model,
        turns_completed=a.turns_completed, total_tokens=a.total_tokens,
        total_tool_calls=a.total_tool_calls, covered_files=a.covered_files or [],
        stage=a.stage or "recon", stages_completed=a.stages_completed or [],
        scan_candidates_count=a.scan_candidates_count or 0,
        error_message=a.error_message,
        created_at=a.created_at, completed_at=a.completed_at,
    )

def _finding_to_response(f: Finding) -> FindingResponse:
    return FindingResponse(
        id=f.id, audit_id=f.audit_id, vulnerability_type=f.vulnerability_type,
        severity=f.severity, title=f.title, description=f.description,
        file_path=f.file_path, line_start=f.line_start, line_end=f.line_end,
        code_snippet=f.code_snippet, source=f.source, sink=f.sink,
        exploit_chain=f.exploit_chain, poc=f.poc, suggestion=f.suggestion,
        confidence=f.confidence, cwe=f.cwe or "", poc_verified=f.poc_verified,
        needs_verification=f.needs_verification,
        created_at=f.created_at,
    )
