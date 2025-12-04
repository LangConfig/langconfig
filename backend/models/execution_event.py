# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Execution Event Model
Stores detailed execution events for workflow replay and debugging
"""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, Text, Index
from sqlalchemy.orm import relationship
from db.database import Base
import datetime


class ExecutionEvent(Base):
    """
    Stores individual events emitted during workflow execution.

    Enables:
    - Historical replay of workflow executions
    - Debugging and troubleshooting past runs
    - Persistent event logs accessible after completion
    """
    __tablename__ = 'execution_events'

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey('workflow_profiles.id'), nullable=True, index=True)

    # Event data
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSON, nullable=False)

    # Metadata
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)
    run_id = Column(String(100), nullable=True, index=True)
    parent_run_id = Column(String(100), nullable=True)

    # Relationships
    task = relationship("Task", back_populates="execution_events")

    # Composite index for efficient queries
    __table_args__ = (
        Index('ix_execution_events_task_timestamp', 'task_id', 'timestamp'),
        Index('ix_execution_events_workflow_timestamp', 'workflow_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<ExecutionEvent(id={self.id}, task_id={self.task_id}, type='{self.event_type}', timestamp={self.timestamp})>"
