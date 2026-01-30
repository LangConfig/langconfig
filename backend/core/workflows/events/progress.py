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
from typing import Optional, Dict, Any, Literal, Union
from typing_extensions import TypedDict
from contextvars import ContextVar
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Event Type Definitions (LangGraph-style)
# =============================================================================

class ProgressEventData(TypedDict, total=False):
    """Progress bar event data"""
    label: str          # Progress label (e.g., "Downloading", "Processing")
    value: int          # Current value (0-100 for percentage, or absolute)
    total: int          # Total value (default 100 for percentage)
    message: str        # Additional status message


class StatusEventData(TypedDict, total=False):
    """Status badge event data"""
    label: str          # Status label (e.g., "Analysis", "Validation")
    status: str         # 'pending', 'running', 'success', 'error', 'warning'
    message: str        # Status message


class FileStatusEventData(TypedDict, total=False):
    """File operation event data"""
    filename: str       # Name of the file
    operation: str      # 'reading', 'writing', 'created', 'modified', 'deleted', 'error'
    size_bytes: int     # File size in bytes
    line_count: int     # Number of lines (for text files)
    message: str        # Additional message


CustomEventPayload = Union[ProgressEventData, StatusEventData, FileStatusEventData, Dict[str, Any]]

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


async def emit_agent_context(
    agent_label: str,
    node_id: str,
    system_prompt: str = "",
    tools: list = None,
    attachments: list = None,
    input_messages: list = None,
    model_config: dict = None,
    metadata: dict = None
) -> None:
    """
    Emit an agent context event for debugging purposes.

    This sends information about what the agent has access to,
    which helps users debug issues like missing images or documents.

    Args:
        agent_label: The agent's display label
        node_id: The node ID in the workflow
        system_prompt: The agent's system prompt
        tools: List of tool names available to the agent
        attachments: List of attachments (with type/mimeType info, not full data)
        input_messages: Summary of input messages (with truncation for large content)
        model_config: Model configuration (model name, temperature, etc.)
        metadata: Additional metadata
    """
    try:
        exec_ctx = get_execution_context()
        if not exec_ctx:
            logger.debug(f"No execution context for agent_context event: {agent_label}")
            return

        workflow_id = exec_ctx.get('workflow_id')
        if not workflow_id:
            return

        from services.event_bus import get_event_bus
        event_bus = get_event_bus()
        channel = f"workflow:{workflow_id}"

        # Summarize attachments (don't send full base64 data)
        attachment_summary = []
        if attachments:
            for att in attachments:
                summary = {
                    "name": att.get("name", "attachment"),
                    "mimeType": att.get("mimeType", "unknown"),
                    "hasData": bool(att.get("data") or att.get("url")),
                }
                # Add size info if available
                if att.get("data"):
                    summary["dataSize"] = len(att.get("data", ""))
                attachment_summary.append(summary)

        # Summarize messages (truncate long content)
        message_summary = []
        if input_messages:
            for msg in input_messages[:10]:  # Limit to first 10 messages
                msg_type = getattr(msg, "type", type(msg).__name__)
                content = getattr(msg, "content", str(msg))

                # Handle different content types
                if isinstance(content, list):
                    # Multimodal content
                    content_parts = []
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                text = part.get("text", "")
                                content_parts.append({
                                    "type": "text",
                                    "preview": text[:500] + "..." if len(text) > 500 else text,
                                    "length": len(text)
                                })
                            elif part.get("type") == "image_url":
                                content_parts.append({
                                    "type": "image",
                                    "hasUrl": bool(part.get("image_url", {}).get("url"))
                                })
                        else:
                            content_parts.append({"type": "unknown"})
                    content = content_parts
                elif isinstance(content, str):
                    content = {
                        "type": "text",
                        "preview": content[:500] + "..." if len(content) > 500 else content,
                        "length": len(content)
                    }

                message_summary.append({
                    "type": msg_type,
                    "content": content
                })

        context_event = {
            "type": "agent_context",
            "data": {
                "agent_label": agent_label,
                "node_id": node_id,
                "timestamp": datetime.utcnow().isoformat(),
                "system_prompt": {
                    "preview": system_prompt[:1000] + "..." if len(system_prompt) > 1000 else system_prompt,
                    "length": len(system_prompt)
                },
                "tools": tools or [],
                "attachments": attachment_summary,
                "messages": message_summary,
                "model_config": model_config or {},
                "metadata": metadata or {},
                "task_id": exec_ctx.get('task_id'),
            }
        }

        await event_bus.publish(channel, context_event)
        logger.debug(f"Emitted agent_context for {agent_label}")

    except Exception as e:
        logger.warning(f"Failed to emit agent_context for {agent_label}: {e}")


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


