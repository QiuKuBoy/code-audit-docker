"""Projects API routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from app.core.database import get_db
from app.models.models import Project, Audit
from app.models.schemas import ProjectCreate, ProjectResponse, AuditResponse
from app.services.agent.service import create_project

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse)
async def create_project_route(data: ProjectCreate):
    try:
        result = await create_project(data.name, data.path, data.description, getattr(data, 'language', ''))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [
        ProjectResponse(
            id=p.id, name=p.name, path=p.path, tech_stack=p.tech_stack,
            description=p.description, created_at=p.created_at, updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=project.id, name=project.name, path=project.path,
        tech_stack=project.tech_stack, description=project.description,
        created_at=project.created_at, updated_at=project.updated_at,
    )


@router.get("/{project_id}/audits", response_model=list[AuditResponse])
async def list_project_audits(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Audit).where(Audit.project_id == project_id).order_by(Audit.created_at.desc())
    )
    audits = result.scalars().all()
    return [
        AuditResponse(
            id=a.id, project_id=a.project_id, mode=a.mode, status=a.status,
            llm_provider=a.llm_provider, llm_model=a.llm_model,
            turns_completed=a.turns_completed, total_tokens=a.total_tokens,
            total_tool_calls=a.total_tool_calls, error_message=a.error_message,
            created_at=a.created_at, completed_at=a.completed_at,
        )
        for a in audits
    ]


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()
    return {"status": "deleted"}
