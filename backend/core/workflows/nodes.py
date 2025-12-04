# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Core workflow nodes for the LangGraph orchestration system.

Enhanced with AgentFactory execution, Reflection (Chapter 4), Resilience (Chapter 12),
and comprehensive Observability (Chapter 11/19).

Key Enhancements:
- Dependency Injection: AgentFactory, MCPManager, VectorStore injected by WorkflowFactory
- Unified Agent Execution: All execution via AgentFactory with tool calling
- Reflection Pattern: Producer-Critic architecture with critique_and_validate_node
- Closed-Loop Feedback: Retry node incorporates critique/HITL feedback
- Observability: Callback merging for comprehensive monitoring
- Resilience: Robust error handling throughout
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from langchain_core.runnables.config import RunnableConfig
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage

# Core State Management
from .graph_state import (
    WorkflowState,
    WorkflowStatus,
    ClassificationType,
    HandoffSummary,
    create_handoff_summary
)

# Context Management
from .context_synthesis import assemble_context_package

# Type hints for injected dependencies
from core.agents.factory import AgentFactory
from langchain_core.vectorstores import VectorStore

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Node Execution (Direct Tool Calls Without Agent)
# =============================================================================

async def execute_tool_node(
    state: WorkflowState,
    config: RunnableConfig,
    # Node-specific configuration
    node_tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute a tool directly without an agent wrapper.

    This allows workflows to have dedicated tool nodes for deterministic operations
    that don't require LLM reasoning (e.g., API calls, notifications, data transforms).

    Based on LangChain documentation: https://docs.langchain.com/oss/python/langchain/tools

    Args:
        state: Current workflow state
        config: LangGraph runtime configuration
        node_tool_config: Tool configuration from the node

    Returns:
        State updates with tool execution results
    """
    task_id = state.get("task_id", 0)
    logger.info(f"[TOOL_NODE] Starting tool execution for task {task_id}")

    if not node_tool_config:
        error_msg = "Tool node configuration is missing"
        logger.error(f"[TOOL_NODE] {error_msg}")
        return {
            **_update_status(WorkflowStatus.FAILED_EXECUTION, "execute_tool", error_msg),
            "execution_failed": True
        }

    tool_type = node_tool_config.get("tool_type")  # "mcp", "cli", or "custom"
    tool_id = node_tool_config.get("tool_id")
    tool_params = node_tool_config.get("tool_params", {})

    logger.info(f"[TOOL_NODE] Tool type: {tool_type}, Tool ID: {tool_id}, Params: {tool_params}")

    try:
        # Load the tool based on type
        tool = None

        if tool_type == "custom":
            # Load custom tool from database
            from core.agents.factory import AgentFactory
            project_id = state.get("project_id", 0)
            custom_tools = await AgentFactory._load_custom_tools([tool_id], project_id)

            if not custom_tools:
                raise ValueError(f"Custom tool '{tool_id}' not found")

            tool = custom_tools[0]
            logger.info(f"[TOOL_NODE] Loaded custom tool: {tool.name}")

        elif tool_type == "mcp":
            # Load MCP tool
            from tools.native_tools import load_native_tools
            mcp_tools = load_native_tools([tool_id])

            if not mcp_tools:
                raise ValueError(f"MCP tool '{tool_id}' not found")

            tool = mcp_tools[0]
            logger.info(f"[TOOL_NODE] Loaded MCP tool: {tool.name}")

        elif tool_type == "cli":
            # Load CLI tool
            from core.agents.factory import AgentFactory
            cli_tools = await AgentFactory._load_cli_tools([tool_id])

            if not cli_tools:
                raise ValueError(f"CLI tool '{tool_id}' not found")

            tool = cli_tools[0]
            logger.info(f"[TOOL_NODE] Loaded CLI tool: {tool.name}")
        else:
            raise ValueError(f"Unknown tool type: {tool_type}")

        # Execute the tool with parameters
        logger.info(f"[TOOL_NODE] Executing tool '{tool.name}' with params: {tool_params}")

        # Call tool (handles both sync and async)
        if hasattr(tool, 'ainvoke'):
            result = await tool.ainvoke(tool_params)
        elif hasattr(tool, 'invoke'):
            result = tool.invoke(tool_params)
        else:
            # Fallback: call as function
            result = await tool(**tool_params) if asyncio.iscoroutinefunction(tool) else tool(**tool_params)

        logger.info(f"[TOOL_NODE] Tool execution successful. Result: {str(result)[:200]}...")

        # Update state with tool result
        return {
            **_update_status(WorkflowStatus.EXECUTING, "execute_tool"),
            "tool_result": result,
            "last_tool_output": str(result)
        }

    except Exception as e:
        error_msg = f"Tool execution failed: {str(e)}"
        logger.error(f"[TOOL_NODE] {error_msg}", exc_info=True)
        return {
            **_update_status(WorkflowStatus.FAILED_EXECUTION, "execute_tool", error_msg),
            "execution_failed": True,
            "tool_error": str(e)
        }


# =============================================================================
# Helper Functions
# =============================================================================

def _update_status(
    status: WorkflowStatus,
    current_step: str,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Helper to standardize status updates returned by nodes.

    Args:
        status: New workflow status
        current_step: Current execution step identifier
        error: Optional error message

    Returns:
        State update dictionary
    """
    updates = {
        "workflow_status": status,
        "current_step": current_step,
    }
    if error:
        updates["error_message"] = error
    return updates


def _extract_agent_handoff(
    task_id: int,
    attempt: int,
    messages: List[BaseMessage]
) -> HandoffSummary:
    """
    Analyze agent's message history to synthesize a HandoffSummary.

    This implements Chapter 7 (Standardized Handoff), extracting actions taken,
    tool usage, and final response from the agent's execution history.

    Args:
        task_id: Task identifier
        attempt: Retry attempt number
        messages: Agent message history

    Returns:
        Structured handoff summary
    """
    actions_taken = []
    final_response = ""

    if messages:
        # The last message is typically the final answer from the agent
        final_response = getattr(messages[-1], 'content', '')

        # Iterate through messages to find tool invocations (Actions Taken)
        for msg in messages:
            # Check for tool calls (standard in modern LangChain Tool Calling Agents)
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for call in msg.tool_calls:
                    tool_name = call.get("name")
                    # Provide a concise summary of the action
                    args_keys = list(call.get('args', {}).keys())
                    actions_taken.append(f"Used tool: {tool_name} (Args: {args_keys})")

    # Use the final response as the rationale/summary
    return create_handoff_summary(
        task_id=task_id,
        attempt=attempt,
        actions_taken=actions_taken or ["Agent analyzed request (No tools used)."],
        # Truncate rationale if excessively long
        rationale=final_response[:2000] + ("..." if len(final_response) > 2000 else ""),
        pending_items=[],
        status="SUCCESS"  # Assume success if the agent finished without raising an exception
    )


def _merge_callbacks(
    runtime_callbacks: Optional[Any],
    factory_callbacks: Optional[List[Any]]
) -> List[Any]:
    """
    Merge callbacks from runtime config and AgentFactory.

    This ensures both workflow monitoring (ExecutionEventCallbackHandler)
    and agent-specific tracing (LangFuse) are active during execution.

    Args:
        runtime_callbacks: Callbacks from RunnableConfig
        factory_callbacks: Callbacks from AgentFactory

    Returns:
        Combined list of callbacks
    """
    merged = []

    if runtime_callbacks:
        # Ensure runtime_callbacks (from config) is a list
        if isinstance(runtime_callbacks, list):
            merged.extend(runtime_callbacks)
        else:
            # Handle case where it might be a single handler object
            merged.append(runtime_callbacks)

    if factory_callbacks:
        merged.extend(factory_callbacks)

    return merged


# =============================================================================
# Workflow Nodes
# =============================================================================

async def initialize_workflow_node(
    state: WorkflowState,
    config: RunnableConfig
) -> Dict[str, Any]:
    """
    Initialize the workflow state.

    This node handles:
    - Workflow ID assignment from LangGraph thread ID
    - Basic validation of required state fields
    - Start timestamp initialization

    Args:
        state: Current workflow state
        config: LangGraph runtime configuration

    Returns:
        State updates dictionary
    """
    logger.info(f"[NODE: Initialize] Task {state.get('task_id')}")

    updates = _update_status(WorkflowStatus.PLANNING, "initialize")

    # Assign Workflow ID from LangGraph thread ID (Essential for Checkpointing)
    thread_id = config.get("configurable", {}).get("thread_id")
    if thread_id:
        updates["workflow_id"] = thread_id

    # Set start time if not present
    if not state.get("started_at"):
        updates["started_at"] = datetime.utcnow()

    # Basic validation (Resilience)
    if not state.get('task_id') or not state.get('current_directive'):
        error_msg = "Missing required initial state fields (task_id or directive)."
        return {
            **_update_status(WorkflowStatus.TERMINATED, "initialize", error_msg),
            "workflow_initialized": False
        }

    updates["workflow_initialized"] = True
    return updates


async def execute_code_node(
    state: WorkflowState,
    config: RunnableConfig,
    # Dependencies injected by the WorkflowFactory/DynamicExecutor
    agent_factory: AgentFactory,
    mcp_manager: Optional[Any] = None,
    vector_store: Optional[VectorStore] = None,
    # Node-specific configuration (from Blueprint)
    node_agent_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute the primary task using AgentFactory (The "Producer" agent).

    This implements the Producer role in the Reflection pattern, creating
    and executing an agent to complete the task directive.

    Dependencies are injected by the WorkflowFactory for loose coupling.

    Args:
        state: Current workflow state
        config: LangGraph runtime configuration
        agent_factory: Injected AgentFactory for agent creation
        mcp_manager: Injected MCP Manager for tool access
        vector_store: Injected vector store for memory
        node_agent_config: Agent configuration from blueprint

    Returns:
        State updates with execution results and handoff summary
    """
    task_id = state.get('task_id')
    logger.info(f"[NODE: Execute] Task {task_id}. Attempt {state.get('retry_count', 0) + 1}.")

    if not node_agent_config:
        error_msg = "Agent configuration missing in blueprint node."
        return {
            **_update_status(WorkflowStatus.FAILED_EXECUTION, "execute_code", error_msg),
            "execution_failed": True
        }

    # 1. Assemble Context Package
    try:
        context_package = await assemble_context_package(state)
    except Exception as e:
        error_msg = f"Context assembly failed: {e}"
        return {
            **_update_status(WorkflowStatus.FAILED_EXECUTION, "execute_code", error_msg),
            "execution_failed": True
        }

    # 2. Update Status
    updates = _update_status(WorkflowStatus.EXECUTING, "execute_code")

    # 3. Create Agent Instance
    try:
        # The Factory handles tools, memory, model selection, and context injection
        agent_graph, tools, factory_callbacks = await agent_factory.create_agent(
            agent_config=node_agent_config,
            project_id=state['project_id'],
            task_id=task_id,
            context=context_package,
            mcp_manager=mcp_manager,
            # Pass vector store only if memory is enabled in the config
            vector_store=vector_store if node_agent_config.get("enable_memory") else None
        )
        logger.info(
            f"Agent created. Model: {node_agent_config.get('model')}. "
            f"Tools: {len(tools)}."
        )

    except Exception as e:
        error_msg = f"Agent creation failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            **_update_status(WorkflowStatus.FAILED_EXECUTION, "execute_code", error_msg),
            "execution_failed": True
        }

    # 4. Execute Agent
    try:
        directive = state['current_directive']

        # Execute without custom callbacks for compatibility
        # Get recursion limit from agent config or use default
        recursion_limit = agent_config.get("recursion_limit", 50)
        agent_result = await agent_graph.ainvoke(
            {"messages": [HumanMessage(content=directive)]},
            config={"recursion_limit": recursion_limit}
        )

        logger.info("✓ Agent execution completed.")

        # 5. Process Handoff (Chapter 7)
        messages = agent_result.get("messages", [])
        latest_handoff = _extract_agent_handoff(
            task_id,
            state.get("retry_count", 0) + 1,
            messages
        )

        # Determine next status (Check for mandatory HITL in config - Chapter 13)
        next_status = WorkflowStatus.PASSED
        if node_agent_config.get("requires_human_approval", False):
            next_status = WorkflowStatus.AWAITING_HITL
            logger.info("Execution complete. Agent configuration requires HITL approval.")

        return {
            **_update_status(next_status, "execute_code"),
            "execution_successful": True,
            "latest_handoff": latest_handoff,
            "agent_execution_history": messages  # Store history for the Critic
        }

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        error_msg = f"Execution error: {type(e).__name__} - {e}"
        return {
            **_update_status(WorkflowStatus.FAILED_EXECUTION, "execute_code", error_msg),
            "execution_failed": True
        }


async def critique_and_validate_node(
    state: WorkflowState,
    config: RunnableConfig,
    # Dependencies injected
    agent_factory: AgentFactory,
    mcp_manager: Optional[Any] = None,
    vector_store: Optional[VectorStore] = None,
    # Node-specific configuration (from Blueprint)
    critic_agent_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Reflection Pattern (Chapter 4) - The "Critic" agent reviews the Producer's output.

    This implements the Critic role, creating a separate agent to validate
    the work of the execution agent. The critic can use tools for rigorous
    validation (linting, testing, analysis).

    Args:
        state: Current workflow state
        config: LangGraph runtime configuration
        agent_factory: Injected AgentFactory for critic agent creation
        mcp_manager: Injected MCP Manager for tool access
        vector_store: Injected vector store for memory
        critic_agent_config: Critic agent configuration from blueprint

    Returns:
        State updates with validation decision and critique
    """
    task_id = state.get('task_id')
    logger.info(f"[NODE: Critique & Validate] Task {task_id}.")

    if not critic_agent_config:
        logger.warning(
            "Critic agent configuration missing. "
            "Skipping reflection and passing validation."
        )
        return {
            **_update_status(WorkflowStatus.PASSED, "critique_validate"),
            "validation_passed": True
        }

    # 1. Prepare Context for the Critic
    try:
        # The critic needs the history/scratchpad from the previous agent
        context_package = await assemble_context_package(state)
    except Exception as e:
        return {
            **_update_status(
                WorkflowStatus.FAILED_VALIDATION,
                "critique_validate",
                f"Context error: {e}"
            ),
            "validation_failed": True
        }

    # 2. Update Status
    updates = _update_status(WorkflowStatus.VALIDATING, "critique_validate")

    # 3. Create Critic Agent Instance
    try:
        critic_graph, _, factory_callbacks = await agent_factory.create_agent(
            agent_config=critic_agent_config,
            project_id=state['project_id'],
            task_id=f"{task_id}_critic",
            context=context_package,
            mcp_manager=mcp_manager,
            vector_store=vector_store  # Critic benefits from memory
        )
    except Exception as e:
        logger.error(f"Critic agent creation failed: {e}")
        return {
            **_update_status(
                WorkflowStatus.FAILED_VALIDATION,
                "critique_validate",
                f"Agent creation error: {e}"
            ),
            "validation_failed": True
        }

    # 4. Define the Critique Directive
    directive = f"""Analyze the recent execution history (provided in the context scratchpad) for the task: '{state.get('original_directive')}'.

Your goal is to validate the work done by the previous agent.

1. Review the actions taken and the final output.
2. If applicable, use your tools (e.g., linting, tests, analysis) to rigorously validate the changes.
3. Provide a detailed critique of the work quality, adherence to requirements, and potential issues.
4. Conclude your response with a clear decision marker:
   - [DECISION: PASS] if work meets requirements
   - [DECISION: FAIL_RETRY] if fixable issues found
   - [DECISION: HITL_REQUIRED] if critical/ambiguous issues require human review"""

    # 5. Execute Critic Agent
    try:
        # Execute without custom callbacks for compatibility
        # Get recursion limit from agent config or use default
        recursion_limit = agent_config.get("recursion_limit", 50)
        critic_result = await critic_graph.ainvoke(
            {"messages": [HumanMessage(content=directive)]},
            config={"recursion_limit": recursion_limit}
        )

        # 6. Process Critique Results
        messages = critic_result.get("messages", [])
        critique_text = getattr(messages[-1], 'content', '') if messages else "No critique generated."

        # Analyze the decision marker
        decision = "FAIL_RETRY"  # Default to fail if unclear
        if "[DECISION: PASS]" in critique_text:
            decision = "PASS"
        elif "[DECISION: HITL_REQUIRED]" in critique_text:
            decision = "HITL_REQUIRED"

        logger.info(f"✓ Critique completed. Decision: {decision}.")

        validation_report = {"critique": critique_text, "decision": decision}

        # 7. Update State based on Decision
        if decision == "PASS":
            return {
                **_update_status(WorkflowStatus.PASSED, "critique_validate"),
                "validation_passed": True,
                "validation_report": validation_report
            }
        elif decision == "HITL_REQUIRED":
            return {
                **_update_status(WorkflowStatus.AWAITING_HITL, "critique_validate"),
                "validation_failed": True,
                "needs_hitl": True,
                "validation_report": validation_report
            }
        else:  # FAIL_RETRY
            return {
                **_update_status(WorkflowStatus.FAILED_VALIDATION, "critique_validate"),
                "validation_failed": True,
                "needs_hitl": False,
                "validation_report": validation_report
            }

    except Exception as e:
        error_msg = f"Critique execution error: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            **_update_status(
                WorkflowStatus.FAILED_VALIDATION,
                "critique_validate",
                error_msg
            ),
            "validation_failed": True
        }


