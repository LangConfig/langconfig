# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangGraph-based orchestration system for LangConfig.

Simplified for standalone app - imports are lazy-loaded to avoid dependency issues.
"""

# Minimal imports - everything else loaded on-demand
from .graph_state import WorkflowState, WorkflowStatus, ClassificationType, ExecutorType, create_initial_state

__all__ = [
    "WorkflowState",
    "WorkflowStatus",
    "ClassificationType",
    "ExecutorType",
    "create_initial_state",
]
