# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Supervisor Pattern Implementation for LangConfig.

Supervisors are agents that:
1. Analyze incoming tasks
2. Delegate to specialized worker agents
3. Aggregate results
4. Make routing decisions

This implements TRUE LangGraph supervisor pattern, not just sequential routing.
"""

import logging
from typing import Dict, Any, List, Optional, Literal
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_agent
from pydantic import BaseModel, Field

from core.workflows.state import WorkflowState, HandoffSummary
from core.agents.factory import AgentFactory
from core.agents.templates import AgentTemplateRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# SUPERVISOR DECISION SCHEMA
# =============================================================================

class WorkerAssignment(BaseModel):
    """Supervisor's decision about which worker to route to."""
    worker_id: str = Field(..., description="ID of the chosen worker agent")
    reasoning: str = Field(..., description="Why this worker was selected")
    task_breakdown: str = Field(..., description="Specific subtask for this worker")
    estimated_complexity: Literal["simple", "moderate", "complex"] = Field(
        ..., description="Task complexity assessment"
    )


class SupervisorDecision(BaseModel):
    """Complete supervisor decision with routing information."""
    action: Literal["delegate", "complete", "request_human"] = Field(
        ..., description="Next action to take"
    )
    assignment: Optional[WorkerAssignment] = Field(
        None, description="Worker assignment if action is 'delegate'"
    )
    completion_summary: Optional[str] = Field(
        None, description="Final summary if action is 'complete'"
    )
    human_request_reason: Optional[str] = Field(
        None, description="Reason for HITL if action is 'request_human'"
    )


# =============================================================================
# SUPERVISOR NODE IMPLEMENTATION
# =============================================================================

async def task_supervisor_node(
    state: WorkflowState,
    config: Dict[str, Any],
    http_bridge=None
) -> WorkflowState:
    """
    Task Supervisor - Analyzes tasks and delegates to specialized workers.

    This is the CENTRAL SUPERVISOR that:
    1. Receives the user's directive
    2. Analyzes task type and complexity
    3. Selects the most appropriate specialist worker
    4. Routes to that worker

    Available Workers:
    - code_implementer: General full-stack coding
    - fast_implementer: Simple tasks, hotfixes
    - refactor_specialist: Code cleanup and refactoring
    - test_generator: Test creation
    - code_reviewer: Code review
    - architect: System design
    - devops_automation: Infrastructure tasks

    Args:
        state: Current workflow state
        config: Node configuration
        http_bridge: HTTP bridge for communication

    Returns:
        Updated state with supervisor decision
    """
    logger.info(f"🎯 Task Supervisor analyzing task {state['task_id']}")

    # Get available workers from registry
    available_workers = _get_available_workers()

    # Build supervisor prompt
    supervisor_prompt = _build_supervisor_prompt(
        directive=state["current_directive"],
        available_workers=available_workers,
        context=state.get("workflow_scratchpad", ""),
        static_context=state.get("static_context_package", "")
    )

    try:
        # Create supervisor agent (uses powerful model for routing decisions)
        supervisor_config = {
            "model": "gpt-5",  # Use powerful model for routing decisions
            "fallback_models": ["claude-sonnet-4-5-20250929"],
            "temperature": 0.3,  # Lower temp for consistent routing
            "system_prompt": supervisor_prompt,
            "mcp_tools": ["sequential_thinking"],  # For analyzing task requirements
            "enable_model_routing": False,  # Always use powerful model
            "enable_structured_output": True,
            "output_schema": SupervisorDecision,
            "enable_memory": False  # Supervisor doesn't need memory
        }

        # Create supervisor agent
        supervisor_agent, tools, callbacks = await AgentFactory.create_agent(
            agent_config=supervisor_config,
            project_id=state["project_id"],
            task_id=state["task_id"],
            context=supervisor_prompt,
            mcp_manager=config.get("mcp_manager"),
            vector_store=config.get("vector_store")
        )

        # Invoke supervisor to make routing decision
        messages = [
            HumanMessage(content=f"""Analyze this task and decide which specialist worker should handle it:

Task: {state["current_directive"]}

Current Status: {state.get("workflow_scratchpad", "Starting new task")}

Make your decision.""")
        ]

        result = await supervisor_agent.ainvoke(
            {"messages": messages},
            config={"callbacks": callbacks}
        )

        # Extract structured decision
        decision: SupervisorDecision = result["messages"][-1].content

        logger.info(
            f"📋 Supervisor Decision: action={decision.action}, "
            f"worker={decision.assignment.worker_id if decision.assignment else 'N/A'}"
        )

        # Update state with supervisor decision
        state["strategy_state"]["supervisor_decision"] = {
            "action": decision.action,
            "worker_id": decision.assignment.worker_id if decision.assignment else None,
            "reasoning": decision.assignment.reasoning if decision.assignment else decision.completion_summary,
            "task_breakdown": decision.assignment.task_breakdown if decision.assignment else None,
            "complexity": decision.assignment.estimated_complexity if decision.assignment else None
        }

        # Set next worker in state
        if decision.action == "delegate" and decision.assignment:
            state["strategy_state"]["next_worker"] = decision.assignment.worker_id
            state["current_directive"] = decision.assignment.task_breakdown  # Refined directive
        elif decision.action == "request_human":
            state["hitl_required"] = True
            state["hitl_reason"] = decision.human_request_reason

        logger.info(f"✅ Supervisor routed to: {state['strategy_state'].get('next_worker', 'COMPLETE/HITL')}")

        return state

    except Exception as e:
        logger.error(f"❌ Supervisor failed: {e}", exc_info=True)
        # Fallback to code_implementer on error
        state["strategy_state"]["next_worker"] = "code_implementer"
        state["error_message"] = f"Supervisor error (fallback to general worker): {str(e)}"
        return state


