# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangGraph Workflow Orchestration and Execution Runner.

Enhanced module for executing compiled LangGraph workflows with comprehensive
lifecycle management, checkpoint configuration, and observability.

This module replaces the execution role of the static workflow_graph.py,
providing a runtime-configurable execution environment for dynamic workflows.

Key Features:
- Thread ID management for checkpoint persistence
- Callback integration for observability (Chapter 11)
- Automatic state recovery on failure (Chapter 12)
- Error handling and resilience
- Execution lifecycle logging
- Workflow execution caching for improved performance
- LangGraph v1.0: WorkflowContext for runtime configuration

Usage:
    >>> from core.workflows.runner import execute_workflow
    >>> from core.workflows.context import WorkflowContext
    >>>
    >>> context = WorkflowContext(
    ...     user_id=123,
    ...     project_id=456,
    ...     model_name="gpt-4o"
    ... )
    >>> result = await execute_workflow(
    ...     workflow=compiled_graph,
    ...     initial_state={"messages": [...]},
    ...     context=context,
    ...     project_id=123,
    ...     task_id=456
    ... )
"""

import logging
from typing import Dict, Any, Optional
from uuid import uuid4
from functools import lru_cache
import hashlib
import json

from langgraph.graph.state import CompiledStateGraph

# Import state management
from .graph_state import WorkflowStatus

# Import runtime context (LangGraph v1.0)
from .workflow_context import WorkflowContext

# Import execution event callback for observability
from .execution_events import ExecutionEventCallbackHandler

logger = logging.getLogger(__name__)

# Execution metrics cache for performance monitoring
_execution_metrics: Dict[str, Dict[str, Any]] = {}
_metrics_cache_size = 100


# =============================================================================
# Performance Utilities
# =============================================================================

def _generate_execution_key(project_id: int, task_id: int) -> str:
    """Generate a unique key for execution tracking."""
    return f"exec_{project_id}_{task_id}"


def _cache_execution_metrics(
    execution_key: str,
    metrics: Dict[str, Any]
) -> None:
    """Cache execution metrics for performance monitoring."""
    global _execution_metrics

    # Implement LRU-like behavior
    if len(_execution_metrics) >= _metrics_cache_size:
        # Remove oldest entry (first key)
        oldest_key = next(iter(_execution_metrics))
        del _execution_metrics[oldest_key]

    _execution_metrics[execution_key] = metrics
    logger.debug(f"Cached metrics for {execution_key}: {metrics}")


def get_cached_metrics(execution_key: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached execution metrics if available."""
    return _execution_metrics.get(execution_key)


# =============================================================================
# Core Workflow Execution Function
# =============================================================================

