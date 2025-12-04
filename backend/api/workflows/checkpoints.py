# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Checkpoint Management API for Workflow Recovery

Provides endpoints for managing LangGraph checkpoints stored in PostgreSQL.
Enables workflow recovery, state inspection, and time-travel debugging.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from db.database import get_db
from models.core import Task
from models.workflow import WorkflowProfile
from services.event_bus import get_event_bus
from core.workflows.executor import get_executor
from core.workflows.checkpointing.utils import CheckpointManager

router = APIRouter(prefix="/api/checkpoints", tags=["checkpoints"])
logger = logging.getLogger(__name__)

# Global checkpoint manager instance
_checkpoint_manager: Optional[CheckpointManager] = None

async def get_checkpoint_manager() -> CheckpointManager:
    """Get or create the global checkpoint manager instance."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
        await _checkpoint_manager.initialize()
    return _checkpoint_manager


# Pydantic Schemas
class CheckpointInfo(BaseModel):
    """Information about a workflow checkpoint"""
    checkpoint_id: str
    workflow_id: int
    task_id: Optional[int]
    thread_id: str
    created_at: str
    step_name: Optional[str]
    message_count: int
    state_summary: Dict[str, Any]


class CheckpointListResponse(BaseModel):
    """List of checkpoints for a workflow"""
    workflow_id: int
    workflow_name: str
    checkpoints: List[CheckpointInfo]
    total: int


class CheckpointRestoreRequest(BaseModel):
    """Request to restore from checkpoint"""
    checkpoint_id: str
    resume_execution: bool = True
    input_override: Optional[Dict[str, Any]] = None


class CheckpointRestoreResponse(BaseModel):
    """Response from checkpoint restore"""
    workflow_id: int
    checkpoint_id: str
    restored_at: str
    new_task_id: Optional[int]
    status: str
    message: str


@router.get("/workflow/{workflow_id}", response_model=CheckpointListResponse)
async def list_checkpoints(
    workflow_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List all checkpoints for a workflow.

    Returns chronologically ordered list of checkpoints from PostgreSQL.
    Each checkpoint represents a saved state during workflow execution.

    Args:
        workflow_id: Workflow ID to get checkpoints for
        limit: Max number of checkpoints to return (default 50)
        db: Database session

    Returns:
        CheckpointListResponse with list of checkpoints

    Usage:
        GET /api/checkpoints/workflow/123?limit=20
    """
    try:
        # Verify workflow exists
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Get checkpoint manager
        manager = await get_checkpoint_manager()

        # Query checkpoints for this workflow
        # Thread ID pattern: workflow_{workflow_id}_task_{task_id}
        thread_id_pattern = f"workflow_{workflow_id}"
        checkpoint_list = await manager.list_checkpoints(
            thread_id=thread_id_pattern,
            limit=limit
        )

        # Convert to CheckpointInfo objects
        checkpoints = []
        for cp in checkpoint_list:
            checkpoints.append(CheckpointInfo(
                checkpoint_id=cp["checkpoint_id"],
                workflow_id=workflow_id,
                task_id=cp.get("task_id"),
                thread_id=cp["checkpoint_id"],  # checkpoint_id contains thread_id
                created_at=cp.get("created_at", datetime.utcnow().isoformat()),
                step_name=cp.get("current_step"),
                message_count=0,  # TODO: Extract from state if needed
                state_summary={
                    "workflow_status": cp.get("workflow_status"),
                    "retry_count": cp.get("retry_count"),
                    "metadata": cp.get("metadata", {})
                }
            ))

        logger.info(f"Found {len(checkpoints)} checkpoints for workflow {workflow_id}")

        return CheckpointListResponse(
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            checkpoints=checkpoints,
            total=len(checkpoints)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list checkpoints for workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{checkpoint_id}", response_model=CheckpointInfo)
async def get_checkpoint(
    checkpoint_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific checkpoint.

    Returns full checkpoint state including messages, metadata, and context.

    Args:
        checkpoint_id: Checkpoint ID to retrieve
        db: Database session

    Returns:
        CheckpointInfo with full checkpoint details

    Usage:
        GET /api/checkpoints/abc123-checkpoint-uuid
    """
    try:
        # Get checkpoint manager
        manager = await get_checkpoint_manager()

        # Get workflow state for this checkpoint
        # checkpoint_id is actually the thread_id in LangGraph
        state = await manager.get_workflow_state(
            thread_id=checkpoint_id,
            checkpoint_id=checkpoint_id
        )

        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint {checkpoint_id} not found"
            )

        # Extract workflow_id from checkpoint_id pattern: workflow_{id}_task_{task_id}
        try:
            workflow_id = int(checkpoint_id.split("_")[1])
        except (IndexError, ValueError):
            workflow_id = 0

        # Build checkpoint info
        checkpoint_info = CheckpointInfo(
            checkpoint_id=checkpoint_id,
            workflow_id=workflow_id,
            task_id=state.get("task_id"),
            thread_id=checkpoint_id,
            created_at=datetime.utcnow().isoformat(),  # TODO: Get from DB
            step_name=state.get("current_step"),
            message_count=len(state.get("messages", [])),
            state_summary={
                "workflow_status": state.get("workflow_status"),
                "retry_count": state.get("retry_count"),
                "error_message": state.get("error_message")
            }
        )

        logger.info(f"Retrieved checkpoint {checkpoint_id}")
        return checkpoint_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get checkpoint {checkpoint_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{checkpoint_id}/restore", response_model=CheckpointRestoreResponse)
async def restore_checkpoint(
    checkpoint_id: str,
    restore_request: CheckpointRestoreRequest,
    db: Session = Depends(get_db)
):
    """
    Restore workflow execution from a checkpoint.

    Loads saved state from PostgreSQL and optionally resumes execution.
    Useful for error recovery, debugging, and what-if analysis.

    Args:
        checkpoint_id: Checkpoint ID to restore from
        restore_request: Restore configuration
        db: Database session

    Returns:
        CheckpointRestoreResponse with new task ID if resumed

    Usage:
        POST /api/checkpoints/abc123/restore
        Body: {"checkpoint_id": "workflow_1_task_2", "resume_execution": true}
    """
    try:
        # Get checkpoint manager
        manager = await get_checkpoint_manager()

        # Load checkpoint state
        state = await manager.get_workflow_state(
            thread_id=checkpoint_id,
            checkpoint_id=restore_request.checkpoint_id
        )

        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint {checkpoint_id} not found"
            )

        # Extract workflow_id from checkpoint_id
        try:
            workflow_id = int(checkpoint_id.split("_")[1])
        except (IndexError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Invalid checkpoint_id format"
            )

        # Publish restoration event
        event_bus = get_event_bus()
        await event_bus.publish("system:checkpoints", {
            "type": "checkpoint_restored",
            "data": {
                "checkpoint_id": checkpoint_id,
                "workflow_id": workflow_id,
                "resume_execution": restore_request.resume_execution,
                "timestamp": datetime.utcnow().isoformat()
            }
        })

        logger.info(f"Checkpoint {checkpoint_id} state loaded successfully")

        # NOTE: Full workflow resumption with LangGraph requires:
        # 1. Compiling graph with same checkpointer
        # 2. Calling graph.invoke() with same thread_id in config
        # 3. LangGraph automatically loads state from checkpoint
        # For now, we just verify the checkpoint exists and can be loaded

        return CheckpointRestoreResponse(
            workflow_id=workflow_id,
            checkpoint_id=checkpoint_id,
            restored_at=datetime.utcnow().isoformat(),
            new_task_id=None,  # Would be set if we resume execution
            status="loaded",
            message=f"Checkpoint state loaded. Full resumption requires workflow execution integration."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore checkpoint {checkpoint_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{checkpoint_id}")
async def delete_checkpoint(
    checkpoint_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a specific checkpoint.

    Removes checkpoint from PostgreSQL storage. Use with caution.

    Args:
        checkpoint_id: Checkpoint ID to delete
        db: Database session

    Returns:
        Success message

    Usage:
        DELETE /api/checkpoints/abc123
    """
    try:
        # Get checkpoint manager
        manager = await get_checkpoint_manager()

        # Delete the checkpoint
        await manager.delete_checkpoint(checkpoint_id)

        logger.info(f"Deleted checkpoint {checkpoint_id}")

        return {
            "message": f"Checkpoint {checkpoint_id} deleted successfully",
            "checkpoint_id": checkpoint_id,
            "deleted_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/{workflow_id}/latest")
async def get_latest_checkpoint(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the most recent checkpoint for a workflow.

    Useful for quick recovery to last known good state.

    Args:
        workflow_id: Workflow ID
        db: Database session

    Returns:
        CheckpointInfo or 404 if no checkpoints exist

    Usage:
        GET /api/checkpoints/workflow/123/latest
    """
    try:
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Get checkpoint manager
        manager = await get_checkpoint_manager()

        # Get latest checkpoint for this workflow
        thread_id_pattern = f"workflow_{workflow_id}"
        checkpoint_list = await manager.list_checkpoints(
            thread_id=thread_id_pattern,
            limit=1
        )

        if not checkpoint_list:
            raise HTTPException(
                status_code=404,
                detail=f"No checkpoints found for workflow {workflow_id}"
            )

        # Convert to CheckpointInfo
        cp = checkpoint_list[0]
        checkpoint_info = CheckpointInfo(
            checkpoint_id=cp["checkpoint_id"],
            workflow_id=workflow_id,
            task_id=cp.get("task_id"),
            thread_id=cp["checkpoint_id"],
            created_at=cp.get("created_at", datetime.utcnow().isoformat()),
            step_name=cp.get("current_step"),
            message_count=0,
            state_summary={
                "workflow_status": cp.get("workflow_status"),
                "retry_count": cp.get("retry_count"),
                "metadata": cp.get("metadata", {})
            }
        )

        logger.info(f"Found latest checkpoint for workflow {workflow_id}: {checkpoint_info.checkpoint_id}")
        return checkpoint_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest checkpoint for workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
