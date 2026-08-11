"""API Key Management - CRUD + connectivity testing"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.crypto import encrypt_secret, decrypt_secret
from app.models.models import APIKey
from app.models.schemas import (
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyResponse,
    APIKeyTestResult,
)
from app.services.llm.testing import test_provider_connectivity
from app.services.llm.factory import LLMFactory

router = APIRouter(prefix="/api/keys", tags=["keys"])


def _mask_key(key: str) -> str:
    """Mask an API key: show first 4 + last 4 chars, hide the middle."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


def _to_response(k: APIKey) -> APIKeyResponse:
    """ORM → Pydantic (api_key masked unless explicitly requested via ?show=full)."""
    return APIKeyResponse(
        id=k.id,
        provider=k.provider,
        api_key=k.api_key,
        base_url=k.base_url or "",
        model=k.model or "",
        label=k.label or "",
        last_status=k.last_status or "unknown",
        last_tested_at=k.last_tested_at,
        last_error=k.last_error or "",
        created_at=k.created_at,
        updated_at=k.updated_at,
    )


@router.get("", response_model=list[APIKeyResponse])
async def list_keys(db: AsyncSession = Depends(get_db)):
    """List all stored API keys (masked by default)."""
    result = await db.execute(select(APIKey).order_by(APIKey.provider))
    keys = result.scalars().all()
    resp = [_to_response(k) for k in keys]
    for r in resp:
        r.api_key = _mask_key(r.api_key)
    return resp


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_key(key_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single API key by ID (masked)."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    k = result.scalar_one_or_none()
    if not k:
        raise HTTPException(404, f"API key {key_id} not found")
    resp = _to_response(k)
    resp.api_key = _mask_key(resp.api_key)
    return resp


@router.post("", response_model=APIKeyResponse)
async def create_key(payload: APIKeyCreate, db: AsyncSession = Depends(get_db)):
    """Create a new API key entry. Provider must be unique (upsert if exists)."""
    if payload.provider not in LLMFactory.supported_providers():
        raise HTTPException(
            400,
            f"Unsupported provider: {payload.provider}. "
            f"Supported: {LLMFactory.supported_providers()}",
        )
    if not payload.api_key or not payload.api_key.strip():
        raise HTTPException(400, "api_key must not be empty")

    # Upsert by provider
    result = await db.execute(select(APIKey).where(APIKey.provider == payload.provider))
    existing = result.scalar_one_or_none()
    if existing:
        existing.api_key = encrypt_secret(payload.api_key.strip())
        if payload.base_url:
            existing.base_url = payload.base_url
        if payload.model:
            existing.model = payload.model
        if payload.label:
            existing.label = payload.label
        existing.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        return _to_response(existing)

    new_key = APIKey(
        id=str(uuid.uuid4())[:8],
        provider=payload.provider.lower(),
        api_key=encrypt_secret(payload.api_key.strip()),
        base_url=payload.base_url or "",
        model=payload.model or "",
        label=payload.label or "",
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    return _to_response(new_key)


@router.patch("/{key_id}", response_model=APIKeyResponse)
async def update_key(key_id: str, payload: APIKeyUpdate, db: AsyncSession = Depends(get_db)):
    """Update an existing API key."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    k = result.scalar_one_or_none()
    if not k:
        raise HTTPException(404, f"API key {key_id} not found")

    if payload.api_key is not None:
        k.api_key = encrypt_secret(payload.api_key)
    if payload.base_url is not None:
        k.base_url = payload.base_url
    if payload.model is not None:
        k.model = payload.model
    if payload.label is not None:
        k.label = payload.label
    k.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(k)
    return _to_response(k)


@router.delete("/{key_id}")
async def delete_key(key_id: str, db: AsyncSession = Depends(get_db)):
    """Delete an API key by ID. Returns the deleted key summary."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    k = result.scalar_one_or_none()
    if not k:
        raise HTTPException(404, f"API key {key_id} not found")
    info = {"id": k.id, "provider": k.provider}
    await db.delete(k)
    await db.commit()
    return {"deleted": info, "message": f"API key for {info['provider']} deleted"}


@router.post("/{key_id}/test", response_model=APIKeyTestResult)
async def test_key(key_id: str, db: AsyncSession = Depends(get_db)):
    """Test stored API key connectivity against the provider."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    k = result.scalar_one_or_none()
    if not k:
        raise HTTPException(404, f"API key {key_id} not found")

    test_result = await test_provider_connectivity(
        provider=k.provider,
        api_key=decrypt_secret(k.api_key),
        base_url=k.base_url,
        model=k.model,
    )

    # Persist the test outcome
    k.last_status = test_result["status"]
    k.last_tested_at = test_result["tested_at"]
    k.last_error = "" if test_result["ok"] else test_result["message"]
    k.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return APIKeyTestResult(
        provider=k.provider,
        ok=test_result["ok"],
        status=test_result["status"],
        model=test_result["model"],
        message=test_result["message"],
        latency_ms=test_result["latency_ms"],
        tested_at=test_result["tested_at"],
    )


@router.post("/test", response_model=APIKeyTestResult)
async def test_provided_key(payload: APIKeyCreate):
    """Test an API key before saving it (does not persist)."""
    if payload.provider not in LLMFactory.supported_providers():
        raise HTTPException(
            400,
            f"Unsupported provider: {payload.provider}. "
            f"Supported: {LLMFactory.supported_providers()}",
        )
    if not payload.api_key or not payload.api_key.strip():
        raise HTTPException(400, "api_key must not be empty")

    test_result = await test_provider_connectivity(
        provider=payload.provider,
        api_key=payload.api_key.strip(),
        base_url=payload.base_url,
        model=payload.model,
    )
    return APIKeyTestResult(
        provider=payload.provider,
        ok=test_result["ok"],
        status=test_result["status"],
        model=test_result["model"],
        message=test_result["message"],
        latency_ms=test_result["latency_ms"],
        tested_at=test_result["tested_at"],
    )