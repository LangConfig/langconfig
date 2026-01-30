# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
API endpoints for workflow scheduling.

Provides CRUD operations for workflow schedules, execution history,
cron expression validation, and manual triggering.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from db.database import get_db

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/schedules", tags=["schedules"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class ScheduleCreate(BaseModel):
    """Request to create a new schedule."""
    workflow_id: int
    name: Optional[str] = None
    cron_expression: str = Field(..., description="Standard cron expression (e.g., '0 9 * * *')")
    timezone: str = "UTC"
    enabled: bool = True
    default_input_data: dict = Field(default_factory=dict)
    max_concurrent_runs: int = 1
    timeout_minutes: int = 60
    idempotency_key_template: Optional[str] = None


class ScheduleUpdate(BaseModel):
    """Request to update a schedule."""
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None
    default_input_data: Optional[dict] = None
    max_concurrent_runs: Optional[int] = None
    timeout_minutes: Optional[int] = None
    idempotency_key_template: Optional[str] = None


class ScheduleResponse(BaseModel):
    """Response with schedule details."""
    id: int
    workflow_id: int
    name: Optional[str]
    cron_expression: str
    timezone: str
    enabled: bool
    default_input_data: dict
    max_concurrent_runs: int
    timeout_minutes: int
    idempotency_key_template: Optional[str]
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    last_run_status: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class ScheduleListResponse(BaseModel):
    """Response with list of schedules."""
    schedules: List[ScheduleResponse]
    total: int


class RunLogResponse(BaseModel):
    """Response with execution log entry."""
    id: int
    schedule_id: int
    scheduled_for: str
    started_at: Optional[str]
    completed_at: Optional[str]
    status: str
    task_id: Optional[int]
    error_message: Optional[str]
    idempotency_key: Optional[str]
    duration: Optional[float]
    created_at: Optional[str]

    class Config:
        from_attributes = True


class RunHistoryResponse(BaseModel):
    """Response with execution history."""
    schedule_id: int
    runs: List[RunLogResponse]
    total: int


class CronValidationRequest(BaseModel):
    """Request to validate a cron expression."""
    cron_expression: str
    timezone: str = "UTC"


class CronValidationResponse(BaseModel):
    """Response with cron validation result."""
    valid: bool
    error: Optional[str] = None
    next_runs: List[str] = []
    human_readable: Optional[str] = None


class TriggerResponse(BaseModel):
    """Response from manual trigger."""
    success: bool
    message: str
    task_id: Optional[int] = None
    run_log_id: Optional[int] = None


# =============================================================================
# Schedule CRUD Endpoints
# =============================================================================

