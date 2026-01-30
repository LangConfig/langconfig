# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
FileVersion Model - Tracks edit history for workspace files.

This model stores version snapshots of files created/edited by agents,
enabling diff viewing and version comparison in the file viewer.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from db.database import Base
import datetime


class FileVersion(Base):
    """Tracks version history for workspace files with edit diffs."""
    __tablename__ = "file_versions"

    id = Column(Integer, primary_key=True, index=True)
    workspace_file_id = Column(Integer, ForeignKey("workspace_files.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=True)  # SHA-256 hash

    # Content snapshot - full content for create/replace operations
    content_snapshot = Column(Text, nullable=True)

    # Edit tracking - for edit_file operations
    operation = Column(String(50), nullable=False)  # "create", "edit", "replace"
    old_string = Column(Text, nullable=True)  # For edit_file: the string that was replaced
    new_string = Column(Text, nullable=True)  # For edit_file: the replacement string

    # Agent context - who made this change
    agent_label = Column(String(255), nullable=True)
    agent_type = Column(String(100), nullable=True)
    node_id = Column(String(100), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    execution_id = Column(String(100), nullable=True)

    # Change summary
    change_summary = Column(String(500), nullable=True)  # Brief description of what changed
    lines_added = Column(Integer, nullable=True)
    lines_removed = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    # Relationships
    workspace_file = relationship("WorkspaceFile", back_populates="versions")
    task = relationship("Task", foreign_keys=[task_id])