async def handle_hitl_node(
    state: WorkflowState,
    config: RunnableConfig
) -> Dict[str, Any]:
    """
    Process human decision after HITL interrupt (Chapter 13/18).

    NOTE: LangGraph interrupts BEFORE this node. This node executes upon resumption
    with the human's decision injected into the state.

    Args:
        state: Current workflow state (should include hitl_response)
        config: LangGraph runtime configuration

    Returns:
        State updates based on human decision
    """
    logger.info(f"[NODE: Handle HITL] Resumed after interrupt. Processing decision.")

    # The human response should be injected into the state during the resume API call
    hitl_response = state.get("hitl_response")

    if not hitl_response:
        # Robustness: Handle case where resumption occurred without input
        logger.error("HITL node executed without a human response in state.")
        return {
            **_update_status(
                WorkflowStatus.FAILED_EXECUTION,
                "handle_hitl",
                "Missing HITL response."
            ),
            "hitl_failed": True
        }

    decision = hitl_response.get("decision", "reject").lower()
    feedback = hitl_response.get("feedback", "")

    logger.info(f"HITL Decision: {decision.upper()}.")

    if decision == "approve":
        return {
            **_update_status(WorkflowStatus.PASSED, "handle_hitl"),
            "hitl_completed": True,
            "hitl_decision": "approve"
        }
    elif decision == "retry":
        # The retry node will handle updating the directive with feedback
        return {
            # Status update handled in the retry node
            "hitl_completed": True,
            "hitl_decision": "retry",
            "hitl_feedback": feedback
        }
    else:  # Reject/Fail
        return {
            **_update_status(WorkflowStatus.TERMINATED, "handle_hitl"),
            "hitl_completed": True,
            "hitl_decision": "reject",
            "workflow_terminated": True
        }


