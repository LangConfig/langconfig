"""
Model server API for local LLM discovery.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from db.database import get_db
from models.local_model import LocalModel
from services.model_server_discovery import (
    ServerUnreachableError,
    create_model_server,
    delete_model_server,
    discovery_service,
    get_model_servers,
    save_model_servers,
)

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_PROVIDERS = ["ollama", "lmstudio", "vllm", "litellm", "custom"]


class ModelServerCreate(BaseModel):
    name: str = Field(..., description="Human-readable server name")
    base_url: str = Field(..., description="Server base URL, for example http://localhost:11434")
    provider: str = Field(..., description="Provider: ollama, lmstudio, vllm, litellm, custom")
    api_key: Optional[str] = None
    auto_sync: bool = False
    sync_interval_seconds: int = 300

    @validator("name")
    def validate_name(cls, value):
        if not value or not value.strip():
            raise ValueError("Name cannot be empty")
        return value.strip()

    @validator("provider")
    def validate_provider(cls, value):
        value = value.lower()
        if value not in VALID_PROVIDERS:
            raise ValueError(f"Provider must be one of: {', '.join(VALID_PROVIDERS)}")
        return value

    @validator("base_url")
    def validate_base_url(cls, value):
        if not value.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return value.rstrip("/")


class ModelServerResponse(BaseModel):
    id: str
    name: str
    base_url: str
    provider: str
    is_active: bool
    auto_sync: bool
    sync_interval_seconds: int
    model_count: int = 0
    last_sync_error: Optional[str] = None


class DiscoveredModelPreview(BaseModel):
    id: str
    name: str
    size: Optional[int] = None


class DiscoverPreviewResponse(BaseModel):
    success: bool
    message: str
    models: List[DiscoveredModelPreview] = []


class SyncResponse(BaseModel):
    success: bool
    added: int = 0
    updated: int = 0
    removed: int = 0
    errors: List[str] = []


def _server_response(server: dict, db: Session) -> ModelServerResponse:
    server_id = server.get("id", "")
    model_count = db.query(LocalModel).filter(
        LocalModel.server_id == server_id,
        LocalModel.is_active == True,
    ).count()
    return ModelServerResponse(
        id=server_id,
        name=server.get("name", ""),
        base_url=server.get("base_url", ""),
        provider=server.get("provider", "custom"),
        is_active=server.get("is_active", True),
        auto_sync=server.get("auto_sync", False),
        sync_interval_seconds=server.get("sync_interval_seconds", 300),
        model_count=model_count,
        last_sync_error=server.get("last_sync_error"),
    )


@router.get("/", response_model=List[ModelServerResponse])
async def list_model_servers(db: Session = Depends(get_db)):
    return [_server_response(server, db) for server in get_model_servers(db)]


@router.post("/", response_model=ModelServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(server_data: ModelServerCreate, db: Session = Depends(get_db)):
    try:
        server = create_model_server(db, server_data.dict())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # sync_server performs blocking network discovery — run it off the event loop
    sync_result = await asyncio.to_thread(discovery_service.sync_server, server, db)
    if sync_result.errors:
        servers = get_model_servers(db)
        for item in servers:
            if item.get("id") == server["id"]:
                item["last_sync_error"] = "; ".join(sync_result.errors)
                break
        save_model_servers(db, servers)
        server["last_sync_error"] = "; ".join(sync_result.errors)

    logger.info(
        "Created model server %s (added=%s, errors=%s)",
        server["name"],
        sync_result.added,
        len(sync_result.errors),
    )
    return _server_response(server, db)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_server(
    server_id: str,
    hard_delete: bool = False,
    db: Session = Depends(get_db),
):
    if not delete_model_server(db, server_id, hard_delete=hard_delete):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model server with ID {server_id} not found",
        )


@router.post("/{server_id}/sync", response_model=SyncResponse)
async def sync_server(server_id: str, db: Session = Depends(get_db)):
    servers = get_model_servers(db)
    target = next((server for server in servers if server.get("id") == server_id), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model server with ID {server_id} not found",
        )

    # sync_server performs blocking network discovery — run it off the event loop
    result = await asyncio.to_thread(discovery_service.sync_server, target, db)
    for server in servers:
        if server.get("id") == server_id:
            server["last_sync_error"] = "; ".join(result.errors) if result.errors else None
            server["last_sync_at"] = datetime.now(timezone.utc).isoformat()
            break
    save_model_servers(db, servers)

    return SyncResponse(
        success=len(result.errors) == 0,
        added=result.added,
        updated=result.updated,
        removed=result.removed,
        errors=result.errors,
    )


@router.post("/discover", response_model=DiscoverPreviewResponse)
async def discover_preview(
    base_url: str = Query(..., description="Server base URL"),
    provider: str = Query("custom", description="Server provider type"),
    api_key: Optional[str] = Query(None, description="Optional API key"),
):
    provider = provider.lower()
    if provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider must be one of: {', '.join(VALID_PROVIDERS)}",
        )

    try:
        models = await discovery_service.discover_models(base_url, provider, api_key)
        return DiscoverPreviewResponse(
            success=True,
            message=f"Found {len(models)} model(s)",
            models=[
                DiscoveredModelPreview(id=model.id, name=model.name, size=model.size)
                for model in models
            ],
        )
    except ServerUnreachableError as e:
        return DiscoverPreviewResponse(success=False, message=str(e), models=[])
    except Exception as e:
        logger.error("Discovery preview failed: %s", e)
        return DiscoverPreviewResponse(success=False, message=f"Discovery failed: {e}", models=[])
