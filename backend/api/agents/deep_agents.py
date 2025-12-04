# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
API endpoints for DeepAgent configuration and management.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from db.database import get_db
from models.deep_agent import (
    DeepAgentTemplate,
    AgentExport,
    DeepAgentConfig,
    SubAgentConfig,
    MiddlewareConfig,
    BackendConfig,
    GuardrailsConfig
)
from services.export_service import ExportService
from core.versioning import check_version_conflict, format_lock_version_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deepagents", tags=["deepagents"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateDeepAgentRequest(BaseModel):
    """Request to create a new DeepAgent."""
    name: str
    description: Optional[str] = None
    category: str
    config: DeepAgentConfig
    base_template_id: Optional[str] = None


class UpdateDeepAgentRequest(BaseModel):
    """Request to update a DeepAgent."""
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[DeepAgentConfig] = None
    lock_version: Optional[int] = None  # For optimistic locking


class DeepAgentResponse(BaseModel):
    """Response with DeepAgent details."""
    id: int
    name: str
    description: Optional[str]
    category: str
    config: dict
    middleware_config: list
    subagents_config: list
    backend_config: dict
    guardrails_config: dict
    usage_count: int
    version: str  # Semantic version (e.g., "1.0.0")
    lock_version: int  # Optimistic locking version
    is_public: bool
    chat_sessions_count: Optional[int] = 0  # Number of chat sessions for this agent
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ExportRequest(BaseModel):
    """Request to export a DeepAgent."""
    export_type: str  # 'standalone' or 'langconfig'
    include_chat_ui: bool = True
    include_docker: bool = False


class ExportResponse(BaseModel):
    """Response with export details."""
    export_id: int
    export_type: str
    file_path: Optional[str]
    download_url: Optional[str]
    created_at: str
    task_id: Optional[int] = None  # Background task ID
    status: Optional[str] = None  # Export status (pending, in_progress, completed, failed)


# =============================================================================
# CRUD Endpoints
# =============================================================================

