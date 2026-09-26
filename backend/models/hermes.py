# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Hermes draft persistence models."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from db.database import Base


class HermesDraft(Base):
    """
    Approval-gated artifact draft created by Hermes.

    Drafts are intentionally separate from workflows, agents, tools, schedules,
    and triggers so Hermes can prepare changes without publishing them.
    """

    __tablename__ = "hermes_drafts"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    artifact_type = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    payload_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="draft", index=True)
    validation_result = Column(JSON, nullable=True, default=dict)
    source_session_id = Column(String(100), nullable=True, index=True)
    codex_run_id = Column(String(100), nullable=True, index=True)
    apply_result = Column(JSON, nullable=True, default=dict)
    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return f"<HermesDraft(id={self.id}, type='{self.artifact_type}', status='{self.status}')>"