# =============================================================================
# SPECIALIZED WORKER NODES
# =============================================================================

async def specialist_worker_node(
    state: WorkflowState,
    config: Dict[str, Any],
    http_bridge=None
) -> WorkflowState:
    """
    Executes work using the specialist worker selected by supervisor.

    This node:
    1. Reads the worker_id from supervisor decision
    2. Loads that worker's template configuration
    3. Creates agent from template
    4. Executes the task
    5. Returns results to supervisor for routing decision

    Args:
        state: Current workflow state
        config: Node configuration
        http_bridge: HTTP bridge for communication

    Returns:
        Updated state with worker results
    """
    worker_id = state["strategy_state"].get("next_worker", "code_implementer")

    logger.info(f"🔧 Executing specialist worker: {worker_id}")

    # Get worker template
    worker_template = AgentTemplateRegistry.get(worker_id)
    if not worker_template:
        logger.error(f"Worker template not found: {worker_id}")
        state["error_message"] = f"Unknown worker: {worker_id}"
        state["execution_failed"] = True
        return state

    logger.info(f"Using worker: {worker_template.name} ({worker_template.category.value})")

    # Create worker agent from template
    try:
        worker_config = worker_template.to_agent_config()

        # Create full context for worker
        from core.workflows.state import get_context_for_prompt
        full_context = get_context_for_prompt(state)

        worker_agent, tools, callbacks = await AgentFactory.create_agent(
            agent_config=worker_config,
            project_id=state["project_id"],
            task_id=state["task_id"],
            context=full_context,
            mcp_manager=config.get("mcp_manager"),
            vector_store=config.get("vector_store")
        )

        # Execute worker via HTTP bridge (existing infrastructure)
        logger.info(f"🚀 Invoking worker via HTTP bridge")

        # Call existing execute_code_node logic but with specialized worker
        from core.workflows.nodes import _execute_via_http_bridge

        result = await _execute_via_http_bridge(
            state=state,
            config=config,
            http_bridge=http_bridge,
            agent_override=worker_agent,  # Use specialist worker instead of default
            callbacks_override=callbacks
        )

        # Update state with worker results
        state.update(result)

        logger.info(f"✅ Worker {worker_id} completed successfully")

        # Clear next_worker to allow supervisor to make new routing decision
        state["strategy_state"]["next_worker"] = None
        state["strategy_state"]["last_worker"] = worker_id

        return state

    except Exception as e:
        logger.error(f"Worker {worker_id} failed: {e}", exc_info=True)
        state["error_message"] = str(e)
        state["execution_failed"] = True
        return state


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_available_workers() -> List[Dict[str, Any]]:
    """Get list of available specialist workers with their capabilities."""

    # Specific worker templates that can be used as specialists
    worker_ids = [
        "code_implementer",
        "fast_implementer",
        "refactor_specialist",
        "code_reviewer",
        "test_generator",
        "architect",
        "devops_automation",
        "research_agent",
        "doc_writer"
    ]

    workers = []
    for worker_id in worker_ids:
        template = AgentTemplateRegistry.get(worker_id)
        if template:
            workers.append({
                "id": worker_id,
                "name": template.name,
                "category": template.category.value,
                "capabilities": template.capabilities,
                "description": template.description
            })

    return workers


