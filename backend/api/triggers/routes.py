# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
API endpoints for workflow triggers.

Provides CRUD operations for workflow triggers (webhooks, file watchers),
trigger history, and manual trigger testing.
"""

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/triggers", tags=["triggers"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class WebhookConfig(BaseModel):
    """Configuration for webhook triggers."""
    require_signature: bool = False
    allowed_ips: List[str] = Field(default_factory=list)
    input_mapping: dict = Field(default_factory=dict)


class FileWatchConfig(BaseModel):
    """Configuration for file watch triggers."""
    watch_path: str
    patterns: List[str] = Field(default_factory=lambda: ["*"])
    recursive: bool = False
    events: List[str] = Field(default_factory=lambda: ["created"])
    debounce_seconds: int = 5
    input_mapping: dict = Field(default_factory=dict)


class TriggerCreate(BaseModel):
    """Request to create a new trigger."""
    workflow_id: int
    trigger_type: str  # "webhook" or "file_watch"
    name: Optional[str] = None
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class TriggerUpdate(BaseModel):
    """Request to update a trigger."""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[dict] = None


class TriggerResponse(BaseModel):
    """Response with trigger details."""
    id: int
    workflow_id: int
    trigger_type: str
    name: Optional[str]
    enabled: bool
    config: dict
    webhook_secret: Optional[str] = None
    webhook_url: Optional[str] = None
    last_triggered_at: Optional[str]
    trigger_count: int
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class TriggerListResponse(BaseModel):
    """Response with list of triggers."""
    triggers: List[TriggerResponse]
    total: int


class TriggerLogResponse(BaseModel):
    """Response with trigger log entry."""
    id: int
    trigger_id: int
    triggered_at: str
    status: str
    trigger_source: Optional[str]
    trigger_payload: Optional[dict]
    task_id: Optional[int]
    error_message: Optional[str]
    completed_at: Optional[str]
    duration: Optional[float]
    created_at: Optional[str]

    class Config:
        from_attributes = True


class TriggerHistoryResponse(BaseModel):
    """Response with trigger history."""
    trigger_id: int
    logs: List[TriggerLogResponse]
    total: int


class TestTriggerRequest(BaseModel):
    """Request to test-fire a trigger."""
    test_payload: dict = Field(default_factory=dict)


class ValidatePathResponse(BaseModel):
    """Response from path validation."""
    valid: bool
    exists: bool
    is_directory: bool
    writable: bool
    error: Optional[str] = None


# =============================================================================
# Trigger CRUD Endpoints
# =============================================================================

@router.post("/", response_model=TriggerResponse)
async def create_trigger(
    trigger: TriggerCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Create a new workflow trigger.

    For webhook triggers, generates a webhook URL and secret.
    For file_watch triggers, validates the watch path.
    """
    from models.workflow_trigger import WorkflowTrigger, TriggerType
    from models.workflow import WorkflowProfile

    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(
        WorkflowProfile.id == trigger.workflow_id
    ).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Validate trigger type
    try:
        trigger_type = TriggerType(trigger.trigger_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger type. Must be one of: {[t.value for t in TriggerType]}"
        )

    # Validate config based on type
    if trigger_type == TriggerType.FILE_WATCH:
        watch_path = trigger.config.get("watch_path")
        if not watch_path:
            raise HTTPException(status_code=400, detail="watch_path is required for file_watch triggers")

    # Create trigger
    db_trigger = WorkflowTrigger(
        workflow_id=trigger.workflow_id,
        trigger_type=trigger.trigger_type,
        name=trigger.name,
        enabled=trigger.enabled,
        config=trigger.config,
    )

    # Generate webhook secret for webhook triggers
    if trigger_type == TriggerType.WEBHOOK:
        db_trigger.webhook_secret = WorkflowTrigger.generate_webhook_secret()

    db.add(db_trigger)
    db.commit()
    db.refresh(db_trigger)

    logger.info(f"Created {trigger.trigger_type} trigger {db_trigger.id} for workflow {trigger.workflow_id}")

    # Start file watcher if enabled
    if trigger_type == TriggerType.FILE_WATCH and trigger.enabled:
        try:
            from services.triggers.file_watcher import get_file_watcher
            watcher = get_file_watcher()
            if watcher._is_running:
                import asyncio
                asyncio.create_task(
                    watcher.start_watcher(db_trigger.id, db_trigger.workflow_id, db_trigger.config)
                )
        except Exception as e:
            logger.warning(f"Could not start file watcher: {e}")

    return _trigger_to_response(db_trigger, request)


