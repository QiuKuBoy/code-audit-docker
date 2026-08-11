"""Dashboard API - Statistics and overview"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.models import Project, Audit, Finding
from app.models.schemas import DashboardStats, FindingResponse
from datetime import datetime

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get overall statistics for dashboard"""

    # Counts
    total_projects = await db.scalar(select(func.count(Project.id)))
    total_audits = await db.scalar(select(func.count(Audit.id)))
    total_findings = await db.scalar(select(func.count(Finding.id)))
    total_tokens = await db.scalar(select(func.coalesce(func.sum(Audit.total_tokens), 0)))
    total_tool_calls = await db.scalar(select(func.coalesce(func.sum(Audit.total_tool_calls), 0)))

    # Findings by severity
    sev_result = await db.execute(
        select(Finding.severity, func.count(Finding.id))
        .group_by(Finding.severity)
    )
    findings_by_severity = {row[0]: row[1] for row in sev_result}

    # Findings by type
    type_result = await db.execute(
        select(Finding.vulnerability_type, func.count(Finding.id))
        .group_by(Finding.vulnerability_type)
        .order_by(func.count(Finding.id).desc())
    )
    findings_by_type = {row[0]: row[1] for row in type_result}

    # Audits by status
    status_result = await db.execute(
        select(Audit.status, func.count(Audit.id))
        .group_by(Audit.status)
    )
    audits_by_status = {row[0]: row[1] for row in status_result}

    # Recent audits
    recent_result = await db.execute(
        select(Audit).order_by(Audit.created_at.desc()).limit(10)
    )
    recent_audits = []
    for a in recent_result.scalars().all():
        # Count findings per audit
        f_count = await db.scalar(
            select(func.count(Finding.id)).where(Finding.audit_id == a.id)
        )
        # Get project name
        proj = await db.scalar(select(Project).where(Project.id == a.project_id))
        recent_audits.append({
            "id": a.id,
            "project_name": proj.name if proj else "Unknown",
            "project_id": a.project_id,
            "status": a.status,
            "mode": a.mode,
            "llm_provider": a.llm_provider,
            "findings_count": f_count or 0,
            "turns": a.turns_completed,
            "tokens": a.total_tokens,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    # Severity timeline: findings per audit ordered by time
    timeline_result = await db.execute(
        select(Audit.id, Audit.created_at).order_by(Audit.created_at).limit(20)
    )
    severity_timeline = []
    for audit_id, created_at in timeline_result:
        sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        f_result = await db.execute(
            select(Finding.severity, func.count(Finding.id))
            .where(Finding.audit_id == audit_id)
            .group_by(Finding.severity)
        )
        for sev, cnt in f_result:
            sev_key = sev.lower() if sev.lower() in sev_counts else "low"
            sev_counts[sev_key] = cnt
        severity_timeline.append({
            "audit_id": audit_id,
            "created_at": created_at.isoformat() if created_at else None,
            **sev_counts,
        })

    return DashboardStats(
        total_projects=total_projects or 0,
        total_audits=total_audits or 0,
        total_findings=total_findings or 0,
        total_tokens=total_tokens or 0,
        total_tool_calls=total_tool_calls or 0,
        findings_by_severity=findings_by_severity,
        findings_by_type=findings_by_type,
        audits_by_status=audits_by_status,
        recent_audits=recent_audits,
        severity_timeline=severity_timeline,
    )