@router.post("/", response_model=DeepAgentResponse)
async def create_deepagent(
    request: CreateDeepAgentRequest,
    db: Session = Depends(get_db)
):
    """Create a new DeepAgent template."""
    try:
        agent = DeepAgentTemplate(
            name=request.name,
            description=request.description,
            category=request.category,
            base_template_id=request.base_template_id,
            config=request.config.dict(),
            middleware_config=[m.dict() for m in request.config.middleware],
            subagents_config=[s.dict() for s in request.config.subagents],
            backend_config=request.config.backend.dict(),
            guardrails_config=request.config.guardrails.dict(),
        )

        db.add(agent)
        db.commit()
        db.refresh(agent)

        logger.info(f"Created DeepAgent: {agent.name} (id={agent.id})")

        return DeepAgentResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            category=agent.category,
            config=agent.config,
            middleware_config=agent.middleware_config,
            subagents_config=agent.subagents_config,
            backend_config=agent.backend_config,
            guardrails_config=agent.guardrails_config,
            usage_count=agent.usage_count,
            version=agent.version,
            lock_version=agent.lock_version,
            is_public=agent.is_public,
            created_at=agent.created_at.isoformat(),
            updated_at=agent.updated_at.isoformat()
        )

    except Exception as e:
        logger.error(f"Error creating DeepAgent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[DeepAgentResponse])
async def list_deepagents(
    category: Optional[str] = None,
    public_only: bool = True,
    db: Session = Depends(get_db)
):
    """List all DeepAgent templates."""
    try:
        query = db.query(DeepAgentTemplate)

        if public_only:
            query = query.filter(DeepAgentTemplate.is_public == True)

        if category:
            query = query.filter(DeepAgentTemplate.category == category)

        agents = query.order_by(DeepAgentTemplate.created_at.desc()).all()

        # Get chat session counts for each agent
        from models.deep_agent import ChatSession
        from sqlalchemy import func

        session_counts = {}
        for agent in agents:
            count = db.query(func.count(ChatSession.id)).filter(
                ChatSession.agent_id == agent.id
            ).scalar()
            session_counts[agent.id] = count or 0

        return [
            DeepAgentResponse(
                id=agent.id,
                name=agent.name,
                description=agent.description,
                category=agent.category,
                config=agent.config,
                middleware_config=agent.middleware_config,
                subagents_config=agent.subagents_config,
                backend_config=agent.backend_config,
                guardrails_config=agent.guardrails_config,
                usage_count=agent.usage_count,
                version=agent.version,
                lock_version=agent.lock_version,
                is_public=agent.is_public,
                chat_sessions_count=session_counts.get(agent.id, 0),
                created_at=agent.created_at.isoformat(),
                updated_at=agent.updated_at.isoformat()
            )
            for agent in agents
        ]

    except Exception as e:
        logger.error(f"Error listing DeepAgents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}", response_model=DeepAgentResponse)
async def get_deepagent(
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific DeepAgent by ID."""
    agent = db.query(DeepAgentTemplate).filter(DeepAgentTemplate.id == agent_id).first()

    if not agent:
        raise HTTPException(status_code=404, detail="DeepAgent not found")

    # Get chat session count
    from models.deep_agent import ChatSession
    from sqlalchemy import func

    session_count = db.query(func.count(ChatSession.id)).filter(
        ChatSession.agent_id == agent.id
    ).scalar() or 0

    return DeepAgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        category=agent.category,
        config=agent.config,
        middleware_config=agent.middleware_config,
        subagents_config=agent.subagents_config,
        backend_config=agent.backend_config,
        guardrails_config=agent.guardrails_config,
        usage_count=agent.usage_count,
        version=agent.version,
        lock_version=agent.lock_version,
        is_public=agent.is_public,
        chat_sessions_count=session_count,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat()
    )


@router.put("/{agent_id}", response_model=DeepAgentResponse)
async def update_deepagent(
    agent_id: int,
    request: UpdateDeepAgentRequest,
    db: Session = Depends(get_db)
):
    """Update a DeepAgent template."""
    agent = db.query(DeepAgentTemplate).filter(DeepAgentTemplate.id == agent_id).first()

    if not agent:
        raise HTTPException(status_code=404, detail="DeepAgent not found")

    # Optimistic locking - check lock version conflict
    if request.lock_version is not None:
        if check_version_conflict(agent, request.lock_version):
            error_msg = format_lock_version_error(
                "DeepAgent",
                agent_id,
                request.lock_version,
                agent.lock_version
            )
            raise HTTPException(status_code=409, detail=error_msg)

    # Update fields
    if request.name:
        agent.name = request.name
    if request.description:
        agent.description = request.description
    if request.config:
        agent.config = request.config.dict()
        agent.middleware_config = [m.dict() for m in request.config.middleware]
        agent.subagents_config = [s.dict() for s in request.config.subagents]
        agent.backend_config = request.config.backend.dict()
        agent.guardrails_config = request.config.guardrails.dict()

    db.commit()
    db.refresh(agent)

    logger.info(f"Updated DeepAgent: {agent.name} (id={agent.id})")

    return DeepAgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        category=agent.category,
        config=agent.config,
        middleware_config=agent.middleware_config,
        subagents_config=agent.subagents_config,
        backend_config=agent.backend_config,
        guardrails_config=agent.guardrails_config,
        usage_count=agent.usage_count,
        version=agent.version,
        lock_version=agent.lock_version,
        is_public=agent.is_public,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat()
    )


@router.delete("/{agent_id}")
async def delete_deepagent(
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Delete a DeepAgent template."""
    agent = db.query(DeepAgentTemplate).filter(DeepAgentTemplate.id == agent_id).first()

    if not agent:
        raise HTTPException(status_code=404, detail="DeepAgent not found")

    db.delete(agent)
    db.commit()

    logger.info(f"Deleted DeepAgent: {agent.name} (id={agent_id})")

    return {"status": "success", "message": f"DeepAgent {agent_id} deleted"}


# =============================================================================
# Export Endpoints
# =============================================================================

@router.post("/{agent_id}/export", response_model=ExportResponse)
async def export_deepagent(
    agent_id: int,
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Export a DeepAgent as standalone code or .langconfig format.

    Export now runs in background using task queue.
    - Returns immediately with export_id and task_id
    - Client polls /api/background-tasks/{task_id} for status
    - Export record is updated when task completes
    """
    agent = db.query(DeepAgentTemplate).filter(DeepAgentTemplate.id == agent_id).first()

    if not agent:
        raise HTTPException(status_code=404, detail="DeepAgent not found")

    try:
        # Create export record with pending status
        export = AgentExport(
            agent_id=agent.id,
            export_type=request.export_type,
            export_config={
                "include_chat_ui": request.include_chat_ui,
                "include_docker": request.include_docker
            }
        )
        db.add(export)
        db.commit()
        db.refresh(export)

        # Enqueue export task (non-blocking)
        from core.task_queue import task_queue, TaskPriority

        task_id = await task_queue.enqueue(
            "export_agent",
            {
                "agent_id": agent.id,
                "export_id": export.id,
                "export_type": request.export_type,
                "export_config": {
                    "include_chat_ui": request.include_chat_ui,
                    "include_docker": request.include_docker
                }
            },
            priority=TaskPriority.NORMAL,
            max_retries=2  # Exports can be expensive, limit retries
        )

        logger.info(
            f"Enqueued export task for DeepAgent {agent.name} (export_id: {export.id}, task_id: {task_id})",
            extra={
                "agent_id": agent.id,
                "export_id": export.id,
                "task_id": task_id,
                "export_type": request.export_type
            }
        )

        return ExportResponse(
            export_id=export.id,
            export_type=export.export_type,
            file_path=None,  # Will be set by background task
            download_url=None,  # Will be available after export completes
            created_at=export.created_at.isoformat(),
            task_id=task_id,
            status="pending"
        )

    except Exception as e:
        logger.error(f"Error exporting DeepAgent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: int,
    db: Session = Depends(get_db)
):
    """Download an exported DeepAgent."""
    from fastapi.responses import FileResponse

    export = db.query(AgentExport).filter(AgentExport.id == export_id).first()

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    if not export.file_path or not os.path.exists(export.file_path):
        raise HTTPException(status_code=404, detail="Export file not found")

    # Update download count
    export.download_count += 1
    import datetime
    export.last_downloaded_at = datetime.datetime.utcnow()
    db.commit()

    return FileResponse(
        export.file_path,
        filename=os.path.basename(export.file_path),
        media_type="application/octet-stream"
    )


@router.get("/{agent_id}/exports", response_model=List[ExportResponse])
async def list_exports(
    agent_id: int,
    db: Session = Depends(get_db)
):
    """List all exports for a DeepAgent."""
    exports = db.query(AgentExport).filter(
        AgentExport.agent_id == agent_id
    ).order_by(AgentExport.created_at.desc()).all()

    return [
        ExportResponse(
            export_id=export.id,
            export_type=export.export_type,
            file_path=export.file_path,
            download_url=f"/api/deepagents/exports/{export.id}/download",
            created_at=export.created_at.isoformat()
        )
        for export in exports
    ]


# =============================================================================
# Import Endpoint
# =============================================================================

class ImportRequest(BaseModel):
    """Request to import a .langconfig file."""
    langconfig_content: str


@router.post("/import", response_model=DeepAgentResponse)
async def import_langconfig(
    request: ImportRequest,
    db: Session = Depends(get_db)
):
    """Import a DeepAgent from .langconfig format."""
    try:
        import json
        langconfig = json.loads(request.langconfig_content)

        # Validate format
        if langconfig.get("version") != "1.0" or langconfig.get("export_type") != "deepagent":
            raise HTTPException(status_code=400, detail="Invalid .langconfig format")

        agent_data = langconfig["agent"]

        # Create agent
        config_dict = {
            "model": agent_data["model"],
            "temperature": agent_data["temperature"],
            "max_tokens": agent_data.get("max_tokens"),
            "system_prompt": agent_data["system_prompt"],
            "tools": agent_data.get("tools", []),
            "mcp_tools": agent_data.get("mcp_tools", []),
            "cli_tools": agent_data.get("cli_tools", []),
            "middleware": agent_data.get("middleware", []),
            "subagents": agent_data.get("subagents", []),
            "backend": agent_data.get("backend", {}),
            "guardrails": agent_data.get("guardrails", {})
        }

        config = DeepAgentConfig(**config_dict)

        agent = DeepAgentTemplate(
            name=agent_data["name"],
            description=agent_data.get("description"),
            category=agent_data.get("category", "research"),
            config=config.dict(),
            middleware_config=[m.dict() for m in config.middleware],
            subagents_config=[s.dict() for s in config.subagents],
            backend_config=config.backend.dict(),
            guardrails_config=config.guardrails.dict(),
            is_community=True  # Mark as imported
        )

        db.add(agent)
        db.commit()
        db.refresh(agent)

        logger.info(f"Imported DeepAgent: {agent.name} (id={agent.id})")

        return DeepAgentResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            category=agent.category,
            config=agent.config,
            middleware_config=agent.middleware_config,
            subagents_config=agent.subagents_config,
            backend_config=agent.backend_config,
            guardrails_config=agent.guardrails_config,
            usage_count=agent.usage_count,
            version=agent.version,
            lock_version=agent.lock_version,
            is_public=agent.is_public,
            created_at=agent.created_at.isoformat(),
            updated_at=agent.updated_at.isoformat()
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        logger.error(f"Error importing .langconfig: {e}")
        raise HTTPException(status_code=500, detail=str(e))


import os