def _build_supervisor_prompt(
    directive: str,
    available_workers: List[Dict[str, Any]],
    context: str,
    static_context: str
) -> str:
    """Build the supervisor's system prompt."""

    # Format workers for prompt
    workers_desc = "\n".join([
        f"- **{w['id']}**: {w['name']} - {w['description']}\n  "
        f"Capabilities: {', '.join(w['capabilities'][:5])}"
        for w in available_workers
    ])

    return f"""ROLE: Task Supervisor & Work Coordinator

You are the central supervisor coordinating specialized worker agents. Your job is to:
1. Analyze incoming development tasks
2. Select the most appropriate specialist worker
3. Delegate work with clear instructions
4. Track progress and re-delegate if needed

AVAILABLE SPECIALIST WORKERS:
{workers_desc}

DECISION FRAMEWORK:
- **code_implementer**: General development tasks, features, bug fixes, full-stack
- **fast_implementer**: Simple hotfixes, quick changes, CRUD operations
- **refactor_specialist**: Code cleanup, design patterns, quality improvements
- **code_reviewer**: PR reviews, code quality analysis, security checks
- **test_generator**: Unit tests, integration tests, test coverage
- **architect**: System design, architecture decisions, data modeling
- **devops_automation**: CI/CD, infrastructure, deployment (requires HITL approval)
- **research_agent**: Technical investigation, codebase analysis
- **doc_writer**: Documentation, README files, API docs

COMPLEXITY ASSESSMENT:
- **Simple**: CRUD operations, config changes, simple fixes → fast_implementer
- **Moderate**: Feature implementation, refactoring, testing → code_implementer/specialist
- **Complex**: Architecture, system design, security-critical → architect/specific specialist

PROJECT CONTEXT (from RAG/DNA):
<static_context>
{static_context[:1000] if static_context else "No static context available"}
</static_context>

WORKFLOW HISTORY:
<scratchpad>
{context[:1000] if context else "No previous work"}
</scratchpad>

OUTPUT INSTRUCTIONS:
Return a structured decision with:
- action: "delegate" (route to worker), "complete" (task done), or "request_human" (needs HITL)
- assignment: worker_id, reasoning, task_breakdown, estimated_complexity
- If complete: completion_summary
- If request_human: human_request_reason

IMPORTANT:
- Delegate to ONE specialist at a time
- Break down complex tasks into sequential specialist assignments
- Route DevOps tasks to devops_automation (auto-triggers HITL)
- If uncertain, delegate to code_implementer (generalist)
"""


# =============================================================================
# SUPERVISOR ROUTING LOGIC
# =============================================================================

def route_after_supervisor(state: WorkflowState) -> str:
    """
    Routing function for supervisor decisions.

    Returns the next node to visit based on supervisor's decision.
    """
    decision = state["strategy_state"].get("supervisor_decision", {})
    action = decision.get("action", "delegate")

    if action == "request_human":
        return "handle_hitl"
    elif action == "complete":
        return "synthesize_context"
    elif action == "delegate":
        next_worker = state["strategy_state"].get("next_worker")
        if next_worker:
            return "specialist_worker"
        else:
            # No worker assigned, go to validation
            return "synthesize_context"
    else:
        # Default to worker execution
        return "specialist_worker"


def route_after_worker(state: WorkflowState) -> str:
    """
    Routing function after worker completes.

    Returns to supervisor for next routing decision.
    """
    if state.get("execution_failed"):
        return "retry_workflow"
    elif state.get("hitl_required"):
        return "handle_hitl"
    else:
        # Return to supervisor for next decision (or completion)
        return "task_supervisor"