@router.post("/", response_model=ScheduleResponse)
async def create_schedule(
    schedule: ScheduleCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new workflow schedule.

    Validates the cron expression and calculates the initial next_run_at.
    """
    from models.workflow_schedule import WorkflowSchedule
    from models.workflow import WorkflowProfile

    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(
        WorkflowProfile.id == schedule.workflow_id
    ).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Validate cron expression
    validation = validate_cron_internal(schedule.cron_expression, schedule.timezone)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cron expression: {validation['error']}"
        )

    # Create schedule
    db_schedule = WorkflowSchedule(
        workflow_id=schedule.workflow_id,
        name=schedule.name,
        cron_expression=schedule.cron_expression,
        timezone=schedule.timezone,
        enabled=schedule.enabled,
        default_input_data=schedule.default_input_data,
        max_concurrent_runs=schedule.max_concurrent_runs,
        timeout_minutes=schedule.timeout_minutes,
        idempotency_key_template=schedule.idempotency_key_template,
        next_run_at=datetime.fromisoformat(validation["next_runs"][0].replace("Z", "+00:00"))
        if validation["next_runs"] else None
    )

    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)

    logger.info(f"Created schedule {db_schedule.id} for workflow {schedule.workflow_id}")

    return _schedule_to_response(db_schedule)


@router.get("/workflow/{workflow_id}", response_model=ScheduleListResponse)
async def list_workflow_schedules(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """
    List all schedules for a specific workflow.
    """
    from models.workflow_schedule import WorkflowSchedule
    from models.workflow import WorkflowProfile

    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(
        WorkflowProfile.id == workflow_id
    ).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    schedules = db.query(WorkflowSchedule).filter(
        WorkflowSchedule.workflow_id == workflow_id
    ).order_by(WorkflowSchedule.created_at.desc()).all()

    return ScheduleListResponse(
        schedules=[_schedule_to_response(s) for s in schedules],
        total=len(schedules)
    )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db)
):
    """
    Get details of a specific schedule.
    """
    from models.workflow_schedule import WorkflowSchedule

    schedule = db.query(WorkflowSchedule).filter(
        WorkflowSchedule.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return _schedule_to_response(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    update: ScheduleUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing schedule.

    If cron_expression or timezone is updated, recalculates next_run_at.
    """
    from models.workflow_schedule import WorkflowSchedule

    schedule = db.query(WorkflowSchedule).filter(
        WorkflowSchedule.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Validate new cron expression if provided
    if update.cron_expression is not None or update.timezone is not None:
        cron = update.cron_expression or schedule.cron_expression
        tz = update.timezone or schedule.timezone

        validation = validate_cron_internal(cron, tz)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cron expression: {validation['error']}"
            )

        # Update next_run_at
        if validation["next_runs"]:
            schedule.next_run_at = datetime.fromisoformat(
                validation["next_runs"][0].replace("Z", "+00:00")
            )

    # Apply updates
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(schedule, key, value)

    db.commit()
    db.refresh(schedule)

    logger.info(f"Updated schedule {schedule_id}")

    return _schedule_to_response(schedule)


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a schedule.

    Also deletes all associated run logs.
    """
    from models.workflow_schedule import WorkflowSchedule

    schedule = db.query(WorkflowSchedule).filter(
        WorkflowSchedule.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    db.delete(schedule)
    db.commit()

    logger.info(f"Deleted schedule {schedule_id}")

    return {"status": "success", "message": f"Schedule {schedule_id} deleted"}


# =============================================================================
# Execution Endpoints
# =============================================================================

@router.post("/{schedule_id}/trigger", response_model=TriggerResponse)
async def trigger_schedule(
    schedule_id: int,
    db: Session = Depends(get_db)
):
    """
    Manually trigger a scheduled workflow execution.

    Bypasses the cron schedule and runs immediately.
    Does not update next_run_at.
    """
    from models.workflow_schedule import WorkflowSchedule, ScheduledRunLog, ScheduleRunStatus
    from core.task_queue import task_queue, TaskPriority

    schedule = db.query(WorkflowSchedule).filter(
        WorkflowSchedule.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not schedule.enabled:
        raise HTTPException(
            status_code=400,
            detail="Cannot trigger disabled schedule"
        )

    # Create run log entry
    run_log = ScheduledRunLog(
        schedule_id=schedule.id,
        scheduled_for=datetime.now(timezone.utc),
        status=ScheduleRunStatus.PENDING.value,
        idempotency_key=f"manual_trigger_{schedule.id}_{datetime.now(timezone.utc).isoformat()}"
    )
    db.add(run_log)
    db.flush()

    try:
        # Enqueue the task
        task_id = await task_queue.enqueue(
            "execute_scheduled_workflow",
            {
                "schedule_id": schedule.id,
                "run_log_id": run_log.id,
                "workflow_id": schedule.workflow_id,
                "input_data": schedule.default_input_data,
                "timeout_minutes": schedule.timeout_minutes
            },
            priority=TaskPriority.HIGH  # Manual triggers get higher priority
        )

        # Update run log with task ID
        run_log.task_id = task_id
        db.commit()

        logger.info(f"Manually triggered schedule {schedule_id}, task {task_id}")

        return TriggerResponse(
            success=True,
            message=f"Workflow execution triggered",
            task_id=task_id,
            run_log_id=run_log.id
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to trigger schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{schedule_id}/history", response_model=RunHistoryResponse)
async def get_schedule_history(
    schedule_id: int,
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get execution history for a schedule.

    Returns run logs ordered by scheduled_for descending.
    """
    from models.workflow_schedule import WorkflowSchedule, ScheduledRunLog

    schedule = db.query(WorkflowSchedule).filter(
        WorkflowSchedule.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    total = db.query(ScheduledRunLog).filter(
        ScheduledRunLog.schedule_id == schedule_id
    ).count()

    runs = db.query(ScheduledRunLog).filter(
        ScheduledRunLog.schedule_id == schedule_id
    ).order_by(ScheduledRunLog.scheduled_for.desc()).offset(skip).limit(limit).all()

    return RunHistoryResponse(
        schedule_id=schedule_id,
        runs=[_run_log_to_response(r) for r in runs],
        total=total
    )


# =============================================================================
# Cron Validation
# =============================================================================

@router.post("/validate-cron", response_model=CronValidationResponse)
async def validate_cron_expression(
    request: CronValidationRequest
):
    """
    Validate a cron expression and preview next run times.

    Returns:
    - valid: Whether the expression is valid
    - error: Error message if invalid
    - next_runs: List of next 5 scheduled run times (ISO format)
    - human_readable: Human-readable description of the schedule
    """
    result = validate_cron_internal(request.cron_expression, request.timezone)
    return CronValidationResponse(**result)


# =============================================================================
# Helper Functions
# =============================================================================

def validate_cron_internal(cron_expression: str, tz: str = "UTC") -> dict:
    """
    Internal cron validation function.

    Returns dict with:
    - valid: bool
    - error: Optional[str]
    - next_runs: List[str] - ISO format datetimes
    - human_readable: Optional[str]
    """
    try:
        from croniter import croniter
        import pytz

        # Validate timezone
        try:
            timezone_obj = pytz.timezone(tz)
        except pytz.exceptions.UnknownTimeZoneError:
            return {
                "valid": False,
                "error": f"Unknown timezone: {tz}",
                "next_runs": [],
                "human_readable": None
            }

        # Validate cron expression
        now = datetime.now(timezone_obj)
        try:
            cron = croniter(cron_expression, now)
        except (KeyError, ValueError) as e:
            return {
                "valid": False,
                "error": f"Invalid cron expression: {str(e)}",
                "next_runs": [],
                "human_readable": None
            }

        # Calculate next 5 runs
        next_runs = []
        for _ in range(5):
            next_run = cron.get_next(datetime)
            if next_run.tzinfo is None:
                next_run = timezone_obj.localize(next_run)
            next_runs.append(next_run.astimezone(pytz.UTC).isoformat())

        # Try to generate human-readable description
        human_readable = _cron_to_human(cron_expression)

        return {
            "valid": True,
            "error": None,
            "next_runs": next_runs,
            "human_readable": human_readable
        }

    except ImportError:
        return {
            "valid": False,
            "error": "croniter package not installed",
            "next_runs": [],
            "human_readable": None
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "next_runs": [],
            "human_readable": None
        }


def _cron_to_human(cron_expression: str) -> str:
    """
    Convert cron expression to human-readable description.

    Basic implementation - handles common patterns.
    """
    parts = cron_expression.split()
    if len(parts) != 5:
        return cron_expression

    minute, hour, dom, month, dow = parts

    # Common patterns
    if cron_expression == "* * * * *":
        return "Every minute"
    if cron_expression == "0 * * * *":
        return "Every hour"
    if cron_expression == "0 0 * * *":
        return "Every day at midnight"
    if cron_expression == "0 0 * * 0":
        return "Every Sunday at midnight"
    if cron_expression == "0 0 1 * *":
        return "First day of every month at midnight"

    # Build description
    desc_parts = []

    # Time
    if minute == "0" and hour != "*":
        if hour.isdigit():
            h = int(hour)
            if h == 0:
                desc_parts.append("At midnight")
            elif h == 12:
                desc_parts.append("At noon")
            elif h < 12:
                desc_parts.append(f"At {h}:00 AM")
            else:
                desc_parts.append(f"At {h-12}:00 PM")
        else:
            desc_parts.append(f"At hour {hour}")
    elif minute.isdigit() and hour.isdigit():
        h, m = int(hour), int(minute)
        period = "AM" if h < 12 else "PM"
        display_h = h if h <= 12 else h - 12
        if display_h == 0:
            display_h = 12
        desc_parts.append(f"At {display_h}:{m:02d} {period}")

    # Day of week
    dow_names = {
        "0": "Sunday", "1": "Monday", "2": "Tuesday",
        "3": "Wednesday", "4": "Thursday", "5": "Friday", "6": "Saturday",
        "7": "Sunday"  # Some systems use 7 for Sunday
    }
    if dow != "*":
        if dow in dow_names:
            desc_parts.append(f"on {dow_names[dow]}")
        else:
            desc_parts.append(f"on day-of-week {dow}")

    # Day of month
    if dom != "*":
        if dom.isdigit():
            d = int(dom)
            suffix = "th"
            if d == 1 or d == 21 or d == 31:
                suffix = "st"
            elif d == 2 or d == 22:
                suffix = "nd"
            elif d == 3 or d == 23:
                suffix = "rd"
            desc_parts.append(f"on the {d}{suffix}")
        else:
            desc_parts.append(f"on day {dom}")

    # Month
    month_names = {
        "1": "January", "2": "February", "3": "March", "4": "April",
        "5": "May", "6": "June", "7": "July", "8": "August",
        "9": "September", "10": "October", "11": "November", "12": "December"
    }
    if month != "*":
        if month in month_names:
            desc_parts.append(f"in {month_names[month]}")
        else:
            desc_parts.append(f"in month {month}")

    if not desc_parts:
        return cron_expression

    return " ".join(desc_parts)


def _schedule_to_response(schedule) -> ScheduleResponse:
    """Convert WorkflowSchedule model to response schema."""
    return ScheduleResponse(
        id=schedule.id,
        workflow_id=schedule.workflow_id,
        name=schedule.name,
        cron_expression=schedule.cron_expression,
        timezone=schedule.timezone,
        enabled=schedule.enabled,
        default_input_data=schedule.default_input_data or {},
        max_concurrent_runs=schedule.max_concurrent_runs,
        timeout_minutes=schedule.timeout_minutes,
        idempotency_key_template=schedule.idempotency_key_template,
        last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        last_run_status=schedule.last_run_status,
        created_at=schedule.created_at.isoformat() if schedule.created_at else None,
        updated_at=schedule.updated_at.isoformat() if schedule.updated_at else None
    )


def _run_log_to_response(run_log) -> RunLogResponse:
    """Convert ScheduledRunLog model to response schema."""
    return RunLogResponse(
        id=run_log.id,
        schedule_id=run_log.schedule_id,
        scheduled_for=run_log.scheduled_for.isoformat() if run_log.scheduled_for else None,
        started_at=run_log.started_at.isoformat() if run_log.started_at else None,
        completed_at=run_log.completed_at.isoformat() if run_log.completed_at else None,
        status=run_log.status,
        task_id=run_log.task_id,
        error_message=run_log.error_message,
        idempotency_key=run_log.idempotency_key,
        duration=run_log.duration,
        created_at=run_log.created_at.isoformat() if run_log.created_at else None
    )
