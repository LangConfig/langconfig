# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pydantic import BaseModel
from models.core import ProjectStatus
from models.workflow_strategy import WorkflowStrategy
import datetime
from typing import Optional
# Import ExecutionPlan to ensure consistency, even if not directly used in the schema definition here
from schemas.strategy import ExecutionPlan

class DirectiveCreate(BaseModel):
    goal_description: str
    workflow_strategy: Optional[WorkflowStrategy] = WorkflowStrategy.DEFAULT_SEQUENTIAL

class Directive(BaseModel):
    id: int
    project_id: int
    goal_description: str
    status: ProjectStatus
    created_at: datetime.datetime
    # The execution plan stored in the DB is a dict (JSON)
    execution_plan: dict | None

    class Config:
        from_attributes = True