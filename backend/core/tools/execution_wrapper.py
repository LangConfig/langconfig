# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Tool Execution Wrapper with Action Preset Constraint Enforcement

Wraps LangChain tools to enforce execution constraints from action presets:
- Timeout enforcement (max_duration_seconds)
- Retry logic (max_retries)
- Exclusive execution (prevent parallel runs)
- Graceful vs hard timeout strategies
- Human-in-the-Loop (HITL) approval for high-risk actions
"""

import asyncio
import logging
import functools
from typing import Any, Dict, Optional, Callable
from datetime import datetime
from langchain_core.tools import BaseTool, StructuredTool
from core.presets.actions import ActionPresetRegistry, ExecutionConstraint, ActionPreset

logger = logging.getLogger(__name__)

# Global registry for HITL approval requests
# Maps tool_execution_id -> approval event
_hitl_approval_events: Dict[str, asyncio.Event] = {}
_hitl_approval_results: Dict[str, Dict[str, Any]] = {}


class ExclusiveExecutionLock:
    """
    Global lock manager for exclusive execution constraints.

    Ensures that tools marked with exclusive=True cannot run concurrently
    with other instances of themselves.
    """
    _locks: Dict[str, asyncio.Lock] = {}

    @classmethod
    def get_lock(cls, tool_name: str) -> asyncio.Lock:
        """Get or create lock for a tool"""
        if tool_name not in cls._locks:
            cls._locks[tool_name] = asyncio.Lock()
        return cls._locks[tool_name]

    @classmethod
    def is_locked(cls, tool_name: str) -> bool:
        """Check if a tool is currently locked"""
        if tool_name not in cls._locks:
            return False
        return cls._locks[tool_name].locked()


async def execute_with_timeout(
    func: Callable,
    args: tuple,
    kwargs: dict,
    timeout_seconds: Optional[int],
    timeout_strategy: str = "kill"
) -> Any:
    """
    Execute a function with timeout enforcement.

    Args:
        func: Function to execute
        args: Positional arguments
        kwargs: Keyword arguments
        timeout_seconds: Maximum execution time in seconds (None = no timeout)
        timeout_strategy: "kill" (raise exception) or "graceful_shutdown" (allow cleanup)

    Returns:
        Function result

    Raises:
        asyncio.TimeoutError: If execution exceeds timeout
    """
    if timeout_seconds is None:
        # No timeout - execute normally
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    try:
        if asyncio.iscoroutinefunction(func):
            # Async function
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout_seconds
            )
        else:
            # Sync function - run in executor
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, functools.partial(func, *args, **kwargs)),
                timeout=timeout_seconds
            )
        return result

    except asyncio.TimeoutError:
        if timeout_strategy == "kill":
            logger.error(
                f"Tool execution exceeded timeout of {timeout_seconds}s - killing execution"
            )
            raise asyncio.TimeoutError(
                f"Tool execution exceeded maximum duration of {timeout_seconds} seconds"
            )
        else:
            # Graceful shutdown - log warning but allow completion
            logger.warning(
                f"Tool execution exceeded timeout of {timeout_seconds}s - "
                f"allowing graceful completion (strategy: {timeout_strategy})"
            )
            # Still raise timeout but with different message
            raise asyncio.TimeoutError(
                f"Tool execution exceeded timeout ({timeout_seconds}s) but was allowed to complete"
            )


async def execute_with_retries(
    func: Callable,
    args: tuple,
    kwargs: dict,
    max_retries: int,
    timeout_seconds: Optional[int],
    timeout_strategy: str,
    tool_name: str
) -> Any:
    """
    Execute a function with retry logic.

    Args:
        func: Function to execute
        args: Positional arguments
        kwargs: Keyword arguments
        max_retries: Maximum number of retry attempts (0 = no retries)
        timeout_seconds: Timeout for each attempt
        timeout_strategy: Timeout handling strategy
        tool_name: Tool name for logging

    Returns:
        Function result

    Raises:
        Exception: Last exception if all retries exhausted
    """
    attempts = 0
    last_exception = None

    while attempts <= max_retries:
        try:
            result = await execute_with_timeout(
                func, args, kwargs,
                timeout_seconds=timeout_seconds,
                timeout_strategy=timeout_strategy
            )

            if attempts > 0:
                logger.info(f"Tool '{tool_name}' succeeded after {attempts} retries")

            return result

        except Exception as e:
            attempts += 1
            last_exception = e

            if attempts <= max_retries:
                logger.warning(
                    f"Tool '{tool_name}' failed (attempt {attempts}/{max_retries + 1}): {e}. Retrying..."
                )
                # Exponential backoff: 1s, 2s, 4s, 8s
                await asyncio.sleep(min(2 ** (attempts - 1), 8))
            else:
                logger.error(
                    f"Tool '{tool_name}' failed after {attempts} attempts: {e}"
                )
                raise last_exception


async def _request_hitl_approval(
    tool_name: str,
    preset: ActionPreset,
    args: tuple,
    kwargs: dict
) -> None:
    """
    Request human approval for a high-risk tool execution.

    Publishes a HITL approval request event and waits for user approval.
    Execution will pause until approval is granted or denied.

    Args:
        tool_name: Name of the tool requiring approval
        preset: Action preset with metadata
        args: Tool arguments
        kwargs: Tool keyword arguments

    Raises:
        RuntimeError: If approval is denied
        asyncio.TimeoutError: If approval times out (5 minutes)
    """
    import uuid
    from services.event_bus import get_event_bus

    # Generate unique ID for this approval request
    approval_id = f"approval_{tool_name}_{uuid.uuid4().hex[:8]}"

    logger.warning(
        f"⚠️ Tool '{tool_name}' requires HUMAN APPROVAL before execution "
        f"(risk_level: {preset.risk_level.value})"
    )

    # Create event for this approval
    approval_event = asyncio.Event()
    _hitl_approval_events[approval_id] = approval_event

    # Prepare approval context with tool details
    approval_context = {
        "approval_id": approval_id,
        "tool_name": tool_name,
        "tool_description": preset.description,
        "risk_level": preset.risk_level.value,
        "args": str(args)[:500],  # Truncate for safety
        "kwargs": {k: str(v)[:200] for k, v in kwargs.items()},  # Truncate values
        "best_practices": preset.best_practices,
        "requested_at": datetime.utcnow().isoformat()
    }

    try:
        # Publish HITL approval request to event bus
        event_bus = get_event_bus()

        # We don't have workflow_id in tool context, so publish to general channel
        # Frontend should listen to "hitl:requests" channel
        await event_bus.publish("hitl:requests", {
            "type": "tool_approval_required",
            "data": approval_context
        })

        logger.info(f"HITL approval request published for tool '{tool_name}' (id: {approval_id})")

        # Wait for approval with 5-minute timeout
        try:
            await asyncio.wait_for(approval_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            logger.error(f"HITL approval timed out for tool '{tool_name}' after 5 minutes")
            raise asyncio.TimeoutError(
                f"Tool execution approval timed out after 5 minutes. "
                f"Tool '{tool_name}' was not approved in time."
            )

        # Check approval result
        result = _hitl_approval_results.get(approval_id, {})

        if not result.get("approved", False):
            reject_reason = result.get("comment", "No reason provided")
            logger.warning(f"HITL approval DENIED for tool '{tool_name}': {reject_reason}")
            raise RuntimeError(
                f"Tool execution rejected by user: {reject_reason}"
            )

        logger.info(
            f"✓ HITL approval GRANTED for tool '{tool_name}'. "
            f"Comment: {result.get('comment', 'None')}"
        )

    finally:
        # Cleanup
        if approval_id in _hitl_approval_events:
            del _hitl_approval_events[approval_id]
        if approval_id in _hitl_approval_results:
            del _hitl_approval_results[approval_id]


def approve_tool_execution(approval_id: str, approved: bool, comment: Optional[str] = None):
    """
    Approve or reject a tool execution request.

    This function should be called by the HITL API when user responds to approval request.

    Args:
        approval_id: Unique ID of the approval request
        approved: True to approve, False to reject
        comment: Optional comment from user
    """
    if approval_id not in _hitl_approval_events:
        logger.warning(f"Approval ID not found: {approval_id}")
        return False

    # Store approval result
    _hitl_approval_results[approval_id] = {
        "approved": approved,
        "comment": comment,
        "approved_at": datetime.utcnow().isoformat()
    }

    # Signal the waiting tool
    _hitl_approval_events[approval_id].set()

    logger.info(
        f"Tool approval {'granted' if approved else 'denied'} for {approval_id}. "
        f"Comment: {comment or 'None'}"
    )

    return True


def wrap_tool_with_constraints(tool: BaseTool, preset_id: Optional[str] = None) -> BaseTool:
    """
    Wrap a LangChain tool with execution constraint enforcement.

    If the tool has a matching action preset with constraints, those constraints
    will be enforced during execution.

    Args:
        tool: Original LangChain tool
        preset_id: Optional preset ID to look up constraints. If not provided,
                  attempts to infer from tool.name

    Returns:
        Wrapped tool with constraint enforcement
    """
    if preset_id is None:
        # Try to infer preset_id from tool name
        # Tool names like "web_search" map to preset "web_search"
        preset_id = tool.name

    # Look up action preset
    registry = ActionPresetRegistry
    preset = registry.get(preset_id)

    if preset is None:
        # No preset found - return tool unchanged
        logger.debug(f"No action preset found for tool '{tool.name}', skipping constraint wrapping")
        return tool

    constraints = preset.constraints

    # Check if any constraints are defined
    has_constraints = (
        constraints.max_duration_seconds is not None or
        constraints.max_retries > 0 or
        constraints.exclusive or
        not constraints.allow_parallel
    )

    if not has_constraints:
        # No constraints to enforce
        logger.debug(f"Tool '{tool.name}' has no execution constraints, skipping wrapping")
        return tool

    logger.info(
        f"Wrapping tool '{tool.name}' with constraints: "
        f"timeout={constraints.max_duration_seconds}s, "
        f"retries={constraints.max_retries}, "
        f"exclusive={constraints.exclusive}, "
        f"allow_parallel={constraints.allow_parallel}"
    )

    # Don't extract internal methods - use proper tool API instead
    # This ensures config and other required parameters are handled correctly
    original_func = None
    original_afunc = None

    # Create wrapped functions
    def wrapped_sync_func(*args, **kwargs):
        """Synchronous wrapper - not commonly used but included for completeness"""
        # Run async wrapper in event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context - create task
            return asyncio.create_task(wrapped_async_func(*args, **kwargs))
        else:
            # No event loop - run until complete
            return loop.run_until_complete(wrapped_async_func(*args, **kwargs))

    async def wrapped_async_func(*args, **kwargs):
        """Async wrapper with constraint enforcement and HITL approval"""
        start_time = datetime.utcnow()

        # Check if tool requires human approval (HITL)
        if preset.requires_approval:
            await _request_hitl_approval(tool.name, preset, args, kwargs)

        # Handle exclusive execution
        if constraints.exclusive:
            lock = ExclusiveExecutionLock.get_lock(tool.name)

            if lock.locked():
                error_msg = (
                    f"Tool '{tool.name}' is marked as exclusive and is already running. "
                    f"Please wait for the current execution to complete."
                )
                logger.warning(error_msg)
                raise RuntimeError(error_msg)

            async with lock:
                logger.info(f"Acquired exclusive lock for tool '{tool.name}'")
                result = await _execute_with_all_constraints(*args, **kwargs)
                logger.info(f"Released exclusive lock for tool '{tool.name}'")
                return result
        else:
            return await _execute_with_all_constraints(*args, **kwargs)

    async def _execute_with_all_constraints(*args, **kwargs):
        """Execute with timeout and retry constraints"""
        # Capture start time for elapsed calculation
        start_time = datetime.utcnow()

        # Use tool.ainvoke for async execution (handles config parameter properly)
        # Don't call internal _arun/_run methods directly
        async def invoke_tool():
            # Combine args into input dict for ainvoke
            if args:
                # If args provided, use first arg as input
                tool_input = args[0] if len(args) == 1 else args
            elif kwargs:
                tool_input = kwargs
            else:
                tool_input = {}

            # Extract config if provided in kwargs, otherwise use empty config
            config = kwargs.pop('config', None)

            # Call tool.ainvoke with proper config
            return await tool.ainvoke(tool_input, config=config)

        func = invoke_tool

        # Execute with retries and timeout
        try:
            result = await execute_with_retries(
                func=func,
                args=(),  # No args needed - closure handles it
                kwargs={},  # No kwargs needed - closure handles it
                max_retries=constraints.max_retries,
                timeout_seconds=constraints.max_duration_seconds,
                timeout_strategy=constraints.timeout_strategy,
                tool_name=tool.name
            )

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Tool '{tool.name}' completed in {elapsed:.2f}s")

            return result

        except asyncio.TimeoutError as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                f"Tool '{tool.name}' timed out after {elapsed:.2f}s "
                f"(limit: {constraints.max_duration_seconds}s)"
            )
            raise
        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Tool '{tool.name}' failed after {elapsed:.2f}s: {e}")
            raise

    # Create new tool with wrapped functions
    # Use StructuredTool.from_function to preserve all metadata
    if original_afunc or not original_func:
        # Prefer async
        wrapped_tool = StructuredTool.from_function(
            func=wrapped_async_func,
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema if hasattr(tool, 'args_schema') else None,
            coroutine=wrapped_async_func  # Explicitly mark as coroutine
        )
    else:
        # Sync only
        wrapped_tool = StructuredTool.from_function(
            func=wrapped_sync_func,
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema if hasattr(tool, 'args_schema') else None
        )

    return wrapped_tool


def wrap_tools_with_constraints(
    tools: list[BaseTool],
    preset_mappings: Optional[Dict[str, str]] = None
) -> list[BaseTool]:
    """
    Wrap a list of tools with execution constraints from action presets.

    Args:
        tools: List of LangChain tools to wrap
        preset_mappings: Optional dict mapping tool names to preset IDs.
                        If not provided, uses tool.name as preset_id

    Returns:
        List of wrapped tools (original tools if no constraints found)
    """
    if preset_mappings is None:
        preset_mappings = {}

    wrapped_tools = []
    for tool in tools:
        preset_id = preset_mappings.get(tool.name, tool.name)
        wrapped_tool = wrap_tool_with_constraints(tool, preset_id)
        wrapped_tools.append(wrapped_tool)

    return wrapped_tools
