# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Background Task Model

Database-backed task queue for long-running operations.

- PostgreSQL-backed task queue (no Redis/Celery needed)
- Uses SELECT FOR UPDATE SKIP LOCKED for queue semantics
- Built-in persistence and retry logic
- Suitable for desktop application with low concurrency

Task Lifecycle:
1. PENDING - Task created, waiting for worker
2. RUNNING - Worker claimed task, executing
3. COMPLETED - Task finished successfully
4. FAILED - Task failed after max retries
5. CANCELLED - Task cancelled by user
"""

import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB
from db.database import Base


class BackgroundTask(Base):
    """
    Background task for async operations.

    Uses PostgreSQL as task queue backend with SELECT FOR UPDATE SKIP LOCKED
    for efficient task claiming without race conditions.

    Attributes:
        id: Unique task identifier
        task_type: Type of task (e.g., 'export_agent', 'download_image')
        payload: Task input data (JSON)
        priority: Task priority (higher = more urgent, default: 50)
        status: Current task status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
        result: Task output data (JSON, set on completion)
        error: Error message (set on failure)
        retry_count: Number of retry attempts
        max_retries: Maximum retry attempts before giving up
        created_at: Task creation timestamp
        started_at: Task execution start timestamp
        completed_at: Task completion timestamp
    """
    __tablename__ = "background_tasks"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Task metadata
    task_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    priority = Column(Integer, nullable=False, default=50, index=True)  # Higher = more urgent

    # Task status
    status = Column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True
    )  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED

    # Task result
    result = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)

    # Retry logic
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.datetime.utcnow,
        index=True
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return (
            f"<BackgroundTask(id={self.id}, type='{self.task_type}', "
            f"status='{self.status}', priority={self.priority})>"
        )

    @property
    def duration(self) -> float:
        """
        Calculate task duration in seconds.

        Returns:
            float: Duration in seconds, or None if not completed
        """
        if not self.started_at or not self.completed_at:
            return None

        delta = self.completed_at - self.started_at
        return delta.total_seconds()

    @property
    def wait_time(self) -> float:
        """
        Calculate time waited in queue before execution.

        Returns:
            float: Wait time in seconds, or None if not started
        """
        if not self.started_at:
            return None

        delta = self.started_at - self.created_at
        return delta.total_seconds()

    @property
    def is_terminal(self) -> bool:
        """Check if task is in terminal state (COMPLETED, FAILED, CANCELLED)."""
        return self.status in ("COMPLETED", "FAILED", "CANCELLED")

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return (
            self.status == "FAILED" and
            self.retry_count < self.max_retries
        )

    def to_dict(self) -> dict:
        """
        Convert task to dictionary for API responses.

        Returns:
            dict: Task data with all fields
        """
        return {
            "id": self.id,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "wait_time": self.wait_time
        }