@router.get("/workflow/{workflow_id}", response_model=TriggerListResponse)
async def list_workflow_triggers(
    workflow_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """List all triggers for a specific workflow."""
    from models.workflow_trigger import WorkflowTrigger
    from models.workflow import WorkflowProfile

    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(
        WorkflowProfile.id == workflow_id
    ).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    triggers = db.query(WorkflowTrigger).filter(
        WorkflowTrigger.workflow_id == workflow_id
    ).order_by(WorkflowTrigger.created_at.desc()).all()

    return TriggerListResponse(
        triggers=[_trigger_to_response(t, request) for t in triggers],
        total=len(triggers)
    )


@router.get("/{trigger_id}", response_model=TriggerResponse)
async def get_trigger(
    trigger_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get details of a specific trigger."""
    from models.workflow_trigger import WorkflowTrigger

    trigger = db.query(WorkflowTrigger).filter(
        WorkflowTrigger.id == trigger_id
    ).first()

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    return _trigger_to_response(trigger, request)


@router.patch("/{trigger_id}", response_model=TriggerResponse)
async def update_trigger(
    trigger_id: int,
    update: TriggerUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update an existing trigger."""
    from models.workflow_trigger import WorkflowTrigger, TriggerType

    trigger = db.query(WorkflowTrigger).filter(
        WorkflowTrigger.id == trigger_id
    ).first()

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    # Track if enabled state changed
    was_enabled = trigger.enabled
    will_be_enabled = update.enabled if update.enabled is not None else was_enabled

    # Apply updates
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(trigger, key, value)

    db.commit()
    db.refresh(trigger)

    logger.info(f"Updated trigger {trigger_id}")

    # Handle file watcher state changes
    if trigger.trigger_type == TriggerType.FILE_WATCH.value:
        try:
            from services.triggers.file_watcher import get_file_watcher
            watcher = get_file_watcher()

            if watcher._is_running:
                import asyncio
                if was_enabled and not will_be_enabled:
                    # Disable: stop watcher
                    asyncio.create_task(watcher.stop_watcher(trigger_id))
                elif not was_enabled and will_be_enabled:
                    # Enable: start watcher
                    asyncio.create_task(
                        watcher.start_watcher(trigger.id, trigger.workflow_id, trigger.config)
                    )
                elif will_be_enabled and update.config is not None:
                    # Config changed: reload watcher
                    asyncio.create_task(watcher.reload_trigger(trigger_id))
        except Exception as e:
            logger.warning(f"Could not update file watcher: {e}")

    return _trigger_to_response(trigger, request)


@router.delete("/{trigger_id}")
async def delete_trigger(
    trigger_id: int,
    db: Session = Depends(get_db)
):
    """Delete a trigger."""
    from models.workflow_trigger import WorkflowTrigger, TriggerType

    trigger = db.query(WorkflowTrigger).filter(
        WorkflowTrigger.id == trigger_id
    ).first()

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    # Stop file watcher if applicable
    if trigger.trigger_type == TriggerType.FILE_WATCH.value:
        try:
            from services.triggers.file_watcher import get_file_watcher
            watcher = get_file_watcher()
            if watcher._is_running:
                import asyncio
                asyncio.create_task(watcher.stop_watcher(trigger_id))
        except Exception as e:
            logger.warning(f"Could not stop file watcher: {e}")

    db.delete(trigger)
    db.commit()

    logger.info(f"Deleted trigger {trigger_id}")

    return {"status": "success", "message": f"Trigger {trigger_id} deleted"}


# =============================================================================
# Trigger Operations
# =============================================================================

@router.post("/{trigger_id}/test", response_model=dict)
async def test_trigger(
    trigger_id: int,
    test_request: TestTriggerRequest,
    db: Session = Depends(get_db)
):
    """
    Test-fire a trigger with a sample payload.

    Does not require the trigger to be enabled.
    Useful for testing configuration before enabling.
    """
    from models.workflow_trigger import WorkflowTrigger, TriggerLog, TriggerStatus
    from core.task_queue import task_queue, TaskPriority

    trigger = db.query(WorkflowTrigger).filter(
        WorkflowTrigger.id == trigger_id
    ).first()

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    # Create trigger log
    trigger_log = TriggerLog(
        trigger_id=trigger.id,
        triggered_at=datetime.now(timezone.utc),
        status=TriggerStatus.PENDING.value,
        trigger_source="test",
        trigger_payload=test_request.test_payload
    )
    db.add(trigger_log)
    db.flush()

    # Build input data based on trigger type
    input_data = _build_test_input(trigger, test_request.test_payload)

    try:
        task_id = await task_queue.enqueue(
            "execute_triggered_workflow",
            {
                "trigger_id": trigger.id,
                "trigger_log_id": trigger_log.id,
                "workflow_id": trigger.workflow_id,
                "trigger_type": trigger.trigger_type,
                "input_data": input_data,
                "trigger_source": "test",
            },
            priority=TaskPriority.HIGH
        )

        trigger_log.task_id = task_id
        db.commit()

        logger.info(f"Test-fired trigger {trigger_id} (task: {task_id})")

        return {
            "status": "success",
            "message": "Test trigger fired",
            "task_id": task_id,
            "trigger_log_id": trigger_log.id,
            "input_data": input_data
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error test-firing trigger {trigger_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trigger_id}/regenerate-secret", response_model=dict)
async def regenerate_webhook_secret(
    trigger_id: int,
    db: Session = Depends(get_db)
):
    """Regenerate the webhook secret for a webhook trigger."""
    from models.workflow_trigger import WorkflowTrigger, TriggerType

    trigger = db.query(WorkflowTrigger).filter(
        WorkflowTrigger.id == trigger_id
    ).first()

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    if trigger.trigger_type != TriggerType.WEBHOOK.value:
        raise HTTPException(status_code=400, detail="Only webhook triggers have secrets")

    old_secret = trigger.webhook_secret
    trigger.webhook_secret = WorkflowTrigger.generate_webhook_secret()
    db.commit()

    logger.info(f"Regenerated webhook secret for trigger {trigger_id}")

    return {
        "status": "success",
        "message": "Webhook secret regenerated",
        "new_secret": trigger.webhook_secret
    }


@router.get("/{trigger_id}/history", response_model=TriggerHistoryResponse)
async def get_trigger_history(
    trigger_id: int,
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db)
):
    """Get execution history for a trigger."""
    from models.workflow_trigger import WorkflowTrigger, TriggerLog

    trigger = db.query(WorkflowTrigger).filter(
        WorkflowTrigger.id == trigger_id
    ).first()

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    total = db.query(TriggerLog).filter(
        TriggerLog.trigger_id == trigger_id
    ).count()

    logs = db.query(TriggerLog).filter(
        TriggerLog.trigger_id == trigger_id
    ).order_by(TriggerLog.triggered_at.desc()).offset(skip).limit(limit).all()

    return TriggerHistoryResponse(
        trigger_id=trigger_id,
        logs=[_log_to_response(log) for log in logs],
        total=total
    )


# =============================================================================
# File Path Validation
# =============================================================================

@router.post("/validate-path", response_model=ValidatePathResponse)
async def validate_watch_path(path: str):
    """
    Validate a file watch path.

    Checks if the path exists, is a directory, and is writable.
    """
    try:
        exists = os.path.exists(path)
        is_dir = os.path.isdir(path) if exists else False
        writable = os.access(path, os.W_OK) if exists else False

        return ValidatePathResponse(
            valid=exists and is_dir,
            exists=exists,
            is_directory=is_dir,
            writable=writable,
            error=None if (exists and is_dir) else (
                "Path does not exist" if not exists else "Path is not a directory"
            )
        )
    except Exception as e:
        return ValidatePathResponse(
            valid=False,
            exists=False,
            is_directory=False,
            writable=False,
            error=str(e)
        )


# =============================================================================
# Helper Functions
# =============================================================================

def _trigger_to_response(trigger, request: Request = None) -> TriggerResponse:
    """Convert WorkflowTrigger model to response schema."""
    from models.workflow_trigger import TriggerType

    # Build webhook URL if applicable
    webhook_url = None
    if trigger.trigger_type == TriggerType.WEBHOOK.value and request:
        base_url = str(request.base_url).rstrip("/")
        webhook_url = f"{base_url}/api/webhooks/trigger/{trigger.id}"

    return TriggerResponse(
        id=trigger.id,
        workflow_id=trigger.workflow_id,
        trigger_type=trigger.trigger_type,
        name=trigger.name,
        enabled=trigger.enabled,
        config=trigger.config or {},
        webhook_secret=trigger.webhook_secret if trigger.trigger_type == TriggerType.WEBHOOK.value else None,
        webhook_url=webhook_url,
        last_triggered_at=trigger.last_triggered_at.isoformat() if trigger.last_triggered_at else None,
        trigger_count=trigger.trigger_count or 0,
        created_at=trigger.created_at.isoformat() if trigger.created_at else None,
        updated_at=trigger.updated_at.isoformat() if trigger.updated_at else None
    )


def _log_to_response(log) -> TriggerLogResponse:
    """Convert TriggerLog model to response schema."""
    return TriggerLogResponse(
        id=log.id,
        trigger_id=log.trigger_id,
        triggered_at=log.triggered_at.isoformat() if log.triggered_at else None,
        status=log.status,
        trigger_source=log.trigger_source,
        trigger_payload=log.trigger_payload,
        task_id=log.task_id,
        error_message=log.error_message,
        completed_at=log.completed_at.isoformat() if log.completed_at else None,
        duration=log.duration,
        created_at=log.created_at.isoformat() if log.created_at else None
    )


def _build_test_input(trigger, test_payload: dict) -> dict:
    """Build input data for test trigger."""
    from models.workflow_trigger import TriggerType

    config = trigger.config or {}
    input_mapping = config.get("input_mapping", {})

    if trigger.trigger_type == TriggerType.WEBHOOK.value:
        if input_mapping:
            # Use input mapping
            input_data = {}
            for target_key, source_path in input_mapping.items():
                if source_path.startswith("$"):
                    # Extract from payload
                    value = test_payload
                    for part in source_path.lstrip("$.").split("."):
                        value = value.get(part) if isinstance(value, dict) else None
                else:
                    value = source_path
                input_data[target_key] = value
            return input_data
        else:
            return {
                "task": "Process webhook data (test)",
                "context": {"source": "webhook_test", "payload": test_payload}
            }

    elif trigger.trigger_type == TriggerType.FILE_WATCH.value:
        test_file = test_payload.get("file_path", "/test/example.txt")
        return {
            "task": f"Process file: {os.path.basename(test_file)} (test)",
            "context": {
                "source": "file_watch_test",
                "file_path": test_file,
                "file_name": os.path.basename(test_file),
            }
        }

    return {"task": "Test trigger", "context": test_payload}