async def retry_workflow_node(
    state: WorkflowState,
    config: RunnableConfig
) -> Dict[str, Any]:
    """
    Handle workflow retry logic, incorporating feedback (Closing the Reflection loop).

    This implements Chapter 12 (Resilience) by managing retry limits and
    Chapter 4 (Reflection) by incorporating critique feedback into the
    next attempt's directive.

    Args:
        state: Current workflow state
        config: LangGraph runtime configuration

    Returns:
        State updates for retry initialization
    """
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if retry_count >= max_retries:
        logger.warning(f"Max retries ({max_retries}) exceeded.")
        return {
            **_update_status(WorkflowStatus.TERMINATED, "retry_exceeded"),
            "retry_exceeded": True,
            "workflow_terminated": True
        }

    # Incorporate Feedback (Reflection - Closing the Loop)
    feedback = ""

    # Prioritize HITL feedback if available (set by handle_hitl_node)
    if state.get("hitl_feedback"):
        feedback = f"HUMAN FEEDBACK (HITL):\n{state.get('hitl_feedback')}\n"
    # Otherwise use the Critic agent's report (set by critique_and_validate_node)
    elif state.get("validation_report") and state["validation_report"].get("critique"):
        feedback = f"CRITIC AGENT FEEDBACK:\n{state['validation_report']['critique']}\n"
    # Otherwise use the raw error message (set by execute_code_node failure)
    elif state.get("error_message"):
        feedback = f"EXECUTION ERROR DETAILS:\n{state.get('error_message')}\n"

    # Update the directive with feedback
    if feedback:
        updated_directive = (
            f"{state.get('original_directive')}\n\n"
            f"--- IMPORTANT FEEDBACK FOR RETRY ---\n"
            f"{feedback}"
            f"--- END FEEDBACK ---"
        )
    else:
        updated_directive = state.get('original_directive')

    # Reset state for the next attempt
    updates = {
        "retry_count": retry_count + 1,
        "current_directive": updated_directive,
        # Clear intermediate execution data
        "agent_execution_history": [],
        "validation_report": None,
        "latest_handoff": None,
        "error_message": None,
        "hitl_response": None,
        "hitl_feedback": None,
    }

    logger.info(f"Initializing retry attempt {retry_count + 1}.")

    return {
        **_update_status(WorkflowStatus.PLANNING, "retry_initialize"),
        **updates,
        "retry_initialized": True
    }


