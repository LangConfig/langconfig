# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Skills API - CRUD, discovery, and invocation endpoints.

Provides REST endpoints for managing modular, context-aware skills
that agents can automatically invoke or users can trigger explicitly.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from db.database import get_db
from core.skills.registry import get_skill_registry
from models.skill import Skill, SkillExecution

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


# =============================================================================
# Pydantic Models for Request/Response
# =============================================================================

class SkillResponse(BaseModel):
    """Skill data for API responses."""
    skill_id: str
    name: str
    description: str
    version: str
    source_type: str
    tags: List[str]
    triggers: List[str]
    allowed_tools: Optional[List[str]]
    usage_count: int
    last_used_at: Optional[datetime]
    avg_success_rate: float

    class Config:
        from_attributes = True


class SkillDetailResponse(SkillResponse):
    """Detailed skill with instructions and examples."""
    instructions: str
    examples: Optional[str]
    source_path: str
    author: Optional[str]
    required_context: List[str]
    created_at: datetime
    updated_at: datetime


class SkillMatchRequest(BaseModel):
    """Request to find matching skills."""
    query: str = Field(..., description="User query to match against skills")
    file_path: Optional[str] = Field(None, description="Current file path for context")
    project_type: Optional[str] = Field(None, description="Project type (e.g., python, nodejs)")
    tags: Optional[List[str]] = Field(None, description="Explicit tags to match")
    max_results: int = Field(5, ge=1, le=20, description="Maximum results to return")


class SkillMatchResponse(BaseModel):
    """Skill match result with relevance info."""
    skill: SkillResponse
    score: float
    match_reason: str


class InvokeSkillRequest(BaseModel):
    """Request to explicitly invoke a skill."""
    context: Dict[str, Any] = Field(default_factory=dict, description="Execution context")
    agent_id: Optional[str] = Field(None, description="Agent ID using the skill")
    workflow_id: Optional[int] = Field(None, description="Workflow context")
    task_id: Optional[int] = Field(None, description="Task context")


class InvokeSkillResponse(BaseModel):
    """Response with skill details for invocation."""
    skill_id: str
    name: str
    instructions: str
    allowed_tools: Optional[List[str]]
    examples: Optional[str]
    status: str


class SkillStatsResponse(BaseModel):
    """Usage statistics for a skill."""
    skill_id: str
    usage_count: int
    last_used_at: Optional[datetime]
    avg_success_rate: float
    recent_executions: List[Dict[str, Any]]


# =============================================================================
# Helper Functions
# =============================================================================

def _skill_to_response(skill: Skill) -> SkillResponse:
    """Convert Skill model to SkillResponse."""
    return SkillResponse(
        skill_id=skill.skill_id,
        name=skill.name,
        description=skill.description,
        version=skill.version,
        source_type=skill.source_type.value if hasattr(skill.source_type, 'value') else skill.source_type,
        tags=skill.tags or [],
        triggers=skill.triggers or [],
        allowed_tools=skill.allowed_tools,
        usage_count=skill.usage_count,
        last_used_at=skill.last_used_at,
        avg_success_rate=skill.avg_success_rate
    )


def _skill_to_detail_response(skill: Skill) -> SkillDetailResponse:
    """Convert Skill model to SkillDetailResponse."""
    return SkillDetailResponse(
        skill_id=skill.skill_id,
        name=skill.name,
        description=skill.description,
        version=skill.version,
        source_type=skill.source_type.value if hasattr(skill.source_type, 'value') else skill.source_type,
        tags=skill.tags or [],
        triggers=skill.triggers or [],
        allowed_tools=skill.allowed_tools,
        usage_count=skill.usage_count,
        last_used_at=skill.last_used_at,
        avg_success_rate=skill.avg_success_rate,
        instructions=skill.instructions,
        examples=skill.examples,
        source_path=skill.source_path,
        author=skill.author,
        required_context=skill.required_context or [],
        created_at=skill.created_at,
        updated_at=skill.updated_at
    )


# =============================================================================
# Skill Endpoints
# =============================================================================

