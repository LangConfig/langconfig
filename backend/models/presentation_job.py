# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Presentation Job Database Model

Tracks the status and results of presentation generation jobs.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from db.database import Base
import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class PresentationJobStatus(str, Enum):
    """Status of a presentation generation job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PresentationFormat(str, Enum):
    """Output format for presentations."""
    GOOGLE_SLIDES = "google_slides"
    PDF = "pdf"
    REVEALJS = "revealjs"


class PresentationTheme(str, Enum):
    """Visual theme for presentations."""
    DEFAULT = "default"
    DARK = "dark"
    MINIMAL = "minimal"


class PresentationJob(Base):
    """
    Tracks presentation generation jobs.
    """
    __tablename__ = 'presentation_jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Job status
    status = Column(String(50), nullable=False, default=PresentationJobStatus.PENDING.value, index=True)

    # Output format
    output_format = Column(String(50), nullable=False)

    # Presentation metadata
    title = Column(String(500), nullable=True)
    theme = Column(String(50), default=PresentationTheme.DEFAULT.value)

    # Input items (array of selected artifact/file references)
    input_items = Column(JSONB, nullable=False)

    # Result data
    result_url = Column(Text, nullable=True)  # Google Slides URL
    result_file_path = Column(Text, nullable=True)  # Local file for PDF/HTML

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Context
    workflow_id = Column(Integer, ForeignKey('workflow_profiles.id', ondelete='SET NULL'), nullable=True)
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<PresentationJob(id={self.id}, status='{self.status}', format='{self.output_format}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "status": self.status,
            "output_format": self.output_format,
            "title": self.title,
            "theme": self.theme,
            "input_items": self.input_items,
            "result_url": self.result_url,
            "result_file_path": self.result_file_path,
            "error_message": self.error_message,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

    def mark_processing(self):
        """Mark job as processing."""
        self.status = PresentationJobStatus.PROCESSING.value

    def mark_completed(self, result_url: Optional[str] = None, result_file_path: Optional[str] = None):
        """Mark job as completed with results."""
        self.status = PresentationJobStatus.COMPLETED.value
        self.result_url = result_url
        self.result_file_path = result_file_path
        self.completed_at = datetime.datetime.now(datetime.timezone.utc)

    def mark_failed(self, error_message: str):
        """Mark job as failed with error message."""
        self.status = PresentationJobStatus.FAILED.value
        self.error_message = error_message
        self.completed_at = datetime.datetime.now(datetime.timezone.utc)
