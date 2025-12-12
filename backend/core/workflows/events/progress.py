# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Tool Progress Event Emitter

Enables tools to emit mid-execution progress updates for long-running operations.
This provides real-time feedback to users while tools like web scraping, file
processing, or API calls are executing.

Usage in tools:

    from core.workflows.events.progress import emit_tool_progress, ToolProgressContext

    # Simple progress emission
    async def my_long_running_tool(query: str) -> str:
        await emit_tool_progress(
            tool_name="my_tool",
            message="Starting analysis...",
            progress_type="started"
        )

        for i, item in enumerate(items):
            await process(item)
            await emit_tool_progress(
                tool_name="my_tool",
                message=f"Processing item {i+1}/{len(items)}",
                progress_type="update",
                percent_complete=int((i+1) / len(items) * 100),
                current_step=i+1,
                total_steps=len(items)
            )

        await emit_tool_progress(
            tool_name="my_tool",
            message="Analysis complete",
            progress_type="completed"
        )
        return result

    # Using context manager for automatic start/complete
    async def web_search(query: str) -> str:
        async with ToolProgressContext("web_search", total_steps=3) as progress:
            await progress.update("Preparing search query...")
            # ... setup ...

            await progress.update("Fetching results...")
            # ... fetch ...

            await progress.update("Processing results...")
            # ... process ...

        return results
"""

import logging
from typing import Optional, Dict, Any, Literal
from contextvars import ContextVar
from datetime import datetime

logger = logging.getLogger(__name__)

# Context variable for execution metadata (workflow_id, task_id, etc.)
# This is set by the executor before graph execution and allows tools
# to emit progress events without needing direct access to the event bus
_execution_context_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    'execution_context', default=None
)


def set_execution_context(context: Dict[str, Any]) -> None:
    """
    Set execution metadata for the current context.

    Called by the workflow executor before graph execution begins.
    This allows tools to emit progress events via the event bus.

    Args:
        context: Dict containing workflow_id, task_id, project_id, etc.
    """
    _execution_context_var.set(context)


def get_execution_context() -> Optional[Dict[str, Any]]:
    """
    Get execution metadata for the current context.

    Returns:
        Dict with workflow_id, task_id, project_id, etc. or None if not set.
    """
    return _execution_context_var.get()


def clear_execution_context() -> None:
    """Clear the execution context (called after workflow completes)."""
    _execution_context_var.set(None)


async def emit_tool_progress(
    tool_name: str,
    message: str,
    progress_type: Literal['started', 'update', 'completed', 'error'] = 'update',
    percent_complete: Optional[int] = None,
    current_step: Optional[int] = None,
    total_steps: Optional[int] = None,
    agent_label: Optional[str] = None,
    node_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Emit a progress event from within a tool execution.

    This function can be called from any tool to report progress updates
    that will be streamed to the frontend in real-time.

    Args:
        tool_name: Name of the tool emitting progress
        message: Human-readable progress message
        progress_type: Type of progress event:
            - 'started': Tool execution has begun
            - 'update': Progress update during execution
            - 'completed': Tool execution finished successfully
            - 'error': Tool encountered an error
        percent_complete: Optional 0-100 percentage complete
        current_step: Optional current step number
        total_steps: Optional total number of steps
        agent_label: Optional agent label (auto-detected from context if not provided)
        node_id: Optional node ID (auto-detected from context if not provided)
        metadata: Optional additional metadata to include in the event
    """
    try:
        # Get execution context for event bus channel
        exec_ctx = get_execution_context()
        if not exec_ctx:
            logger.debug(f"No execution context for progress event: {tool_name}")
            return

        workflow_id = exec_ctx.get('workflow_id')
        if not workflow_id:
            logger.debug(f"No workflow_id in execution context for progress event: {tool_name}")
            return

        # Import event bus here to avoid circular imports
        from services.event_bus import get_event_bus
        event_bus = get_event_bus()
        channel = f"workflow:{workflow_id}"

        # Build progress event payload
        progress_event = {
            "type": "tool_progress",
            "data": {
                "tool_name": tool_name,
                "message": message,
                "progress_type": progress_type,
                "agent_label": agent_label or exec_ctx.get('agent_label'),
                "node_id": node_id or exec_ctx.get('node_id'),
                "timestamp": datetime.utcnow().isoformat(),
                "task_id": exec_ctx.get('task_id'),
                "project_id": exec_ctx.get('project_id'),
            }
        }

        # Add optional fields if provided
        if percent_complete is not None:
            progress_event["data"]["percent_complete"] = max(0, min(100, percent_complete))
        if current_step is not None:
            progress_event["data"]["current_step"] = current_step
        if total_steps is not None:
            progress_event["data"]["total_steps"] = total_steps
        if metadata:
            progress_event["data"]["metadata"] = metadata

        # Publish to event bus (non-blocking)
        await event_bus.publish(channel, progress_event)
        logger.debug(f"Emitted tool progress: {tool_name} - {message} ({progress_type})")

    except Exception as e:
        # Never let progress emission break tool execution
        logger.warning(f"Failed to emit tool progress for {tool_name}: {e}")