@router.get("", response_model=List[SkillResponse])
async def list_skills(
    source_type: Optional[str] = Query(None, description="Filter by source: builtin, personal, project"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search by name/description")
):
    """
    List all available skills with optional filtering.

    Query parameters:
    - source_type: Filter by builtin, personal, or project
    - tag: Filter by a specific tag
    - search: Text search across names and descriptions
    """
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    # Apply filters
    if tag:
        skills = registry.find_by_tags([tag])
    elif source_type:
        skills = registry.find_by_source(source_type)
    elif search:
        skills = registry.search(search)
    else:
        skills = registry.list_all()

    return [_skill_to_response(s) for s in skills]


@router.get("/summary")
async def get_skills_summary():
    """
    Get a summary of available skills.

    Returns counts by source type and tag statistics.
    """
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    skills = registry.list_all()

    # Count by source type
    by_source = {}
    tag_counts = {}

    for skill in skills:
        source = skill.source_type.value if hasattr(skill.source_type, 'value') else skill.source_type
        by_source[source] = by_source.get(source, 0) + 1

        for tag in (skill.tags or []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Sort tags by count
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "total_skills": len(skills),
        "by_source": by_source,
        "top_tags": dict(top_tags)
    }


@router.get("/{skill_id}", response_model=SkillDetailResponse)
async def get_skill(skill_id: str):
    """Get detailed information for a specific skill."""
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    skill = registry.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    return _skill_to_detail_response(skill)


class SkillCreateRequest(BaseModel):
    """Request to create a new skill."""
    name: str = Field(..., description="Skill name")
    description: str = Field(..., description="Brief description of the skill")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    triggers: List[str] = Field(default_factory=list, description="Auto-trigger conditions")
    instructions: str = Field("", description="Detailed instructions for the skill")


class SkillUpdateRequest(BaseModel):
    """Request to update a skill."""
    name: Optional[str] = Field(None, description="Updated skill name")
    description: Optional[str] = Field(None, description="Updated description")
    triggers: Optional[List[str]] = Field(None, description="Updated trigger conditions")
    instructions: Optional[str] = Field(None, description="Updated instructions")


@router.post("", response_model=SkillDetailResponse)
async def create_skill(request: SkillCreateRequest):
    """
    Create a new personal skill.

    Creates a skill that is stored in the database (not filesystem).
    """
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    # Generate skill_id from name
    skill_id = request.name.lower().replace(" ", "-").replace("_", "-")

    # Check if skill already exists
    if registry.get_skill(skill_id):
        raise HTTPException(status_code=409, detail=f"Skill '{skill_id}' already exists")

    try:
        skill = await registry.create_skill(
            skill_id=skill_id,
            name=request.name,
            description=request.description,
            tags=request.tags,
            triggers=request.triggers,
            instructions=request.instructions
        )
        return _skill_to_detail_response(skill)
    except Exception as e:
        logger.error(f"Failed to create skill: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create skill: {str(e)}")


@router.put("/{skill_id}", response_model=SkillDetailResponse)
async def update_skill(skill_id: str, request: SkillUpdateRequest):
    """
    Update a skill's properties.

    Only updates fields that are provided in the request.
    """
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    skill = registry.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    # Update fields if provided
    if request.name is not None:
        skill.name = request.name
    if request.description is not None:
        skill.description = request.description
    if request.triggers is not None:
        skill.triggers = request.triggers
    if request.instructions is not None:
        skill.instructions = request.instructions

    skill.updated_at = datetime.utcnow()

    # Persist to database
    try:
        await registry.update_skill(skill)
    except Exception as e:
        logger.error(f"Failed to update skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update skill: {str(e)}")

    return _skill_to_detail_response(skill)


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    """
    Delete a skill.

    Only personal/custom skills can be deleted.
    Builtin skills cannot be deleted.
    """
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    skill = registry.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    # Prevent deletion of builtin skills
    if skill.source_type == SkillSourceType.BUILTIN:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete builtin skills"
        )

    try:
        await registry.delete_skill(skill_id)
        return {"status": "deleted", "skill_id": skill_id}
    except Exception as e:
        logger.error(f"Failed to delete skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete skill: {str(e)}")


