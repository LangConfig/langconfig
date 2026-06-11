"""Compatibility exports for Deep Agents middleware.

Deep Agents 0.6 moved some middleware and backend symbols. Keep the old
LangConfig import path stable while pointing at the current package layout.
"""

from core.middleware.deep import (
    DeepAgentsMiddlewareFactory,
    FilesystemMiddleware as LocalFilesystemMiddleware,
    SubAgentMiddleware as LocalSubAgentMiddleware,
    TodoListMiddleware as LocalTodoListMiddleware,
)

try:
    from langchain.agents.middleware.todo import TodoListMiddleware
except Exception:
    TodoListMiddleware = LocalTodoListMiddleware

try:
    from deepagents.middleware.filesystem import FilesystemMiddleware
except Exception:
    FilesystemMiddleware = LocalFilesystemMiddleware

try:
    from deepagents.middleware.subagents import SubAgentMiddleware
except Exception:
    SubAgentMiddleware = LocalSubAgentMiddleware

__all__ = [
    "DeepAgentsMiddlewareFactory",
    "FilesystemMiddleware",
    "SubAgentMiddleware",
    "TodoListMiddleware",
]
