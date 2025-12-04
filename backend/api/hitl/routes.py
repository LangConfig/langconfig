# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Human-in-the-Loop (HITL) API for Workflow Approval

Provides endpoints for human approval/rejection of workflows paused at APPROVAL_NODEs.
Works with SSE streaming - approval events are published to event bus for real-time updates.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

from db.database import get_db
from models.core import Task, TaskStatus
from models.workflow import WorkflowProfile
from services.event_bus import get_event_bus

router = APIRouter(prefix="/api/hitl", tags=["hitl"])
logger = logging.getLogger(__name__)


# Pydantic Schemas
class HITLApprovalRequest(BaseModel):
    """Request to approve HITL checkpoint"""
    approved: bool
    comment: Optional[str] = None
    context: Optional[dict] = None


class HITLResponse(BaseModel):
    """Response from HITL action"""
    workflow_id: int
    task_id: Optional[int]
    status: str
    message: str
    timestamp: str


@router.post("/{workflow_id}/approve", response_model=HITLResponse)
async def approve_hitl(
    workflow_id: int,
    approval: HITLApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Approve HITL checkpoint and resume workflow execution.

    This endpoint is called by frontend when user clicks "Approve" button
    in HITLApprovalPanel. The approval is published to event bus which
    LangGraph workflow can consume to resume execution.

    Args:
        workflow_id: Workflow ID waiting for approval
        approval: Approval details (approved=True, optional comment)
        db: Database session

    Returns:
        HITLResponse with status and message

    Usage:
        POST /api/hitl/123/approve
        Body: {"approved": true, "comment": "Looks good!"}
    """
    try:
        # Verify workflow exists
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Find associated task (if executing)
        task = db.query(Task).filter(
            Task.workflow_profile_id == workflow_id,
            Task.status == TaskStatus.IN_PROGRESS
        ).order_by(Task.created_at.desc()).first()

        if not approval.approved:
            logger.warning(
                f"HITL approval rejected for workflow {workflow_id}. "
                f"Reason: {approval.comment or 'No reason provided'}"
            )
            raise HTTPException(
                status_code=400,
                detail="Use /reject endpoint to reject HITL"
            )

        # Publish approval event to event bus
        event_bus = get_event_bus()
        await event_bus.publish(f"workflow:{workflow_id}", {
            "type": "hitl_approved",
            "data": {
                "workflow_id": workflow_id,
                "task_id": task.id if task else None,
                "approved": True,
                "comment": approval.comment,
                "context": approval.context,
                "approved_at": datetime.utcnow().isoformat()
            }
        })

        logger.info(
            f"HITL approved for workflow {workflow_id}. "
            f"Comment: {approval.comment or 'None'}"
        )

        # TODO: Integrate with LangGraph interrupt_after/interrupt_before resume
        # For now, just publish event - workflow executor needs to listen for it

        return HITLResponse(
            workflow_id=workflow_id,
            task_id=task.id if task else None,
            status="approved",
            message=f"Workflow {workflow.name} approved and will resume execution",
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITL approval failed for workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/reject", response_model=HITLResponse)
async def reject_hitl(
    workflow_id: int,
    approval: HITLApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Reject HITL checkpoint and terminate workflow execution.

    This endpoint is called by frontend when user clicks "Reject" button
    in HITLApprovalPanel. The rejection is published to event bus and
    workflow execution is terminated.

    Args:
        workflow_id: Workflow ID waiting for approval
        approval: Rejection details (approved=False, required comment)
        db: Database session

    Returns:
        HITLResponse with status and message

    Usage:
        POST /api/hitl/123/reject
        Body: {"approved": false, "comment": "Output looks incorrect"}
    """
    try:
        # Verify workflow exists
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Find associated task (if executing)
        task = db.query(Task).filter(
            Task.workflow_profile_id == workflow_id,
            Task.status == TaskStatus.IN_PROGRESS
        ).order_by(Task.created_at.desc()).first()

        # Require comment for rejection
        if not approval.comment:
            raise HTTPException(
                status_code=400,
                detail="Comment required for rejection"
            )

        # Update task status if found
        if task:
            task.status = TaskStatus.FAILED  # Mark as failed when rejected
            task.error_message = f"Rejected by user: {approval.comment}"
            task.updated_at = datetime.utcnow()
            db.commit()

        # Publish rejection event to event bus
        event_bus = get_event_bus()
        await event_bus.publish(f"workflow:{workflow_id}", {
            "type": "hitl_rejected",
            "data": {
                "workflow_id": workflow_id,
                "task_id": task.id if task else None,
                "approved": False,
                "comment": approval.comment,
                "context": approval.context,
                "rejected_at": datetime.utcnow().isoformat()
            }
        })

        logger.info(
            f"HITL rejected for workflow {workflow_id}. "
            f"Reason: {approval.comment}"
        )

        return HITLResponse(
            workflow_id=workflow_id,
            task_id=task.id if task else None,
            status="rejected",
            message=f"Workflow {workflow.name} rejected and execution terminated",
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITL rejection failed for workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/status")
async def get_hitl_status(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """
    Get HITL status for a workflow.

    Returns whether workflow is waiting for approval, and checkpoint context.

    Args:
        workflow_id: Workflow ID to check
        db: Database session

    Returns:
        Dict with:
        - waiting_for_approval: bool
        - checkpoint_context: dict (if applicable)
        - task_id: int (if executing)
        - workflow_name: str
    """
    try:
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Find associated running task
        task = db.query(Task).filter(
            Task.workflow_profile_id == workflow_id,
            Task.status == TaskStatus.RUNNING
        ).order_by(Task.created_at.desc()).first()

        waiting_for_approval = False
        checkpoint_context = None

        if task and task.configuration:
            # Check if task state indicates AWAITING_APPROVAL
            task_state = task.configuration.get("state", {})
            waiting_for_approval = task_state.get("workflow_status") == "AWAITING_APPROVAL"
            checkpoint_context = task_state.get("approval_context")

        return {
            "workflow_id": workflow_id,
            "workflow_name": workflow.name,
            "task_id": task.id if task else None,
            "waiting_for_approval": waiting_for_approval,
            "checkpoint_context": checkpoint_context,
            "checked_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITL status check failed for workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Tool Execution Approval Endpoints
class ToolApprovalRequest(BaseModel):
    """Request to approve/reject a tool execution"""
    approval_id: str
    approved: bool
    comment: Optional[str] = None


@router.post("/tools/approve", response_model=dict)
async def approve_tool(approval: ToolApprovalRequest):
    """
    Approve or reject a tool execution that requires HITL approval.

    This endpoint is called when a high-risk tool (marked with requires_approval=True
    in action presets) is about to execute and needs human approval.

    Args:
        approval: Tool approval details

    Returns:
        Dict with status and message

    Usage:
        POST /api/hitl/tools/approve
        Body: {"approval_id": "approval_terminal_abc123", "approved": true, "comment": "Safe to run"}
    """
    try:
        from core.tools.execution_wrapper import approve_tool_execution

        # Call the approval function
        success = approve_tool_execution(
            approval_id=approval.approval_id,
            approved=approval.approved,
            comment=approval.comment
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Approval request not found: {approval.approval_id}"
            )

        action = "approved" if approval.approved else "rejected"
        logger.info(f"Tool execution {action}: {approval.approval_id}")

        return {
            "status": "success",
            "approval_id": approval.approval_id,
            "action": action,
            "message": f"Tool execution {action}",
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tool approval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/pending")
async def list_pending_tool_approvals():
    """
    List all pending tool approval requests.

    Returns list of tools waiting for human approval with their context.

    Returns:
        Dict with:
        - pending_approvals: List of approval requests
        - count: Number of pending approvals
    """
    try:
        from core.tools.execution_wrapper import _hitl_approval_events

        pending = []
        for approval_id, event in _hitl_approval_events.items():
            if not event.is_set():
                pending.append({
                    "approval_id": approval_id,
                    "status": "pending"
                })

        return {
            "pending_approvals": pending,
            "count": len(pending),
            "checked_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to list pending tool approvals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