@router.post("/match", response_model=List[SkillMatchResponse])
async def match_skills(request: SkillMatchRequest):
    """
    Find skills matching the given context.

    Uses multiple matching strategies:
    1. Semantic matching against descriptions
    2. Trigger condition evaluation
    3. Tag matching

    Returns skills ranked by relevance score.
    """
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    # For now, use simple tag + text matching
    # Full semantic matching will be in SkillMatcher
    results = []

    skills = registry.list_all()
    query_lower = request.query.lower()

    for skill in skills:
        score = 0.0
        match_reason = []

        # Text matching
        if query_lower in skill.description.lower():
            score += 0.5
            match_reason.append("description match")
        if query_lower in skill.name.lower():
            score += 0.3
            match_reason.append("name match")

        # Tag matching
        if request.tags:
            skill_tags_lower = [t.lower() for t in (skill.tags or [])]
            matching_tags = set(t.lower() for t in request.tags) & set(skill_tags_lower)
            if matching_tags:
                score += 0.3 * len(matching_tags)
                match_reason.append(f"tags: {', '.join(matching_tags)}")

        # Trigger matching (basic keyword check)
        for trigger in (skill.triggers or []):
            trigger_lower = trigger.lower()
            if "mentions" in trigger_lower:
                keywords = trigger_lower.split("mentions")[-1].strip()
                if keywords in query_lower:
                    score += 0.6
                    match_reason.append(f"trigger: {trigger}")
                    break

        if score > 0:
            results.append(SkillMatchResponse(
                skill=_skill_to_response(skill),
                score=min(score, 1.0),
                match_reason="; ".join(match_reason) if match_reason else "partial match"
            ))

    # Sort by score and limit results
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:request.max_results]


@router.post("/{skill_id}/invoke", response_model=InvokeSkillResponse)
async def invoke_skill(skill_id: str, request: InvokeSkillRequest):
    """
    Explicitly invoke a skill.

    Returns the skill's instructions and configuration for use by an agent.
    Records the invocation for analytics.
    """
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    skill = registry.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    # Record invocation start
    await registry.record_execution(
        skill_id=skill_id,
        invocation_type="explicit",
        status="started",
        context=request.context,
        agent_id=request.agent_id,
        workflow_id=request.workflow_id,
        task_id=request.task_id
    )

    return InvokeSkillResponse(
        skill_id=skill.skill_id,
        name=skill.name,
        instructions=skill.instructions,
        allowed_tools=skill.allowed_tools,
        examples=skill.examples,
        status="ready"
    )


@router.post("/{skill_id}/reload")
async def reload_skill(skill_id: str):
    """
    Reload a skill from filesystem.

    Use this after modifying a SKILL.md file to pick up changes.
    """
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    if not registry.get_skill(skill_id):
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    success = await registry.reload_skill(skill_id)

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to reload skill '{skill_id}'")

    return {"status": "reloaded", "skill_id": skill_id}


@router.post("/reload-all")
async def reload_all_skills(project_paths: Optional[List[str]] = None):
    """
    Reload all skills from filesystem.

    Scans all skill directories and updates the registry.
    """
    registry = get_skill_registry()
    count = await registry.reload_all(project_paths)

    return {"status": "reloaded", "skill_count": count}


@router.get("/debug/paths")
async def debug_skill_paths():
    """Debug endpoint to check skill loader paths."""
    import os
    from core.skills.loader import SkillLoader

    loader = SkillLoader()

    # Check paths
    builtin_exists = os.path.exists(loader.builtin_path)
    personal_exists = os.path.exists(loader.personal_path)

    # Try to discover
    discovered = loader.discover_all()

    # Try to load each
    loaded = []
    for d in discovered:
        skill = loader.load_skill(d.skill_path)
        loaded.append({
            "path": d.skill_path,
            "source_type": d.source_type,
            "loaded": skill is not None,
            "skill_id": skill.skill_id if skill else None,
            "error": None if skill else "Failed to parse"
        })

    return {
        "builtin_path": loader.builtin_path,
        "builtin_exists": builtin_exists,
        "personal_path": loader.personal_path,
        "personal_exists": personal_exists,
        "discovered_count": len(discovered),
        "loaded_skills": loaded
    }


@router.get("/debug/registry-state")
async def debug_registry_state():
    """Debug endpoint to check registry state."""
    registry = get_skill_registry()
    return {
        "is_initialized": registry.is_initialized,
        "skill_count": registry.skill_count,
        "skills_in_memory": list(registry._skills.keys()),
        "tags_indexed": list(registry._by_tag.keys())
    }


