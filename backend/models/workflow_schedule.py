# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Schedule Models

Database models for workflow cron scheduling and execution tracking.

WorkflowSchedule: Defines when a workflow should run automatically.
ScheduledRunLog: Tracks individual scheduled execution attempts.
"""

import datetime
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from db.database import Base


class ScheduleRunStatus(str, enum.Enum):
    """Status of a scheduled workflow execution."""
    PENDING = "PENDING"      # Scheduled, waiting to start
    RUNNING = "RUNNING"      # Currently executing
    SUCCESS = "SUCCESS"      # Completed successfully
    FAILED = "FAILED"        # Failed with error
    SKIPPED = "SKIPPED"      # Skipped (e.g., duplicate idempotency key)


class WorkflowSchedule(Base):
    """
    Cron-based workflow schedule configuration.

    Allows workflows to be automatically executed on a recurring schedule
    using cron expressions. Supports timezone awareness, concurrency limits,
    and idempotency controls.

    Attributes:
        id: Unique schedule identifier
        workflow_id: Reference to the workflow profile to execute
        name: Optional human-readable schedule name
        cron_expression: Standard cron expression (e.g., "0 9 * * *" for 9 AM daily)
        timezone: Timezone for cron evaluation (default: UTC)
        enabled: Whether the schedule is active
        default_input_data: Default input to pass to workflow execution
        max_concurrent_runs: Maximum parallel executions (lock mechanism)
        timeout_minutes: Maximum execution time before timeout
        idempotency_key_template: Template for deduplication (e.g., "report_{date}")
        last_run_at: Timestamp of last execution
        next_run_at: Calculated next execution time (indexed for polling)
        last_run_status: Status of the most recent execution
    """
    __tablename__ = "workflow_schedules"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Workflow reference
    workflow_id = Column(
        Integer,
        ForeignKey('workflow_profiles.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Schedule metadata
    name = Column(String(255), nullable=True)

    # Cron configuration
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), nullable=False, default="UTC")
    enabled = Column(Boolean, nullable=False, default=True)

    # Execution settings
    default_input_data = Column(JSONB, nullable=False, default=dict)
    max_concurrent_runs = Column(Integer, nullable=False, default=1)
    timeout_minutes = Column(Integer, nullable=False, default=60)
    idempotency_key_template = Column(String(255), nullable=True)

    # Tracking
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_run_status = Column(String(20), nullable=True)  # SUCCESS, FAILED, SKIPPED

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.datetime.utcnow
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow
    )

    # Relationships
    run_logs = relationship(
        "ScheduledRunLog",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="desc(ScheduledRunLog.scheduled_for)"
    )

    def __repr__(self):
        return (
            f"<WorkflowSchedule(id={self.id}, workflow_id={self.workflow_id}, "
            f"cron='{self.cron_expression}', enabled={self.enabled})>"
        )

    @property
    def is_due(self) -> bool:
        """Check if schedule is due for execution."""
        if not self.enabled or not self.next_run_at:
            return False
        return datetime.datetime.now(datetime.timezone.utc) >= self.next_run_at

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "name": self.name,
            "cron_expression": self.cron_expression,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "default_input_data": self.default_input_data,
            "max_concurrent_runs": self.max_concurrent_runs,
            "timeout_minutes": self.timeout_minutes,
            "idempotency_key_template": self.idempotency_key_template,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_run_status": self.last_run_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScheduledRunLog(Base):
    """
    Log of scheduled workflow execution attempts.

    Records each scheduled execution with its status, timing, and any errors.
    Links to the BackgroundTask table for full execution details.

    Attributes:
        id: Unique log entry identifier
        schedule_id: Reference to the parent schedule
        scheduled_for: Original scheduled execution time
        started_at: Actual execution start time
        completed_at: Execution completion time
        status: Current status (PENDING, RUNNING, SUCCESS, FAILED, SKIPPED)
        task_id: Reference to BackgroundTask for execution details
        error_message: Error details if failed
        idempotency_key: Unique key for deduplication
    """
    __tablename__ = "scheduled_run_logs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Schedule reference
    schedule_id = Column(
        Integer,
        ForeignKey('workflow_schedules.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Timing
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    status = Column(
        String(20),
        nullable=False,
        default=ScheduleRunStatus.PENDING.value,
        index=True
    )

    # Task reference (links to BackgroundTask for full execution details)
    task_id = Column(
        Integer,
        ForeignKey('background_tasks.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Idempotency
    idempotency_key = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.datetime.utcnow
    )

    # Unique constraint for idempotency
    __table_args__ = (
        UniqueConstraint('idempotency_key', name='uq_scheduled_run_logs_idempotency_key'),
    )

    # Relationships
    schedule = relationship("WorkflowSchedule", back_populates="run_logs")

    def __repr__(self):
        return (
            f"<ScheduledRunLog(id={self.id}, schedule_id={self.schedule_id}, "
            f"status='{self.status}', scheduled_for={self.scheduled_for})>"
        )

    @property
    def duration(self) -> float | None:
        """Calculate execution duration in seconds."""
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def is_terminal(self) -> bool:
        """Check if execution is in a terminal state."""
        return self.status in (
            ScheduleRunStatus.SUCCESS.value,
            ScheduleRunStatus.FAILED.value,
            ScheduleRunStatus.SKIPPED.value
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "task_id": self.task_id,
            "error_message": self.error_message,
            "idempotency_key": self.idempotency_key,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