async def execute_workflow(
    workflow: CompiledStateGraph,
    initial_state: Dict[str, Any],
    project_id: int,
    task_id: int,
    context: Optional[WorkflowContext] = None,
    execution_id: Optional[str] = None,
    enable_observability: bool = True
) -> Dict[str, Any]:
    """
    Execute a compiled LangGraph workflow with lifecycle management,
    checkpoint configuration, and observability.

    This is the primary entry point for running dynamic workflows created
    by the WorkflowFactory.

    ✅ LangGraph v1.0: Accepts WorkflowContext for runtime configuration.
    Context contains user_id, credentials, model settings, etc. and is
    passed separately from checkpointed state.

    Args:
        workflow: The compiled LangGraph instance (from WorkflowFactory.compile_workflow)
        initial_state: The starting state for the workflow
        project_id: Project context ID for event routing
        task_id: Task ID for event attribution
        context: Runtime configuration (WorkflowContext) - NOT checkpointed
        execution_id: Unique ID for this run (thread_id for checkpointer).
                     If None, a new UUID will be generated.
        enable_observability: Enable ExecutionEventCallbackHandler for monitoring

    Returns:
        The final state of the workflow after execution

    Raises:
        None: Exceptions are caught and embedded in the returned state

    Example:
        >>> from orchestration.workflow_factory import WorkflowFactory
        >>> from core.workflows.runner import execute_workflow
        >>> from core.workflows.context import WorkflowContext
        >>> from core.workflows.checkpointing.manager import create_postgres_checkpointer
        >>>
        >>> # Create workflow
        >>> factory = WorkflowFactory()
        >>> graph, hitl_nodes = factory.create_workflow_structure(blueprint, strategy)
        >>> checkpointer = await create_postgres_checkpointer()
        >>> compiled = factory.compile_workflow(graph, hitl_nodes, checkpointer)
        >>>
        >>> # Create runtime context
        >>> context = WorkflowContext(
        ...     user_id=current_user.id,
        ...     project_id=123,
        ...     model_name="gpt-4o",
        ...     jira_email=user.jira_email,
        ...     jira_api_token=user.jira_token
        ... )
        >>>
        >>> # Execute workflow
        >>> result = await execute_workflow(
        ...     workflow=compiled,
        ...     initial_state={"task_id": 456, "directive": "Build the feature"},
        ...     context=context,
        ...     project_id=123,
        ...     task_id=456
        ... )
        >>>
        >>> print(f"Status: {result['workflow_status']}")
    """
    # 1. Determine the Execution ID (Thread ID) for the Checkpointer
    thread_id = execution_id or f"run_{task_id}_{uuid4().hex[:8]}"
    execution_key = _generate_execution_key(project_id, task_id)

    logger.info(
        f"Starting workflow execution for Task {task_id}. "
        f"Thread ID: {thread_id}"
    )

    # Track execution start time for metrics
    import time
    start_time = time.time()

    # 2. Initialize Observability (Chapter 11)
    callbacks = []
    if enable_observability:
        try:
            execution_monitor = ExecutionEventCallbackHandler(
                project_id=project_id,
                task_id=task_id,
                save_to_db=True  # Enable DB persistence for historical execution logs
            )
            callbacks.append(execution_monitor)
            logger.debug("✓ ExecutionEventCallbackHandler initialized")
        except Exception as e:
            # Don't fail execution if callback setup fails
            logger.warning(
                f"Failed to initialize ExecutionEventCallbackHandler: {e}. "
                f"Proceeding without detailed event monitoring."
            )

    # 3. Configure Runtime
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": callbacks
    }

    # 4. Execute the Workflow (Asynchronous)
    final_state = {}
    try:
        logger.info(f"Invoking workflow for task {task_id}")

        # ✅ LangGraph v1.0: Pass context separately from state
        # Context is NOT checkpointed - it's runtime configuration only
        if context:
            logger.debug(f"Executing with WorkflowContext (user_id={context.user_id}, model={context.model_name})")
            final_state = await workflow.ainvoke(initial_state, config=config, context=context)
        else:
            # Backward compatibility: No context provided
            logger.debug("Executing without WorkflowContext (backward compatibility mode)")
            final_state = await workflow.ainvoke(initial_state, config=config)

        workflow_status = final_state.get('workflow_status', 'UNKNOWN')
        logger.info(
            f"Workflow execution completed for Task {task_id}. "
            f"Final Status: {workflow_status}"
        )

        # Log and cache execution metrics if callback was used
        execution_time = time.time() - start_time
        metrics = {
            "execution_time": execution_time,
            "workflow_status": workflow_status,
            "thread_id": thread_id,
        }

        if enable_observability and callbacks:
            monitor = callbacks[0]
            metrics.update({
                "tool_calls": monitor.tool_call_count,
                "llm_calls": monitor.llm_call_count,
                "tokens": monitor.total_tokens,
                "errors": monitor.error_count,
            })
            logger.info(
                f"Execution Metrics for Task {task_id}: "
                f"time={execution_time:.2f}s, "
                f"tool_calls={monitor.tool_call_count}, "
                f"llm_calls={monitor.llm_call_count}, "
                f"tokens={monitor.total_tokens}, "
                f"errors={monitor.error_count}"
            )
        else:
            logger.info(
                f"Execution Metrics for Task {task_id}: "
                f"time={execution_time:.2f}s"
            )

        # Cache metrics for performance analysis
        _cache_execution_metrics(execution_key, metrics)

    except Exception as e:
        # Handle unexpected execution errors (Resilience/Chapter 12)
        logger.error(
            f"Critical workflow execution error for Task {task_id}: {e}",
            exc_info=True
        )

        # Attempt recovery: Retrieve the last known state from the checkpointer
        final_state = await _attempt_state_recovery(workflow, config, initial_state)

        # Update the state to reflect the critical error
        final_state.update({
            "error": f"Workflow execution failed: {type(e).__name__}",
            "error_message": str(e),
            "workflow_status": WorkflowStatus.CRITICAL_FAILURE
        })

        logger.error(
            f"Workflow execution terminated with CRITICAL_FAILURE for task {task_id}"
        )

    return final_state