@router.post("/debug/init")
async def debug_init():
    """Debug endpoint to force registry initialization."""
    import traceback
    registry = get_skill_registry()

    try:
        count = await registry.initialize()
        return {
            "status": "success",
            "skill_count": count,
            "is_initialized": registry.is_initialized,
            "skills_in_memory": list(registry._skills.keys())
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@router.post("/debug/reload-verbose")
async def debug_reload_verbose():
    """Debug endpoint to reload skills with verbose error output."""
    import os
    import traceback
    from core.skills.loader import SkillLoader
    from db.database import AsyncSessionLocal
    from models.skill import Skill, SkillSourceType
    from sqlalchemy import select
    from datetime import datetime

    loader = SkillLoader()
    discovered = loader.discover_all()
    results = []

    async with AsyncSessionLocal() as session:
        for d in discovered:
            result = {"path": d.skill_path, "source_type": d.source_type}
            try:
                parsed = loader.load_skill(d.skill_path)
                if not parsed:
                    result["status"] = "parse_failed"
                    results.append(result)
                    continue

                result["skill_id"] = parsed.skill_id

                # Try to check if exists
                db_result = await session.execute(
                    select(Skill).where(Skill.skill_id == parsed.skill_id)
                )
                existing = db_result.scalar_one_or_none()

                if existing:
                    result["status"] = "exists_in_db"
                    result["db_id"] = existing.id
                else:
                    # Try to create
                    skill = Skill(
                        skill_id=parsed.skill_id,
                        name=parsed.name,
                        description=parsed.description,
                        version=parsed.version,
                        author=parsed.author,
                        source_type=SkillSourceType(d.source_type),
                        source_path=parsed.source_path,
                        tags=parsed.tags,
                        triggers=parsed.triggers,
                        allowed_tools=parsed.allowed_tools,
                        required_context=parsed.required_context,
                        instructions=parsed.instructions,
                        examples=parsed.examples,
                        file_modified_at=parsed.file_modified_at
                    )
                    session.add(skill)
                    result["status"] = "created"

            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
                result["traceback"] = traceback.format_exc()

            results.append(result)

        try:
            await session.commit()
        except Exception as e:
            return {
                "commit_error": str(e),
                "commit_traceback": traceback.format_exc(),
                "results": results
            }

    return {"results": results}


@router.get("/{skill_id}/stats", response_model=SkillStatsResponse)
async def get_skill_stats(skill_id: str, db: Session = Depends(get_db)):
    """Get usage statistics for a skill."""
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    skill = registry.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    # Get recent executions from database
    recent = db.query(SkillExecution).filter(
        SkillExecution.skill_id == skill.id
    ).order_by(
        SkillExecution.created_at.desc()
    ).limit(10).all()

    recent_executions = [
        {
            "id": ex.id,
            "invocation_type": ex.invocation_type.value if hasattr(ex.invocation_type, 'value') else ex.invocation_type,
            "status": ex.status,
            "execution_time_ms": ex.execution_time_ms,
            "created_at": ex.created_at.isoformat() if ex.created_at else None
        }
        for ex in recent
    ]

    return SkillStatsResponse(
        skill_id=skill_id,
        usage_count=skill.usage_count,
        last_used_at=skill.last_used_at,
        avg_success_rate=skill.avg_success_rate,
        recent_executions=recent_executions
    )


@router.post("/{skill_id}/record-execution")
async def record_skill_execution(
    skill_id: str,
    status: str = Query(..., description="Execution status: success, failed, partial"),
    execution_time_ms: Optional[int] = Query(None, description="Execution time in milliseconds"),
    error_message: Optional[str] = Query(None, description="Error message if failed"),
    invocation_type: str = Query("explicit", description="How skill was invoked: automatic, explicit")
):
    """
    Record a skill execution result.

    Call this after a skill has finished executing to track metrics.
    """
    registry = get_skill_registry()

    if not registry.is_initialized:
        await registry.initialize()

    if not registry.get_skill(skill_id):
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    await registry.record_execution(
        skill_id=skill_id,
        invocation_type=invocation_type,
        status=status,
        execution_time_ms=execution_time_ms,
        error_message=error_message
    )

    return {"status": "recorded", "skill_id": skill_id}