# =============================================================================
# LangGraph-Style Custom Event Emission
# =============================================================================

async def emit_custom_event(
    event_type: str,
    data: CustomEventPayload,
    event_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    agent_label: Optional[str] = None,
    node_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Emit a custom streaming event from within tool execution.

    This follows the LangGraph pattern of custom events that can be:
    - Transient (no id): Fire-and-forget notifications
    - Persistent (with id): Can be updated in-place by emitting same id

    Args:
        event_type: Type identifier (e.g., 'progress', 'status', 'file_status', or custom)
        data: Event-specific payload (ProgressEventData, StatusEventData, FileStatusEventData, or dict)
        event_id: Optional ID for persistent events that can be updated
        tool_name: Tool emitting the event (used for grouping)
        agent_label: Agent context (auto-detected from execution context if not provided)
        node_id: Node context (auto-detected from execution context if not provided)
        metadata: Additional metadata to include

    Example:
        # Transient status event
        await emit_custom_event(
            event_type="status",
            data={"label": "Analysis", "status": "running", "message": "Starting..."}
        )

        # Persistent progress event (can be updated by re-emitting with same id)
        await emit_custom_event(
            event_type="progress",
            event_id="download-progress",
            data={"label": "Download", "value": 50, "total": 100}
        )

        # File operation event
        await emit_custom_event(
            event_type="file_status",
            data={"filename": "report.md", "operation": "created", "size_bytes": 1024}
        )
    """
    try:
        exec_ctx = get_execution_context()
        if not exec_ctx:
            logger.debug(f"No execution context for custom event: {event_type}")
            return

        workflow_id = exec_ctx.get('workflow_id')
        if not workflow_id:
            logger.debug(f"No workflow_id in execution context for custom event: {event_type}")
            return

        from services.event_bus import get_event_bus
        event_bus = get_event_bus()
        channel = f"workflow:{workflow_id}"

        # Build custom event payload
        custom_event = {
            "type": "custom_event",
            "data": {
                "event_type": event_type,
                "payload": dict(data),  # Ensure it's a plain dict
                "timestamp": datetime.utcnow().isoformat(),
                "task_id": exec_ctx.get('task_id'),
                "project_id": exec_ctx.get('project_id'),
            }
        }

        # Add optional fields
        if event_id:
            custom_event["data"]["event_id"] = event_id
        if tool_name:
            custom_event["data"]["tool_name"] = tool_name
        if agent_label or exec_ctx.get('agent_label'):
            custom_event["data"]["agent_label"] = agent_label or exec_ctx.get('agent_label')
        if node_id or exec_ctx.get('node_id'):
            custom_event["data"]["node_id"] = node_id or exec_ctx.get('node_id')
        if metadata:
            custom_event["data"]["metadata"] = metadata

        # Publish to event bus
        await event_bus.publish(channel, custom_event)
        logger.debug(f"Emitted custom event: {event_type} (id={event_id})")

    except Exception as e:
        logger.warning(f"Failed to emit custom event {event_type}: {e}")


class CustomEventContext:
    """
    Async context manager for emitting custom events with lifecycle management.

    Provides convenience methods for common event types (progress, status, file_status).
    Events can be persistent (with event_id) for in-place updates.

    Usage:
        async with CustomEventContext("data_processing", event_id="proc-1") as ctx:
            await ctx.emit_status(status="running", message="Starting...")
            await ctx.emit_progress(label="Step 1", value=25)
            # ... processing ...
            await ctx.emit_progress(label="Step 2", value=75)
            await ctx.emit_status(status="success", message="Done!")

        # Or for file operations:
        async with CustomEventContext("file_ops") as ctx:
            await ctx.emit_file_status("report.md", "writing")
            # ... write file ...
            await ctx.emit_file_status("report.md", "created", size_bytes=1024)
    """

    def __init__(
        self,
        context_name: str,
        event_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        agent_label: Optional[str] = None,
        node_id: Optional[str] = None
    ):
        """
        Initialize custom event context.

        Args:
            context_name: Name for this context (used in event metadata)
            event_id: Optional base ID for persistent events (sub-events will append suffixes)
            tool_name: Tool name for event attribution
            agent_label: Agent label override
            node_id: Node ID override
        """
        self.context_name = context_name
        self.base_event_id = event_id or str(uuid4())[:8]
        self.tool_name = tool_name
        self.agent_label = agent_label
        self.node_id = node_id
        self._progress_counter = 0

    async def __aenter__(self):
        """Enter context - optionally emit a start event."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context - no automatic events on exit for flexibility."""
        return False

    async def emit_progress(
        self,
        label: str,
        value: int,
        total: int = 100,
        message: str = "",
        persistent: bool = True
    ) -> None:
        """
        Emit a progress event.

        Args:
            label: Progress label (e.g., "Downloading", "Processing")
            value: Current value (0-100 for percentage)
            total: Total value (default 100)
            message: Optional status message
            persistent: If True, uses event_id for in-place updates
        """
        self._progress_counter += 1
        event_id = f"{self.base_event_id}-progress" if persistent else None

        await emit_custom_event(
            event_type="progress",
            data=ProgressEventData(
                label=label,
                value=value,
                total=total,
                message=message
            ),
            event_id=event_id,
            tool_name=self.tool_name,
            agent_label=self.agent_label,
            node_id=self.node_id
        )

    async def emit_status(
        self,
        status: Literal['pending', 'running', 'success', 'error', 'warning'],
        message: str = "",
        label: Optional[str] = None,
        persistent: bool = True
    ) -> None:
        """
        Emit a status event.

        Args:
            status: Status type ('pending', 'running', 'success', 'error', 'warning')
            message: Status message
            label: Status label (defaults to context_name)
            persistent: If True, uses event_id for in-place updates
        """
        event_id = f"{self.base_event_id}-status" if persistent else None

        await emit_custom_event(
            event_type="status",
            data=StatusEventData(
                label=label or self.context_name,
                status=status,
                message=message
            ),
            event_id=event_id,
            tool_name=self.tool_name,
            agent_label=self.agent_label,
            node_id=self.node_id
        )

    async def emit_file_status(
        self,
        filename: str,
        operation: Literal['reading', 'writing', 'created', 'modified', 'deleted', 'error'],
        size_bytes: Optional[int] = None,
        line_count: Optional[int] = None,
        message: str = "",
        persistent: bool = False
    ) -> None:
        """
        Emit a file operation status event.

        Args:
            filename: Name of the file
            operation: Operation type
            size_bytes: Optional file size
            line_count: Optional line count
            message: Optional message
            persistent: If True, uses event_id for in-place updates (default False for files)
        """
        event_id = f"{self.base_event_id}-file-{filename}" if persistent else None

        data = FileStatusEventData(
            filename=filename,
            operation=operation,
            message=message
        )
        if size_bytes is not None:
            data["size_bytes"] = size_bytes
        if line_count is not None:
            data["line_count"] = line_count

        await emit_custom_event(
            event_type="file_status",
            data=data,
            event_id=event_id,
            tool_name=self.tool_name,
            agent_label=self.agent_label,
            node_id=self.node_id
        )

    async def emit(
        self,
        event_type: str,
        data: Dict[str, Any],
        event_id: Optional[str] = None
    ) -> None:
        """
        Emit a custom event with arbitrary type and data.

        Args:
            event_type: Custom event type
            data: Event payload
            event_id: Optional event ID for persistence
        """
        await emit_custom_event(
            event_type=event_type,
            data=data,
            event_id=event_id or f"{self.base_event_id}-{event_type}",
            tool_name=self.tool_name,
            agent_label=self.agent_label,
            node_id=self.node_id
        )
