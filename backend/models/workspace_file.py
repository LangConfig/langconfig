# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
WorkspaceFile Model - Tracks metadata for files created by agents.

This model stores information about which agent created a file,
the workflow/task context, and allows for tagging and organizing outputs.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from db.database import Base
import datetime


class WorkspaceFile(Base):
    """Tracks metadata for files created by agents during workflow execution."""
    __tablename__ = "workspace_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False, unique=True)  # Relative path in outputs/

    # Source tracking - which agent created this file
    agent_label = Column(String(255), nullable=True)  # "Deep Research 3.1", "Content Writer"
    agent_type = Column(String(100), nullable=True)   # "researcher", "writer", "coder"
    node_id = Column(String(100), nullable=True)      # React Flow node ID

    # Workflow context
    workflow_id = Column(Integer, ForeignKey("workflow_profiles.id"), nullable=True)
    workflow_name = Column(String(255), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    execution_id = Column(String(100), nullable=True)  # Unique execution run ID

    # Content metadata
    original_query = Column(Text, nullable=True)       # User's original prompt
    description = Column(Text, nullable=True)          # Agent-provided description
    content_type = Column(String(50), nullable=True)   # "report", "data", "code", "notes"
    tags = Column(JSON, default=lambda: [])            # ["research", "gemini", "analysis"]

    # File info
    size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    extension = Column(String(20), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    workflow = relationship("WorkflowProfile", foreign_keys=[workflow_id])
    project = relationship("Project", foreign_keys=[project_id])
    task = relationship("Task", foreign_keys=[task_id])
    versions = relationship("FileVersion", back_populates="workspace_file", order_by="FileVersion.version_number", cascade="all, delete-orphan")
