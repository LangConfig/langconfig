# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Main LangGraph workflow definition for LangConfig development orchestration.

This module creates and configures the complete workflow graph that orchestrates
the development process from initial directive through execution, validation,
and potential Human-in-the-Loop intervention.

LangGraph v1.0 Features:
- context_schema for runtime configuration
- Reducers for automatic list accumulation
- Nodes receive Runtime[WorkflowContext] parameter
- Clean separation of state vs. configuration
"""

import logging
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, START, END

from .graph_state import WorkflowState, WorkflowStatus, ClassificationType
from .workflow_context import WorkflowContext
from .workflow_nodes import (
    initialize_workflow_node,
    execute_code_node,
    critique_and_validate_node,
    handle_hitl_node,
    retry_workflow_node,
    complete_workflow_node
)
from .context_synthesis import node_synthesize_context
from .http_bridge_adapter import HttpBridgeAdapter
from .checkpointing import get_checkpointer

logger = logging.getLogger(__name__)


def create_workflow_graph(http_bridge: HttpBridgeAdapter) -> StateGraph:
    """
    Create the complete LangGraph workflow for LangConfig orchestration.

    This function defines the workflow structure, including:
    - Node definitions and routing logic
    - Conditional edges for different execution paths
    - HITL intervention points
    - Retry mechanisms

    Args:
        http_bridge: Configured HttpBridgeAdapter instance for task execution

    Returns:
        Configured StateGraph ready for compilation
    """
    logger.info("Creating LangConfig orchestration workflow graph")

    # ✅ Create the state graph with context schema
    workflow = StateGraph(
        WorkflowState,
        context_schema=WorkflowContext  # LangGraph v1.0: Runtime configuration
    )
    
    # Create bound nodes with http_bridge
    from functools import partial
    execute_code_with_bridge = partial(execute_code_node, http_bridge=http_bridge)
    validate_execution_with_bridge = partial(critique_and_validate_node, http_bridge=http_bridge)
    
    # Add workflow nodes
    workflow.add_node("initialize", initialize_workflow_node)
    workflow.add_node("execute_code", execute_code_with_bridge)
    workflow.add_node("synthesize_context", node_synthesize_context)
    workflow.add_node("validate_execution", validate_execution_with_bridge)
    workflow.add_node("handle_hitl", handle_hitl_node)
    workflow.add_node("retry_workflow", retry_workflow_node)
    workflow.add_node("complete_workflow", complete_workflow_node)
    
    # Set entry point using START edge
    workflow.add_edge(START, "initialize")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "initialize",
        _should_proceed_from_initialize,
        {
            "execute": "execute_code",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "execute_code", 
        _route_after_execution,
        {
            "synthesize": "synthesize_context",
            "retry": "retry_workflow",
            "end": END
        }
    )
    
    # Context synthesis routes based on workflow status
    workflow.add_conditional_edges(
        "synthesize_context",
        _route_after_synthesis,
        {
            "validate": "validate_execution",
            "hitl": "handle_hitl",
            "complete": "complete_workflow",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "validate_execution",
        _route_after_validation,
        {
            "complete": "complete_workflow",
            "hitl": "handle_hitl",
            "retry": "retry_workflow", 
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "handle_hitl",
        _route_after_hitl,
        {
            "complete": "complete_workflow",
            "retry": "retry_workflow",
            "wait": "handle_hitl",  # Continue waiting
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "retry_workflow",
        _route_after_retry,
        {
            "execute": "execute_code",
            "end": END
        }
    )
    
    workflow.add_edge("complete_workflow", END)
    
    logger.info("Workflow graph structure created successfully")
    return workflow


def compile_workflow_graph(
    http_bridge: HttpBridgeAdapter,
    checkpointer_enabled: bool = True,
    enable_hitl_interrupts: bool = True,
    checkpoint_mode: str = "selective"
):
    """
    Compile the workflow graph using LangGraph with PostgreSQL checkpointing and HITL interrupts.

    Args:
        http_bridge: Configured HttpBridgeAdapter instance
        checkpointer_enabled: Whether to enable PostgreSQL checkpointing for durability and HITL
        enable_hitl_interrupts: Whether to configure automatic interrupts before HITL nodes
        checkpoint_mode: Checkpointing strategy - "all" (every node), "selective" (key nodes only), "minimal" (HITL only)

    Returns:
        Compiled LangGraph workflow ready for execution

    Note:
        When checkpointer is provided, LangGraph automatically saves state after every node transition.
        HITL interrupts allow workflows to pause before critical nodes for human approval.

        Checkpoint modes:
        - "all": Save state after every node (default LangGraph behavior, most overhead)
        - "selective": Save state at key decision points (validation, execution, HITL)
        - "minimal": Only save state before HITL nodes (lowest overhead, less recovery)
    """
    logger.info("Compiling LangConfig LangGraph orchestration workflow")
    logger.info(f"Checkpoint mode: {checkpoint_mode}")
    
    # Create the workflow graph structure
    workflow = create_workflow_graph(http_bridge)
    
    # Prepare compilation arguments
    compile_args = {}
    
    # Add PostgreSQL checkpointer for durability and HITL support
    if checkpointer_enabled:
        try:
            # Get the initialized checkpointer from the global instance
            checkpointer = get_checkpointer()
            compile_args["checkpointer"] = checkpointer
            logger.info("✓ PostgreSQL checkpointing ENABLED")

            # Configure checkpoint strategy based on mode
            checkpoint_nodes = []
            if checkpoint_mode == "all":
                # Default LangGraph behavior - checkpoint after every node
                logger.info("  - Checkpoint mode: ALL (every node, highest overhead)")
                # No checkpoint_at specified = checkpoint all nodes
            elif checkpoint_mode == "selective":
                # Checkpoint at key decision points for balance of performance and recovery
                checkpoint_nodes = ["execute_code", "validate_execution", "handle_hitl", "complete_workflow"]
                compile_args["checkpoint_at"] = checkpoint_nodes
                logger.info(f"  - Checkpoint mode: SELECTIVE (nodes: {', '.join(checkpoint_nodes)})")
            elif checkpoint_mode == "minimal":
                # Only checkpoint before HITL for minimal overhead
                checkpoint_nodes = ["handle_hitl"]
                compile_args["checkpoint_at"] = checkpoint_nodes
                logger.info(f"  - Checkpoint mode: MINIMAL (HITL only: {', '.join(checkpoint_nodes)})")
            else:
                logger.warning(f"Unknown checkpoint_mode '{checkpoint_mode}', using default (all nodes)")

            logger.info("  - Workflow recovery: ENABLED")
            logger.info("  - HITL support: ENABLED")

            # Configure HITL interrupts if checkpointing is enabled
            # LangGraph will interrupt BEFORE these nodes execute, allowing human review
            if enable_hitl_interrupts:
                compile_args["interrupt_before"] = ["handle_hitl"]
                logger.info("  - HITL interrupts: ENABLED (interrupt before 'handle_hitl' node)")
                logger.info("    Workflows will pause for human approval when HITL is required")

        except Exception as e:
            logger.warning(f"Failed to initialize checkpointer: {e}")
            logger.warning("Compiling workflow WITHOUT checkpointing - HITL and recovery disabled")
    else:
        logger.info("Checkpointing DISABLED - workflow state will not be persisted")
        logger.warning("⚠ HITL workflows will NOT function without checkpointing")
    
    # Compile the workflow with all configured options
    try:
        compiled_workflow = workflow.compile(**compile_args)
        logger.info("✓ LangGraph workflow compiled successfully")
        
        # Log compilation configuration summary
        if "checkpointer" in compile_args:
            logger.info("  Compilation mode: PERSISTENT (with checkpointing)")
        else:
            logger.info("  Compilation mode: EPHEMERAL (no checkpointing)")
            
        if "interrupt_before" in compile_args:
            nodes = ", ".join(compile_args["interrupt_before"])
            logger.info(f"  Interrupt nodes: {nodes}")
        
        return compiled_workflow
        
    except Exception as e:
        logger.error(f"CRITICAL: Failed to compile LangGraph workflow: {e}")
        logger.error("  This is a fatal error - orchestration system will not function")
        raise


# Conditional routing functions
def _should_proceed_from_initialize(state: WorkflowState) -> str:
    """Route from initialization node."""
    # In LangGraph, we check the node's return value which gets merged into state
    # The initialize node returns {"workflow_initialized": True}
    workflow_initialized = state.get("workflow_initialized")
    logger.info(f"Routing from initialize: workflow_initialized={workflow_initialized}, task_id={state.get('task_id')}")
    
    if workflow_initialized:
        logger.info(f"Task {state.get('task_id')}: Proceeding to execute_code")
        return "execute"
    else:
        logger.error(f"Task {state.get('task_id')}: Workflow initialization failed, ending")
        return "end"


def _route_after_execution(state: WorkflowState) -> str:
    """Route after code execution based on results."""
    # This is the new routing logic based on workflow_status
    status = state.get("workflow_status")
    execution_successful = state.get("execution_successful")
    execution_failed = state.get("execution_failed")
    handoff_captured = state.get("handoff_captured")
    
    logger.info(f"Routing after execution for task {state.get('task_id')}: "
                f"status={status}, execution_successful={execution_successful}, "
                f"execution_failed={execution_failed}, handoff_captured={handoff_captured}")
    
    if status == WorkflowStatus.FAILED_EXECUTION:
        logger.error(f"Execution failed for task {state['task_id']}, terminating")
        return "end"
    
    # If SUCCESS, AWAITING_HITL, or EXECUTED, synthesize the context first
    if execution_successful or handoff_captured:
        logger.info(f"Execution successful, proceeding to context synthesis for task {state['task_id']}")
        return "synthesize"
    
    elif execution_failed:
        error_info = state.get("error_message", "")
        
        # Check if we should retry based on error type and retry count
        if (state["retry_count"] < state["max_retries"] and 
            _is_retryable_error(error_info)):
            logger.info(f"Retryable execution failure for task {state['task_id']}, will retry")
            return "retry"
        else:
            logger.error(f"Non-retryable execution failure for task {state['task_id']}, ending workflow")
            return "end"
    
    else:
        logger.warning(f"Unexpected execution state for task {state['task_id']} - "
                       f"no clear success or failure indicator, ending workflow")
        return "end"


def _route_after_synthesis(state: WorkflowState) -> str:
    """Route after context synthesis based on the workflow status."""
    status = state.get("workflow_status")
    classification = state.get("classification")
    
    if status == WorkflowStatus.AWAITING_HITL:
        # Route to the HITL node. The graph will interrupt BEFORE this node runs.
        logger.info(f"Task {state['task_id']} requires HITL intervention")
        return "hitl"
    
    # If DevOps task succeeded without HITL
    if classification == ClassificationType.DEVOPS_IAC and status != WorkflowStatus.FAILED_EXECUTION:
        logger.info(f"DevOps task {state['task_id']} completed, finalizing")
        return "complete"
    
    # Default path for standard coding tasks
    logger.debug(f"Task {state['task_id']} proceeding to validation")
    return "validate"


def _route_after_validation(state: WorkflowState) -> str:
    """Route after validation based on results."""
    if state.get("validation_successful") and state.get("validation_passed"):
        logger.debug(f"Validation passed for task {state['task_id']}, completing workflow")
        return "complete"
    
    elif state.get("validation_failed"):
        if state.get("needs_hitl"):
            logger.info(f"Validation failed but HITL required for task {state['task_id']}")
            return "hitl"
        elif (state["retry_count"] < state["max_retries"] and 
              _should_retry_validation_failure(state)):
            logger.info(f"Validation failed, retrying task {state['task_id']}")
            return "retry"
        else:
            logger.error(f"Validation failed permanently for task {state['task_id']}")
            return "end"
    
    else:
        logger.warning(f"Unexpected validation state for task {state['task_id']}")
        return "end"


def _route_after_hitl(state: WorkflowState) -> str:
    """Route after HITL intervention."""
    if state.get("hitl_completed"):
        decision = state.get("hitl_decision")
        
        if decision == "approve" and state.get("workflow_approved"):
            logger.info(f"HITL approved task {state['task_id']}, completing workflow")
            return "complete"
        
        elif decision == "reject":
            if state.get("should_retry"):
                logger.info(f"HITL rejected task {state['task_id']}, retrying with feedback")
                return "retry"
            else:
                logger.info(f"HITL rejected task {state['task_id']}, ending workflow")
                return "end"
    
    elif state.get("hitl_pending"):
        # Still waiting for human input, continue waiting
        logger.debug(f"Still waiting for human input on task {state['task_id']}")
        return "wait"
    
    else:
        logger.warning(f"Unexpected HITL state for task {state['task_id']}")
        return "end"


def _route_after_retry(state: WorkflowState) -> str:
    """Route after retry logic."""
    if state.get("retry_exceeded") or state.get("workflow_terminated"):
        logger.warning(f"Retry limit exceeded or workflow terminated for task {state['task_id']}")
        return "end"
    
    elif state.get("retry_initialized"):
        logger.info(f"Retry initialized for task {state['task_id']}, restarting execution")
        return "execute"
    
    else:
        logger.warning(f"Unexpected retry state for task {state['task_id']}")
        return "end"


# Helper functions for routing decisions
def _is_retryable_error(error_message: str) -> bool:
    """
    Determine if an error is retryable based on the error message.
    
    Some errors are permanent (e.g., syntax errors in directives)
    while others are transient (e.g., network timeouts).
    """
    if not error_message:
        return False
    
    error_lower = error_message.lower()
    
    # Non-retryable errors
    non_retryable_keywords = [
        "syntax error",
        "invalid directive", 
        "permission denied",
        "authentication failed",
        "invalid configuration",
        "malformed request"
    ]
    
    for keyword in non_retryable_keywords:
        if keyword in error_lower:
            return False
    
    # Retryable errors  
    retryable_keywords = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "unavailable",
        "busy",
        "overloaded"
    ]
    
    for keyword in retryable_keywords:
        if keyword in error_lower:
            return True
    
    # Default to retryable for unknown errors
    return True


def _should_retry_validation_failure(state: WorkflowState) -> bool:
    """
    Determine if a validation failure should trigger a retry.
    
    Some validation failures might be due to transient issues,
    while others indicate fundamental problems with the generated code.
    """
    validation_report = state.get("validation_report", {})
    validation_score = validation_report.get("score", 0.0)
    failure_reasons = validation_report.get("failure_reasons", [])
    
    # If validation score is very low, probably not worth retrying
    if validation_score < 0.1:  # Less than 10%
        return False
    
    # Check for non-retryable failure reasons
    non_retryable_failures = [
        "syntax error",
        "import error", 
        "missing dependency",
        "configuration error"
    ]
    
    for reason in failure_reasons:
        reason_lower = reason.lower() if isinstance(reason, str) else ""
        for non_retryable in non_retryable_failures:
            if non_retryable in reason_lower:
                return False
    
    # If we got here, it might be worth retrying
    return True


# Factory function for easy workflow creation
def create_langconfig_orchestrator(
    http_bridge: HttpBridgeAdapter,
    enable_checkpointing: bool = True,
    enable_hitl: bool = True,
    checkpoint_mode: str = "selective"
):
    """
    Factory function to create a complete LangConfig orchestrator using LangGraph.

    This is the primary entry point for creating the orchestration workflow.
    It configures the workflow with checkpointing and HITL support.

    Args:
        http_bridge: Configured HttpBridgeAdapter instance for task execution
        enable_checkpointing: Whether to enable PostgreSQL state persistence
        enable_hitl: Whether to enable Human-in-the-Loop interrupts
        checkpoint_mode: Checkpointing strategy ("all", "selective", "minimal")

    Returns:
        Ready-to-use compiled LangGraph workflow orchestrator

    Example:
        ```python
        http_bridge = HttpBridgeAdapter()
        orchestrator = create_langconfig_orchestrator(
            http_bridge=http_bridge,
            enable_checkpointing=True,
            enable_hitl=True,
            checkpoint_mode="selective"  # Optimized for performance
        )

        # Execute workflow
        thread_id = f"task_{task_id}"
        config = {"configurable": {"thread_id": thread_id}}
        async for event in orchestrator.astream(state, config):
            logger.info(f"Step: {event}")
        ```
    """
    logger.info("Creating LangConfig LangGraph orchestrator")
    logger.info("  Configuration:")
    logger.info(f"    - Checkpointing: {'ENABLED' if enable_checkpointing else 'DISABLED'}")
    logger.info(f"    - HITL: {'ENABLED' if enable_hitl else 'DISABLED'}")
    logger.info(f"    - Checkpoint mode: {checkpoint_mode}")

    return compile_workflow_graph(
        http_bridge=http_bridge,
        checkpointer_enabled=enable_checkpointing,
        enable_hitl_interrupts=enable_hitl,
        checkpoint_mode=checkpoint_mode
    )
