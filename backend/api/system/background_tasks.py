# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Background Tasks API

API endpoints for managing and monitoring background tasks.

Endpoints:
- GET /api/background-tasks/{task_id} - Get task status
- GET /api/background-tasks - List tasks with filters
- POST /api/background-tasks/{task_id}/cancel - Cancel pending task
- POST /api/background-tasks/{task_id}/retry - Retry failed task
- GET /api/background-tasks/stats - Get queue statistics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from db.database import get_db
from models.background_task import BackgroundTask
from core.task_queue import task_queue

router = APIRouter(prefix="/api/background-tasks", tags=["background-tasks"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class BackgroundTaskResponse(BaseModel):
    """Response schema for background task."""
    id: int
    task_type: str
    payload: dict
    priority: int
    status: str
    result: Optional[dict]
    error: Optional[str]
    retry_count: int
    max_retries: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration: Optional[float]
    wait_time: Optional[float]

    class Config:
        from_attributes = True


class BackgroundTaskListResponse(BaseModel):
    """Response schema for task list."""
    total: int
    tasks: List[BackgroundTaskResponse]


class QueueStatsResponse(BaseModel):
    """Response schema for queue statistics."""
    pending: int
    running: int
    completed: int
    failed: int
    cancelled: int
    workers: int
    workers_running: bool


class TaskCancelResponse(BaseModel):
    """Response schema for task cancellation."""
    success: bool
    task_id: int
    message: str


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/{task_id}", response_model=BackgroundTaskResponse)
async def get_task_status(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    Get status of a background task.

    Returns detailed information about task execution including:
    - Current status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
    - Result data (if completed)
    - Error message (if failed)
    - Timing information (duration, wait_time)
    - Retry information

    Args:
        task_id: ID of the task to check

    Returns:
        BackgroundTaskResponse with task details

    Raises:
        HTTPException 404: Task not found
    """
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return task


@router.get("/", response_model=BackgroundTaskListResponse)
async def list_tasks(
    skip: int = Query(0, ge=0, description="Number of tasks to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum tasks to return"),
    status: Optional[str] = Query(None, description="Filter by status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    db: Session = Depends(get_db)
):
    """
    List background tasks with optional filters.

    Supports filtering by:
    - status: Task status (PENDING, RUNNING, etc.)
    - task_type: Type of task (export_workflow_agent, etc.)

    Tasks are returned in reverse chronological order (newest first).

    Args:
        skip: Number of tasks to skip (for pagination)
        limit: Maximum tasks to return (1-100)
        status: Optional status filter
        task_type: Optional task type filter

    Returns:
        BackgroundTaskListResponse with tasks and total count
    """
    query = db.query(BackgroundTask)

    # Apply filters
    if status:
        query = query.filter(BackgroundTask.status == status.upper())
    if task_type:
        query = query.filter(BackgroundTask.task_type == task_type)

    # Get total count
    total = query.count()

    # Get tasks with pagination
    tasks = query.order_by(
        BackgroundTask.created_at.desc()
    ).offset(skip).limit(limit).all()

    return BackgroundTaskListResponse(
        total=total,
        tasks=tasks
    )


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse)
async def cancel_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    Cancel a pending background task.

    Only tasks in PENDING status can be cancelled. Tasks that are already
    running cannot be stopped.

    Args:
        task_id: ID of the task to cancel

    Returns:
        TaskCancelResponse with success status

    Raises:
        HTTPException 404: Task not found
        HTTPException 400: Task cannot be cancelled (already running or completed)
    """
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task with status {task.status}. Only PENDING tasks can be cancelled."
        )

    # Cancel the task
    success = await task_queue.cancel_task(task_id)

    if success:
        return TaskCancelResponse(
            success=True,
            task_id=task_id,
            message=f"Task {task_id} cancelled successfully"
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel task {task_id}"
        )


@router.post("/{task_id}/retry", response_model=BackgroundTaskResponse)
async def retry_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    Retry a failed background task.

    Resets a FAILED task back to PENDING status so workers will pick it up again.
    The retry count is incremented.

    Args:
        task_id: ID of the task to retry

    Returns:
        BackgroundTaskResponse with updated task details

    Raises:
        HTTPException 404: Task not found
        HTTPException 400: Task is not in FAILED status
        HTTPException 400: Task has exceeded max retries
    """
    task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status != "FAILED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry task with status {task.status}. Only FAILED tasks can be retried."
        )

    if task.retry_count >= task.max_retries:
        raise HTTPException(
            status_code=400,
            detail=f"Task has already been retried {task.retry_count} times (max: {task.max_retries})"
        )

    # Reset task to PENDING for retry
    task.status = "PENDING"
    task.started_at = None
    task.completed_at = None
    task.result = None
    # Keep error message for debugging
    # retry_count will be incremented by worker when it picks up the task

    db.commit()
    db.refresh(task)

    return task


@router.get("/stats", response_model=QueueStatsResponse)
async def get_queue_stats():
    """
    Get background task queue statistics.

    Returns current queue metrics including:
    - Number of tasks in each status
    - Number of active workers
    - Worker running status

    Useful for monitoring queue health and worker activity.

    Returns:
        QueueStatsResponse with queue metrics
    """
    stats = await task_queue.get_queue_stats()
    return QueueStatsResponse(**stats)


# =============================================================================
# Exports
# =============================================================================

__all__ = ["router"]