async def complete_workflow_node(
    state: WorkflowState,
    config: RunnableConfig
) -> Dict[str, Any]:
    """
    Finalize the workflow.

    This node handles:
    - Setting final workflow status
    - Calculating execution duration
    - Preparing final results

    Args:
        state: Current workflow state
        config: LangGraph runtime configuration

    Returns:
        State updates with completion metadata
    """
    logger.info(f"[NODE: Complete] Finalizing workflow.")

    # Determine final status
    current_status = state.get("workflow_status")
    if current_status in [WorkflowStatus.PASSED, WorkflowStatus.HITL_APPROVED]:
        final_status = WorkflowStatus.PASSED
    elif current_status in [WorkflowStatus.TERMINATED, WorkflowStatus.FAILED_EXECUTION, WorkflowStatus.FAILED_VALIDATION]:
        final_status = current_status
    else:
        # Handle unexpected states reaching completion
        logger.warning(
            f"Workflow reached completion node with unexpected status: {current_status}. Treating as PASSED."
        )
        final_status = WorkflowStatus.PASSED

    updates = _update_status(final_status, "completed")

    # Calculate duration
    duration = None
    completed_at = datetime.utcnow()
    started_at = state.get("started_at")
    if started_at and isinstance(started_at, datetime):
        duration = (completed_at - started_at).total_seconds()

    duration_str = f"{duration:.2f}s" if duration else "N/A"
    logger.info(
        f"Workflow finished. Status: {final_status}. "
        f"Duration: {duration_str}."
    )

    updates["workflow_completed"] = True
    updates["completed_at"] = completed_at
    updates["execution_duration_seconds"] = duration

    return updates