async def _attempt_state_recovery(
    workflow: CompiledStateGraph,
    config: Dict[str, Any],
    initial_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Helper to attempt recovery of the last checkpointed state on failure.

    If the workflow has a checkpointer configured, this function will attempt
    to retrieve the last saved state for the given thread_id. This enables
    partial recovery in case of catastrophic failures.

    Args:
        workflow: The compiled workflow graph (may have checkpointer)
        config: Runtime config with thread_id
        initial_state: Fallback to return if recovery fails

    Returns:
        Last checkpointed state or initial state if recovery fails
    """
    if not hasattr(workflow, 'checkpointer') or workflow.checkpointer is None:
        logger.debug("No checkpointer available for state recovery")
        return initial_state.copy()

    try:
        logger.info("Attempting to recover last checkpointed state...")

        # Retrieve the last checkpoint for the given configuration (thread_id)
        last_checkpoint = await workflow.checkpointer.aget(config)

        if last_checkpoint and "channel_values" in last_checkpoint:
            logger.info("✓ Recovered last known state from checkpointer")
            return last_checkpoint["channel_values"]
        else:
            logger.warning("Checkpoint exists but no channel_values found")
            return initial_state.copy()

    except Exception as cp_e:
        logger.error(
            f"Failed to retrieve last checkpoint during error recovery: {cp_e}",
            exc_info=True
        )
        return initial_state.copy()


# =============================================================================
# Advanced Execution: Streaming Support
# =============================================================================

async def execute_workflow_streaming(
    workflow: CompiledStateGraph,
    initial_state: Dict[str, Any],
    project_id: int,
    task_id: int,
    context: Optional[WorkflowContext] = None,
    execution_id: Optional[str] = None,
    enable_observability: bool = True
):
    """
    Execute a workflow with streaming support for real-time state updates.

    This function uses astream_events() to yield state updates as they occur,
    enabling real-time progress monitoring in the frontend.

    ✅ LangGraph v1.0: Accepts WorkflowContext for runtime configuration.

    Args:
        workflow: Compiled LangGraph workflow
        initial_state: Starting state
        project_id: Project context ID
        task_id: Task ID
        context: Runtime configuration (WorkflowContext) - NOT checkpointed
        execution_id: Unique execution ID (thread_id)
        enable_observability: Enable callback monitoring

    Yields:
        Dict[str, Any]: State updates as they occur during execution

    Example:
        >>> context = WorkflowContext(user_id=123, project_id=456)
        >>> async for state_update in execute_workflow_streaming(workflow, initial_state, 123, 456, context):
        ...     print(f"Node completed: {state_update.get('node_id')}")
    """
    thread_id = execution_id or f"run_{task_id}_{uuid4().hex[:8]}"
    logger.info(
        f"Starting STREAMING workflow execution for Task {task_id}. "
        f"Thread ID: {thread_id}"
    )

    # Initialize callbacks
    callbacks = []
    if enable_observability:
        try:
            execution_monitor = ExecutionEventCallbackHandler(
                project_id=project_id,
                task_id=task_id,
                save_to_db=True  # Enable DB persistence for historical execution logs
            )
            callbacks.append(execution_monitor)
            logger.debug("✓ ExecutionEventCallbackHandler initialized with DB persistence")
        except Exception as e:
            logger.warning(f"Failed to initialize callbacks: {e}")

    # Configure runtime
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": callbacks
    }

    try:
        # ✅ LangGraph v1.0: Use astream with context
        if context:
            async for state_snapshot in workflow.astream(initial_state, config=config, context=context):
                yield state_snapshot
        else:
            # Backward compatibility
            async for state_snapshot in workflow.astream(initial_state, config=config):
                yield state_snapshot

        logger.info(f"Streaming workflow execution completed for Task {task_id}")

    except Exception as e:
        logger.error(
            f"Streaming workflow execution error for Task {task_id}: {e}",
            exc_info=True
        )

        # Yield error state
        error_state = initial_state.copy()
        error_state.update({
            "error": f"Workflow execution failed: {type(e).__name__}",
            "error_message": str(e),
            "workflow_status": WorkflowStatus.CRITICAL_FAILURE
        })
        yield error_state


# =============================================================================
# HITL Resume Execution
# =============================================================================

async def resume_workflow_after_hitl(
    workflow: CompiledStateGraph,
    thread_id: str,
    approval_data: Dict[str, Any],
    project_id: int,
    task_id: int,
    context: Optional[WorkflowContext] = None,
    enable_observability: bool = True
) -> Dict[str, Any]:
    """
    Resume a workflow execution after HITL approval/modification.

    When a workflow is interrupted for human-in-the-loop approval, this
    function resumes execution with the human's decision.

    ✅ LangGraph v1.0: Accepts WorkflowContext for runtime configuration.

    Args:
        workflow: The compiled workflow graph
        thread_id: Thread ID of the interrupted execution
        approval_data: Data from human approval (may include state updates)
        project_id: Project context ID
        task_id: Task ID
        context: Runtime configuration (WorkflowContext) - NOT checkpointed
        enable_observability: Enable callback monitoring

    Returns:
        Final state after resuming execution

    Example:
        >>> # Workflow interrupted at HITL node
        >>> # User approves in frontend, sends approval_data
        >>> context = WorkflowContext(user_id=123, project_id=456)
        >>> result = await resume_workflow_after_hitl(
        ...     workflow=compiled,
        ...     thread_id="run_456_abc123",
        ...     approval_data={"approved": True, "modifications": {...}},
        ...     project_id=123,
        ...     task_id=456,
        ...     context=context
        ... )
    """
    logger.info(
        f"Resuming workflow after HITL for Task {task_id}. "
        f"Thread ID: {thread_id}"
    )

    # Initialize callbacks
    callbacks = []
    if enable_observability:
        try:
            execution_monitor = ExecutionEventCallbackHandler(
                project_id=project_id,
                task_id=task_id,
                save_to_db=False  # Disable DB persistence to avoid asyncio loop conflicts
            )
            callbacks.append(execution_monitor)
        except Exception as e:
            logger.warning(f"Failed to initialize callbacks: {e}")

    # Configure runtime with existing thread_id
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": callbacks
    }

    try:
        # ✅ LangGraph v1.0: Resume with context
        # LangGraph will continue from where it was interrupted
        if context:
            final_state = await workflow.ainvoke(approval_data, config=config, context=context)
        else:
            # Backward compatibility
            final_state = await workflow.ainvoke(approval_data, config=config)

        logger.info(
            f"Workflow resumed and completed for Task {task_id}. "
            f"Status: {final_state.get('workflow_status')}"
        )

        return final_state

    except Exception as e:
        logger.error(
            f"Failed to resume workflow after HITL for Task {task_id}: {e}",
            exc_info=True
        )

        # Attempt state recovery
        recovery_state = await _attempt_state_recovery(
            workflow, config, approval_data
        )

        recovery_state.update({
            "error": f"Workflow resume failed: {type(e).__name__}",
            "error_message": str(e),
            "workflow_status": WorkflowStatus.CRITICAL_FAILURE
        })

        return recovery_state


# =============================================================================
# Execution State Inspection
# =============================================================================

async def get_workflow_state(
    workflow: CompiledStateGraph,
    thread_id: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve the current state of a workflow execution by thread ID.

    This is useful for inspecting interrupted workflows (e.g., HITL)
    or monitoring long-running executions.

    Args:
        workflow: The compiled workflow graph
        thread_id: Thread ID of the execution

    Returns:
        Current workflow state or None if not found

    Example:
        >>> state = await get_workflow_state(workflow, "run_456_abc123")
        >>> if state:
        ...     print(f"Current status: {state.get('workflow_status')}")
    """
    if not hasattr(workflow, 'checkpointer') or workflow.checkpointer is None:
        logger.warning("Cannot retrieve state: workflow has no checkpointer")
        return None

    try:
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint = await workflow.checkpointer.aget(config)

        if checkpoint and "channel_values" in checkpoint:
            logger.info(f"Retrieved state for thread {thread_id}")
            return checkpoint["channel_values"]
        else:
            logger.warning(f"No state found for thread {thread_id}")
            return None

    except Exception as e:
        logger.error(f"Failed to retrieve workflow state: {e}", exc_info=True)
        return None


# =============================================================================
# Workflow Execution History
# =============================================================================

async def get_workflow_history(
    workflow: CompiledStateGraph,
    thread_id: str,
    limit: Optional[int] = None
) -> list:
    """
    Retrieve the execution history (checkpoints) for a workflow.

    This provides a timeline of state changes throughout the workflow execution,
    useful for debugging and auditing.

    Args:
        workflow: The compiled workflow graph
        thread_id: Thread ID of the execution
        limit: Optional limit on number of checkpoints to retrieve

    Returns:
        List of checkpoint snapshots (newest first)

    Example:
        >>> history = await get_workflow_history(workflow, "run_456_abc123", limit=10)
        >>> for i, checkpoint in enumerate(history):
        ...     print(f"Step {i}: {checkpoint['channel_values'].get('workflow_status')}")
    """
    if not hasattr(workflow, 'checkpointer') or workflow.checkpointer is None:
        logger.warning("Cannot retrieve history: workflow has no checkpointer")
        return []

    try:
        config = {"configurable": {"thread_id": thread_id}}

        # Use aget_tuple_history if available (newer LangGraph API)
        if hasattr(workflow.checkpointer, 'aget_tuple_history'):
            history = []
            async for checkpoint_tuple in workflow.checkpointer.aget_tuple_history(config):
                history.append(checkpoint_tuple)
                if limit and len(history) >= limit:
                    break
            logger.info(f"Retrieved {len(history)} checkpoints for thread {thread_id}")
            return history
        else:
            logger.warning("Checkpointer does not support history retrieval")
            return []

    except Exception as e:
        logger.error(f"Failed to retrieve workflow history: {e}", exc_info=True)
        return []