class ToolProgressContext:
    """
    Async context manager for automatic progress tracking.

    Automatically emits 'started' on entry and 'completed'/'error' on exit.
    Provides an update() method for reporting progress during execution.

    Usage:
        async with ToolProgressContext("web_search", total_steps=5) as progress:
            await progress.update("Searching...", step=1)
            results = await search()
            await progress.update("Processing results...", step=2)
            # ... more steps
            await progress.update("Formatting output...", step=5)

        # Automatically emits 'completed' on normal exit
        # Automatically emits 'error' if an exception occurs
    """

    def __init__(
        self,
        tool_name: str,
        total_steps: Optional[int] = None,
        agent_label: Optional[str] = None,
        node_id: Optional[str] = None
    ):
        """
        Initialize progress context.

        Args:
            tool_name: Name of the tool for progress events
            total_steps: Optional total number of steps (enables percentage calc)
            agent_label: Optional agent label override
            node_id: Optional node ID override
        """
        self.tool_name = tool_name
        self.total_steps = total_steps
        self.agent_label = agent_label
        self.node_id = node_id
        self.current_step = 0

    async def __aenter__(self):
        """Emit 'started' event on context entry."""
        await emit_tool_progress(
            tool_name=self.tool_name,
            message=f"Starting {self.tool_name}...",
            progress_type="started",
            total_steps=self.total_steps,
            agent_label=self.agent_label,
            node_id=self.node_id,
            percent_complete=0
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Emit 'completed' or 'error' event on context exit."""
        if exc_type is None:
            await emit_tool_progress(
                tool_name=self.tool_name,
                message=f"Completed {self.tool_name}",
                progress_type="completed",
                percent_complete=100,
                current_step=self.total_steps,
                total_steps=self.total_steps,
                agent_label=self.agent_label,
                node_id=self.node_id
            )
        else:
            # Extract error message
            error_msg = str(exc_val) if exc_val else "Unknown error"
            await emit_tool_progress(
                tool_name=self.tool_name,
                message=f"Error in {self.tool_name}: {error_msg}",
                progress_type="error",
                agent_label=self.agent_label,
                node_id=self.node_id,
                metadata={"error_type": exc_type.__name__ if exc_type else "Unknown"}
            )
        return False  # Don't suppress exceptions

    async def update(
        self,
        message: str,
        step: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Emit a progress update.

        Args:
            message: Progress message to display
            step: Optional step number (auto-increments if not provided)
            metadata: Optional additional metadata
        """
        if step is not None:
            self.current_step = step
        else:
            self.current_step += 1

        # Calculate percentage if total_steps is known
        percent = None
        if self.total_steps and self.total_steps > 0:
            percent = int((self.current_step / self.total_steps) * 100)

        await emit_tool_progress(
            tool_name=self.tool_name,
            message=message,
            progress_type="update",
            percent_complete=percent,
            current_step=self.current_step,
            total_steps=self.total_steps,
            agent_label=self.agent_label,
            node_id=self.node_id,
            metadata=metadata
        )
