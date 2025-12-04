# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
DeepAgents Instrumentation Middleware

This module wraps official DeepAgents middleware with observability hooks
to emit real-time events for todos, subagent spawning, and filesystem operations.

The wrappers intercept middleware method calls and emit events via the
ExecutionEventCallbackHandler, enabling frontend visibility into DeepAgent
reasoning and actions.
"""

import logging
from typing import Any, Dict, List, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class InstrumentedFilesystemMiddleware:
    """
    Wrapper around DeepAgents FilesystemMiddleware that emits observability events.

    Intercepts filesystem operations (ls, read_file, write_file, edit_file, etc.)
    and emits DEEPAGENT_FILESYSTEM_OP events for real-time monitoring.
    """

    def __init__(self, filesystem_middleware, callback_handler=None):
        """
        Initialize instrumented middleware.

        Args:
            filesystem_middleware: The official DeepAgents FilesystemMiddleware instance
            callback_handler: ExecutionEventCallbackHandler for event emission
        """
        self.middleware = filesystem_middleware
        self.callback_handler = callback_handler
        logger.info("InstrumentedFilesystemMiddleware initialized")

    async def _emit_operation_event(self, operation: str, file_path: str):
        """Emit filesystem operation event if callback handler is available."""
        if self.callback_handler and hasattr(self.callback_handler, 'on_deepagent_filesystem_operation'):
            try:
                await self.callback_handler.on_deepagent_filesystem_operation(
                    operation=operation,
                    file_path=file_path
                )
            except Exception as e:
                logger.warning(f"Failed to emit filesystem operation event: {e}")

    async def ls(self, path: str, **kwargs):
        """List directory contents with event emission."""
        await self._emit_operation_event("ls", path)
        return await self.middleware.ls(path, **kwargs)

    async def read_file(self, path: str, **kwargs):
        """Read file with event emission."""
        await self._emit_operation_event("read", path)
        return await self.middleware.read_file(path, **kwargs)

    async def write_file(self, path: str, content: str, **kwargs):
        """Write file with event emission."""
        await self._emit_operation_event("write", path)
        return await self.middleware.write_file(path, content, **kwargs)

    async def edit_file(self, path: str, **kwargs):
        """Edit file with event emission."""
        await self._emit_operation_event("edit", path)
        return await self.middleware.edit_file(path, **kwargs)

    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped middleware."""
        return getattr(self.middleware, name)


class InstrumentedSubAgentMiddleware:
    """
    Wrapper around DeepAgents SubAgentMiddleware that emits observability events.

    Intercepts subagent spawning via the `task` tool and emits
    DEEPAGENT_SUBAGENT_SPAWNED events for real-time monitoring.
    """

    def __init__(self, subagent_middleware, callback_handler=None):
        """
        Initialize instrumented middleware.

        Args:
            subagent_middleware: The official DeepAgents SubAgentMiddleware instance
            callback_handler: ExecutionEventCallbackHandler for event emission
        """
        self.middleware = subagent_middleware
        self.callback_handler = callback_handler
        logger.info("InstrumentedSubAgentMiddleware initialized")

    async def task(self, subagent_name: str, task_description: str, **kwargs):
        """
        Spawn a subagent with event emission.

        Args:
            subagent_name: Name of the subagent to spawn
            task_description: Task to assign to the subagent
        """
        # Emit subagent spawned event
        if self.callback_handler and hasattr(self.callback_handler, 'on_deepagent_subagent_spawned'):
            try:
                await self.callback_handler.on_deepagent_subagent_spawned(
                    subagent_name=subagent_name,
                    subagent_task=task_description
                )
            except Exception as e:
                logger.warning(f"Failed to emit subagent spawned event: {e}")

        # Delegate to actual middleware
        return await self.middleware.task(subagent_name, task_description, **kwargs)

    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped middleware."""
        return getattr(self.middleware, name)


class TodoListTracker:
    """
    Tracks todo list operations and emits events.

    DeepAgents' write_todos tool is built-in and not exposed as middleware,
    so we need to track it via tool usage monitoring in the callback handler.

    This class provides helper methods that can be called when we detect
    write_todos tool invocations in the ExecutionEventCallbackHandler.
    """

    def __init__(self, callback_handler=None):
        """
        Initialize todo tracker.

        Args:
            callback_handler: ExecutionEventCallbackHandler for event emission
        """
        self.callback_handler = callback_handler
        self.tracked_todos: Dict[str, str] = {}  # todo_id -> todo_text
        logger.info("TodoListTracker initialized")

    async def on_todo_created(self, todo_id: str, todo_text: str, node_name: str = "DeepAgent"):
        """
        Track a newly created todo and emit event.

        Args:
            todo_id: Unique identifier for the todo
            todo_text: The todo item text
            node_name: Name of the agent node
        """
        self.tracked_todos[todo_id] = todo_text

        if self.callback_handler and hasattr(self.callback_handler, 'on_deepagent_todo_created'):
            try:
                await self.callback_handler.on_deepagent_todo_created(
                    todo_id=todo_id,
                    todo_text=todo_text,
                    node_name=node_name
                )
            except Exception as e:
                logger.warning(f"Failed to emit todo created event: {e}")

    async def on_todo_completed(self, todo_id: str, node_name: str = "DeepAgent"):
        """
        Mark a todo as completed and emit event.

        Args:
            todo_id: Unique identifier for the todo
            node_name: Name of the agent node
        """
        todo_text = self.tracked_todos.get(todo_id, "Unknown todo")

        if self.callback_handler and hasattr(self.callback_handler, 'on_deepagent_todo_completed'):
            try:
                await self.callback_handler.on_deepagent_todo_completed(
                    todo_id=todo_id,
                    todo_text=todo_text,
                    node_name=node_name
                )
            except Exception as e:
                logger.warning(f"Failed to emit todo completed event: {e}")

        # Remove from tracked todos
        self.tracked_todos.pop(todo_id, None)


def instrument_deepagents_middleware(
    middleware_instance,
    callback_handler=None
):
    """
    Wrap a DeepAgents middleware instance with instrumentation.

    Automatically detects the middleware type and applies the appropriate wrapper.

    Args:
        middleware_instance: Official DeepAgents middleware instance
        callback_handler: ExecutionEventCallbackHandler for event emission

    Returns:
        Instrumented middleware instance
    """
    middleware_class_name = middleware_instance.__class__.__name__

    if "FilesystemMiddleware" in middleware_class_name:
        logger.info("Instrumenting FilesystemMiddleware")
        return InstrumentedFilesystemMiddleware(middleware_instance, callback_handler)

    elif "SubAgentMiddleware" in middleware_class_name:
        logger.info("Instrumenting SubAgentMiddleware")
        return InstrumentedSubAgentMiddleware(middleware_instance, callback_handler)

    else:
        # Unknown middleware type - return as-is
        logger.warning(f"Unknown middleware type: {middleware_class_name}, skipping instrumentation")
        return middleware_instance


def create_todo_tracker(callback_handler=None) -> TodoListTracker:
    """
    Factory function to create a TodoListTracker.

    Args:
        callback_handler: ExecutionEventCallbackHandler for event emission

    Returns:
        Configured TodoListTracker instance
    """
    return TodoListTracker(callback_handler)
