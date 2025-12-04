# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from db.database import get_db
from models.core import Task, TaskStatus

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# Pydantic Schemas
class TaskResponse(BaseModel):
    id: int
    project_id: int
    description: str
    status: TaskStatus
    assigned_model: str
    workflow_profile_id: Optional[int]
    result: Optional[dict]
    error_message: Optional[str]
    tokens_used: Optional[int]
    configuration: Optional[dict]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    total: int
    tasks: List[TaskResponse]


# Endpoints
@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    skip: int = 0,
    limit: int = 50,
    project_id: Optional[int] = None,
    status: Optional[TaskStatus] = None,
    db: Session = Depends(get_db)
):
    """List tasks with optional filters"""
    query = db.query(Task)

    if project_id:
        query = query.filter(Task.project_id == project_id)
    if status:
        query = query.filter(Task.status == status)

    total = query.count()
    tasks = query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()

    return TaskListResponse(total=total, tasks=tasks)


class ExecutionEventResponse(BaseModel):
    """Execution event response schema"""
    id: int
    task_id: int
    workflow_id: Optional[int]
    event_type: str
    event_data: dict
    timestamp: datetime
    run_id: Optional[str]
    parent_run_id: Optional[str]

    class Config:
        from_attributes = True


@router.get("/{task_id}/events", response_model=List[ExecutionEventResponse])
async def get_task_events(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all execution events for a task.

    Returns chronologically ordered events that capture the agent's thinking,
    tool usage, and execution flow for historical replay and debugging.
    """
    from models.execution_event import ExecutionEvent

    # Verify task exists
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get all events for this task, ordered by timestamp
    events = db.query(ExecutionEvent)\
        .filter(ExecutionEvent.task_id == task_id)\
        .order_by(ExecutionEvent.timestamp)\
        .all()

    return events


@router.get("/{task_id:int}", response_model=TaskResponse)
async def get_task(
    task_id: int = Path(..., ge=1),
    db: Session = Depends(get_db)
):
    """Get a specific task by ID"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/project/{project_id}/recent", response_model=List[TaskResponse])
async def get_recent_project_tasks(
    project_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get recent tasks for a specific project"""
    tasks = (
        db.query(Task)
        .filter(Task.project_id == project_id)
        .order_by(Task.created_at.desc())
        .limit(limit)
        .all()
    )
    return tasks


@router.get("/stats/summary")
async def get_task_stats(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get task statistics summary"""
    query = db.query(Task)
    if project_id:
        query = query.filter(Task.project_id == project_id)

    total = query.count()
    queued = query.filter(Task.status == TaskStatus.QUEUED).count()
    in_progress = query.filter(Task.status == TaskStatus.IN_PROGRESS).count()
    completed = query.filter(Task.status == TaskStatus.COMPLETED).count()
    failed = query.filter(Task.status == TaskStatus.FAILED).count()

    return {
        "total": total,
        "queued": queued,
        "in_progress": in_progress,
        "completed": completed,
        "failed": failed
    }


@router.delete("/{task_id:int}", status_code=204)
async def delete_task(
    task_id: int = Path(..., ge=1),
    db: Session = Depends(get_db)
):
    """Delete a task record"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == TaskStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Cannot delete a task in progress")

    db.delete(task)
    db.commit()
    return None
