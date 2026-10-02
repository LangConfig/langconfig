"""Background workflow delegation; ownership and leases live on the worker Task."""
from db.database import Base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func


class SubagentJob(Base):
    __tablename__ = 'subagent_jobs'
    __table_args__ = (UniqueConstraint('parent_task_id', 'request_key', name='uq_subagent_job_request'),)
    id = Column(Integer, primary_key=True)
    parent_task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, index=True)
    worker_task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, unique=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True, index=True)
    workflow_version_id = Column(Integer, ForeignKey('workflow_versions.id'), nullable=False)
    request_key = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default='queued', index=True)
    cancel_with_parent = Column(Boolean, nullable=False, default=True, server_default='true')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
