"""
PII Profiles API — CRUD + test endpoint.

Profiles are named collections of PII redaction rules that can be attached
to a pii_redact TOOL_NODE via `tool_params.profile_id`. Scoped to projects
via `project_id` (NULL = global, available across all projects).
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from db.database import AsyncSessionLocal
from models.pii_profile import PIIProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pii-profiles", tags=["pii-profiles"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class CustomPIIType(BaseModel):
    name: str = Field(..., description="Type name, e.g. 'internal_id'")
    trigger_phrases: List[str] = Field(default_factory=list, description="Context phrases")
    value_regex: str = Field("", description="Regex for the value following the trigger")


class PIIProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    project_id: Optional[int] = None
    blocklist: List[str] = Field(default_factory=list)
    allowlist: List[str] = Field(default_factory=list)
    custom_types: List[CustomPIIType] = Field(default_factory=list)
    enabled_builtin_types: List[str] = Field(default_factory=list)


class PIIProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    project_id: Optional[int] = None
    blocklist: Optional[List[str]] = None
    allowlist: Optional[List[str]] = None
    custom_types: Optional[List[CustomPIIType]] = None
    enabled_builtin_types: Optional[List[str]] = None


class PIIProfileResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    project_id: Optional[int]
    blocklist: List[str]
    allowlist: List[str]
    custom_types: List[Dict[str, Any]]
    enabled_builtin_types: List[str]
    created_at: datetime
    updated_at: datetime


class PIITestRequest(BaseModel):
    text: str
    strategy: str = "redact"


class PIITestResponse(BaseModel):
    redacted_text: str
    items_detected: int
    types_detected: List[str]


# ─── Helpers ────────────────────────────────────────────────────────────────


def _to_response(profile: PIIProfile) -> PIIProfileResponse:
    return PIIProfileResponse(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        project_id=profile.project_id,
        blocklist=profile.blocklist or [],
        allowlist=profile.allowlist or [],
        custom_types=profile.custom_types or [],
        enabled_builtin_types=profile.enabled_builtin_types or [],
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("", response_model=List[PIIProfileResponse])
async def list_profiles(project_id: Optional[int] = None) -> List[PIIProfileResponse]:
    """
    List PII profiles.

    If `project_id` is provided, returns profiles scoped to that project
    PLUS global profiles (project_id IS NULL). Without a project_id, only
    global profiles are returned.
    """
    async with AsyncSessionLocal() as db:
        query = select(PIIProfile)
        if project_id is not None:
            query = query.where(
                (PIIProfile.project_id == project_id) | (PIIProfile.project_id.is_(None))
            )
        else:
            query = query.where(PIIProfile.project_id.is_(None))
        query = query.order_by(PIIProfile.name)
        result = await db.execute(query)
        profiles = result.scalars().all()
        return [_to_response(p) for p in profiles]


@router.get("/types/available")
async def list_available_types() -> Dict[str, List[str]]:
    """List built-in PII types that profiles can enable/disable."""
    from tools.pii_tool import ALL_PII_TYPES
    return {"builtin_types": sorted(ALL_PII_TYPES)}


@router.get("/{profile_id}", response_model=PIIProfileResponse)
async def get_profile(profile_id: int) -> PIIProfileResponse:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PIIProfile).where(PIIProfile.id == profile_id))
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
        return _to_response(profile)


@router.post("", response_model=PIIProfileResponse)
async def create_profile(payload: PIIProfileCreate) -> PIIProfileResponse:
    async with AsyncSessionLocal() as db:
        profile = PIIProfile(
            name=payload.name,
            description=payload.description,
            project_id=payload.project_id,
            blocklist=payload.blocklist,
            allowlist=payload.allowlist,
            custom_types=[t.model_dump() for t in payload.custom_types],
            enabled_builtin_types=payload.enabled_builtin_types,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return _to_response(profile)


@router.put("/{profile_id}", response_model=PIIProfileResponse)
async def update_profile(profile_id: int, payload: PIIProfileUpdate) -> PIIProfileResponse:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PIIProfile).where(PIIProfile.id == profile_id))
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")

        if payload.name is not None:
            profile.name = payload.name
        if payload.description is not None:
            profile.description = payload.description
        if payload.project_id is not None:
            profile.project_id = payload.project_id
        if payload.blocklist is not None:
            profile.blocklist = payload.blocklist
        if payload.allowlist is not None:
            profile.allowlist = payload.allowlist
        if payload.custom_types is not None:
            profile.custom_types = [t.model_dump() for t in payload.custom_types]
        if payload.enabled_builtin_types is not None:
            profile.enabled_builtin_types = payload.enabled_builtin_types

        await db.commit()
        await db.refresh(profile)
        return _to_response(profile)


@router.delete("/{profile_id}")
async def delete_profile(profile_id: int) -> Dict[str, Any]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PIIProfile).where(PIIProfile.id == profile_id))
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
        await db.delete(profile)
        await db.commit()
        return {"deleted": profile_id}


@router.post("/{profile_id}/test", response_model=PIITestResponse)
async def test_profile(profile_id: int, payload: PIITestRequest) -> PIITestResponse:
    """
    Preview what a profile would redact from sample text.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PIIProfile).where(PIIProfile.id == profile_id))
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")

    # Apply the profile via the pii_tool's profile-aware entrypoint
    from tools.pii_tool import _run_detection_with_profile

    processed, matches = _run_detection_with_profile(
        text=payload.text,
        strategy=payload.strategy,
        profile={
            "blocklist": profile.blocklist or [],
            "allowlist": profile.allowlist or [],
            "custom_types": profile.custom_types or [],
            "enabled_builtin_types": profile.enabled_builtin_types or [],
        },
    )
    types = sorted({m["type"] for m in matches})
    return PIITestResponse(
        redacted_text=processed,
        items_detected=len(matches),
        types_detected=types,
    )
