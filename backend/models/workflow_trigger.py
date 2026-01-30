# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Trigger Models

Database models for event-based workflow triggers including:
- Webhooks (external services calling in)
- File watchers (local file system monitoring)
- Future: Email triggers (Gmail, Outlook)
"""

import datetime
import enum
import secrets
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from db.database import Base


class TriggerType(str, enum.Enum):
    """Types of workflow triggers."""
    WEBHOOK = "webhook"
    FILE_WATCH = "file_watch"
    # Future trigger types
    # EMAIL_GMAIL = "email_gmail"
    # EMAIL_OUTLOOK = "email_outlook"
    # DATABASE_CHANGE = "database_change"


class TriggerStatus(str, enum.Enum):
    """Status of a trigger execution."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WorkflowTrigger(Base):
    """
    Event-based workflow trigger configuration.

    Allows workflows to be automatically executed in response to external
    events like webhooks or file system changes.

    Attributes:
        id: Unique trigger identifier
        workflow_id: Reference to the workflow to execute
        trigger_type: Type of trigger (webhook, file_watch, etc.)
        name: Optional human-readable name
        enabled: Whether the trigger is active
        config: Trigger-specific configuration (JSON)
            - webhook: {secret, allowed_ips, require_signature}
            - file_watch: {watch_path, patterns, recursive, events}
        webhook_url: Generated URL for webhook triggers (read-only)
        webhook_secret: Secret for webhook signature verification
        last_triggered_at: Timestamp of last trigger
        trigger_count: Number of times triggered
    """
    __tablename__ = "workflow_triggers"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Workflow reference
    workflow_id = Column(
        Integer,
        ForeignKey('workflow_profiles.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Trigger metadata
    name = Column(String(255), nullable=True)
    trigger_type = Column(String(50), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True)

    # Trigger-specific configuration
    config = Column(JSONB, nullable=False, default=dict)
    """
    Config structure by trigger type:

    webhook:
        {
            "require_signature": true,
            "allowed_ips": ["192.168.1.0/24"],  # Optional IP whitelist
            "transform_payload": false,  # Pass raw payload or transform
            "input_mapping": {  # Map webhook fields to workflow input
                "task": "$.body.message",
                "context.source": "webhook"
            }
        }

    file_watch:
        {
            "watch_path": "C:/Users/Cade/Downloads",
            "patterns": ["*.pdf", "*.docx"],  # Glob patterns to match
            "recursive": false,
            "events": ["created", "modified"],  # Which events to trigger on
            "debounce_seconds": 5,  # Prevent rapid re-triggers
            "input_mapping": {
                "task": "Process file: {file_path}",
                "context.file_path": "{file_path}",
                "context.file_name": "{file_name}"
            }
        }
    """

    # Webhook-specific fields
    webhook_secret = Column(String(64), nullable=True)

    # State tracking
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, nullable=False, default=0)

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
    trigger_logs = relationship(
        "TriggerLog",
        back_populates="trigger",
        cascade="all, delete-orphan",
        order_by="desc(TriggerLog.triggered_at)"
    )

    def __repr__(self):
        return (
            f"<WorkflowTrigger(id={self.id}, workflow_id={self.workflow_id}, "
            f"type='{self.trigger_type}', enabled={self.enabled})>"
        )

    @staticmethod
    def generate_webhook_secret() -> str:
        """Generate a secure webhook secret."""
        return secrets.token_urlsafe(32)

    def get_webhook_url(self, base_url: str) -> str:
        """Get the full webhook URL for this trigger."""
        if self.trigger_type != TriggerType.WEBHOOK.value:
            return None
        return f"{base_url}/api/webhooks/trigger/{self.id}"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "enabled": self.enabled,
            "config": self.config,
            "webhook_secret": self.webhook_secret,  # Only return for owner
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "trigger_count": self.trigger_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TriggerLog(Base):
    """
    Log of trigger executions.

    Records each time a trigger fires, including the payload received
    and the resulting workflow execution.
    """
    __tablename__ = "trigger_logs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Trigger reference
    trigger_id = Column(
        Integer,
        ForeignKey('workflow_triggers.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Execution details
    triggered_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, default=TriggerStatus.PENDING.value, index=True)

    # What caused the trigger
    trigger_source = Column(String(255), nullable=True)  # IP address, file path, etc.
    trigger_payload = Column(JSONB, nullable=True)  # Incoming data

    # Task reference
    task_id = Column(
        Integer,
        ForeignKey('background_tasks.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Timestamps
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.datetime.utcnow
    )

    # Relationships
    trigger = relationship("WorkflowTrigger", back_populates="trigger_logs")

    def __repr__(self):
        return (
            f"<TriggerLog(id={self.id}, trigger_id={self.trigger_id}, "
            f"status='{self.status}')>"
        )

    @property
    def duration(self) -> float | None:
        """Calculate execution duration in seconds."""
        if not self.triggered_at or not self.completed_at:
            return None
        return (self.completed_at - self.triggered_at).total_seconds()

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "trigger_id": self.trigger_id,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "status": self.status,
            "trigger_source": self.trigger_source,
            "trigger_payload": self.trigger_payload,
            "task_id": self.task_id,
            "error_message": self.error_message,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
