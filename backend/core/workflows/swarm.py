# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Swarm Orchestration System for LangConfig

Coordinates multiple specialized agents working together on complex tasks.
Agents can dynamically delegate subtasks to peers based on capabilities.

Architecture:
- SwarmCoordinator: Manages a pool of agents and task queue
- Task decomposition via Supreme Commander
- Dynamic routing via Agent Delegation System
- Context continuity via existing HandoffSummary system

Example Flow:
1. User submits: "Build a REST API with authentication"
2. Supreme Commander decomposes into subtasks
3. Swarm routes each subtask to specialized agent
4. Agents collaborate and hand off context
5. Results aggregated and returned
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .agent_delegation import (
    AgentCapability,
    AgentRegistry,
    DelegationBroker,
    DelegationRequest,
    DelegationResult,
    get_agent_registry,
    get_delegation_broker
)
from .graph_state import HandoffSummary, create_handoff_summary

logger = logging.getLogger(__name__)


# =============================================================================
# SWARM MODELS
# =============================================================================

class TaskStatus(str, Enum):
    """Status of a task in the swarm queue."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DELEGATED = "delegated"


@dataclass
class SwarmTask:
    """A task in the swarm workflow."""
    task_id: str
    description: str
    required_capabilities: Set[AgentCapability]

    # Task relationships
    depends_on: List[str] = field(default_factory=list)  # Task IDs this depends on
    parent_task_id: Optional[str] = None  # Parent task if this is a subtask

    # Execution
    assigned_agent_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5  # 1-10

    # Results
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    handoff_summary: Optional[HandoffSummary] = None

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Context
    input_context: Dict[str, Any] = field(default_factory=dict)
    output_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmWorkflow:
    """A complete swarm workflow with multiple tasks."""
    workflow_id: str
    description: str
    source_task_id: int  # Original LangConfig task ID

    tasks: Dict[str, SwarmTask] = field(default_factory=dict)
    task_order: List[str] = field(default_factory=list)  # Execution order

    status: str = "active"  # active, completed, failed

    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Aggregate results
    final_result: Optional[Dict[str, Any]] = None
    all_handoffs: List[HandoffSummary] = field(default_factory=list)


# =============================================================================
# SWARM COORDINATOR
# =============================================================================

class SwarmCoordinator:
    """
    Coordinates multiple agents working together on complex workflows.

    Features:
    - Task decomposition and dependency management
    - Dynamic agent selection and load balancing
    - Context aggregation across agents
    - Failure handling and recovery
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        broker: Optional[DelegationBroker] = None,
        max_concurrent_tasks: int = 10
    ):
        self.registry = registry or get_agent_registry()
        self.broker = broker or get_delegation_broker()
        self.max_concurrent_tasks = max_concurrent_tasks

        self._active_workflows: Dict[str, SwarmWorkflow] = {}
        self._task_semaphore = asyncio.Semaphore(max_concurrent_tasks)

    def create_workflow(
        self,
        workflow_id: str,
        description: str,
        source_task_id: int,
        tasks: List[SwarmTask]
    ) -> SwarmWorkflow:
        """Create a new swarm workflow with multiple tasks."""
        workflow = SwarmWorkflow(
            workflow_id=workflow_id,
            description=description,
            source_task_id=source_task_id,
            tasks={task.task_id: task for task in tasks},
            task_order=[task.task_id for task in tasks]
        )

        self._active_workflows[workflow_id] = workflow
        logger.info(f"Created swarm workflow {workflow_id} with {len(tasks)} tasks")

        return workflow

    async def execute_workflow(
        self,
        workflow: SwarmWorkflow,
        workflow_context: Dict[str, Any]
    ) -> SwarmWorkflow:
        """
        Execute a swarm workflow with dependency-aware task execution.

        Tasks are executed in order, respecting dependencies.
        Context flows from task to task via handoff summaries.
        """
        logger.info(f"Starting swarm workflow {workflow.workflow_id}")

        try:
            # Build dependency graph
            dependency_graph = self._build_dependency_graph(workflow)

            # Execute tasks in topological order
            execution_order = self._topological_sort(dependency_graph)

            logger.info(f"Execution order: {execution_order}")

            # Accumulated context from all previous tasks
            accumulated_context = workflow_context.copy()

            for task_id in execution_order:
                task = workflow.tasks[task_id]

                # Check if dependencies are completed
                if not self._dependencies_met(task, workflow):
                    logger.error(f"Dependencies not met for task {task_id}")
                    task.status = TaskStatus.FAILED
                    task.error = "Dependencies not satisfied"
                    continue

                # Update task context with results from dependencies
                for dep_id in task.depends_on:
                    dep_task = workflow.tasks[dep_id]
                    if dep_task.output_context:
                        accumulated_context.update(dep_task.output_context)

                # Execute task
                result = await self._execute_task(task, accumulated_context, workflow.source_task_id)

                # Update accumulated context
                if result.status == "SUCCESS" and result.result:
                    accumulated_context.update(result.result)
                    task.output_context = result.result

                    # Store handoff summary
                    if result.handoff_summary:
                        handoff = create_handoff_summary(
                            task_id=workflow.source_task_id,
                            attempt=1,
                            actions_taken=result.handoff_summary.get("actions_taken", []),
                            rationale=result.handoff_summary.get("rationale", ""),
                            pending_items=result.handoff_summary.get("pending_items", []),
                            status=result.handoff_summary.get("status", "SUCCESS")
                        )
                        task.handoff_summary = handoff
                        workflow.all_handoffs.append(handoff)

                # Check for failure
                if result.status != "SUCCESS":
                    logger.error(f"Task {task_id} failed: {result.error}")
                    workflow.status = "failed"
                    break

            # Mark workflow as completed if all tasks succeeded
            if all(t.status == TaskStatus.COMPLETED for t in workflow.tasks.values()):
                workflow.status = "completed"
                workflow.completed_at = datetime.utcnow()
                workflow.final_result = accumulated_context
                logger.info(f"Swarm workflow {workflow.workflow_id} completed successfully")
            else:
                workflow.status = "failed"
                logger.error(f"Swarm workflow {workflow.workflow_id} failed")

            return workflow

        except Exception as e:
            logger.error(f"Swarm workflow {workflow.workflow_id} error: {e}")
            workflow.status = "failed"
            return workflow

    async def _execute_task(
        self,
        task: SwarmTask,
        context: Dict[str, Any],
        source_task_id: int
    ) -> DelegationResult:
        """Execute a single swarm task via delegation."""
        logger.info(f"Executing swarm task {task.task_id}: {task.description}")

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()

        # Create delegation request
        delegation_request = DelegationRequest(
            request_id=f"swarm_{task.task_id}",
            task_description=task.description,
            required_capabilities=task.required_capabilities,
            source_task_id=source_task_id,
            source_agent_id="swarm_coordinator",
            workflow_context=context,
            priority=task.priority
        )

        # Delegate to appropriate agent
        async with self._task_semaphore:  # Limit concurrency
            result = await self.broker.delegate_with_retry(delegation_request)

        # Update task based on result
        task.completed_at = datetime.utcnow()

        if result.status == "SUCCESS":
            task.status = TaskStatus.COMPLETED
            task.result = result.result
            task.assigned_agent_id = result.agent_id
        else:
            task.status = TaskStatus.FAILED
            task.error = result.error

        return result

    def _build_dependency_graph(self, workflow: SwarmWorkflow) -> Dict[str, List[str]]:
        """Build adjacency list for task dependencies."""
        graph = {task_id: [] for task_id in workflow.tasks}

        for task_id, task in workflow.tasks.items():
            for dep_id in task.depends_on:
                if dep_id in graph:
                    graph[dep_id].append(task_id)

        return graph

    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """
        Perform topological sort on dependency graph.

        Returns execution order that respects dependencies.
        """
        # Calculate in-degrees
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] += 1

        # Queue nodes with no dependencies
        queue = [node for node in graph if in_degree[node] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # Reduce in-degree for neighbors
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(result) != len(graph):
            raise ValueError("Circular dependency detected in workflow")

        return result

    def _dependencies_met(self, task: SwarmTask, workflow: SwarmWorkflow) -> bool:
        """Check if all dependencies for a task are completed."""
        for dep_id in task.depends_on:
            dep_task = workflow.tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True

    def get_workflow(self, workflow_id: str) -> Optional[SwarmWorkflow]:
        """Get workflow by ID."""
        return self._active_workflows.get(workflow_id)

    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a workflow."""
        workflow = self._active_workflows.get(workflow_id)
        if not workflow:
            return None

        task_statuses = {
            task_id: {
                "status": task.status.value,
                "assigned_agent": task.assigned_agent_id,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            }
            for task_id, task in workflow.tasks.items()
        }

        return {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status,
            "total_tasks": len(workflow.tasks),
            "completed_tasks": sum(1 for t in workflow.tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed_tasks": sum(1 for t in workflow.tasks.values() if t.status == TaskStatus.FAILED),
            "task_statuses": task_statuses,
            "handoff_count": len(workflow.all_handoffs)
        }


# =============================================================================
# SUPREME COMMANDER INTEGRATION
# =============================================================================

async def decompose_goal_with_supreme_commander(
    goal: str,
    context: Dict[str, Any]
) -> List[SwarmTask]:
    """
    Use Supreme Commander to decompose a complex goal into swarm tasks.

    This is a placeholder - integrate with your actual Supreme Commander service.
    """
    from services.supreme_commander import SupremeCommanderService

    # Call Supreme Commander to decompose goal
    # NOTE: You'll need to adapt this to your actual Supreme Commander interface
    commander = SupremeCommanderService()

    try:
        execution_plan = await commander.decompose_goal(goal, context)

        # Convert execution plan steps to swarm tasks
        swarm_tasks = []
        for idx, step in enumerate(execution_plan.get("steps", [])):
            # Map step to capabilities (you'll need to enhance this)
            capabilities = _infer_capabilities_from_step(step)

            task = SwarmTask(
                task_id=f"task_{idx}",
                description=step.get("description", ""),
                required_capabilities=capabilities,
                depends_on=step.get("dependencies", []),
                priority=step.get("priority", 5),
                input_context=step.get("context", {})
            )
            swarm_tasks.append(task)

        logger.info(f"Supreme Commander decomposed goal into {len(swarm_tasks)} tasks")
        return swarm_tasks

    except Exception as e:
        logger.error(f"Supreme Commander decomposition failed: {e}")
        # Fallback: create a single task
        return [
            SwarmTask(
                task_id="task_0",
                description=goal,
                required_capabilities={AgentCapability.CODE_GENERATION},
                priority=5
            )
        ]


def _infer_capabilities_from_step(step: Dict[str, Any]) -> Set[AgentCapability]:
    """
    Infer required capabilities from a Supreme Commander step.

    This is a simple heuristic - you can make it more sophisticated.
    """
    description = step.get("description", "").lower()
    capabilities = set()

    # Keyword matching
    if "test" in description:
        capabilities.add(AgentCapability.TESTING)
    if "review" in description or "audit" in description:
        capabilities.add(AgentCapability.CODE_REVIEW)
    if "refactor" in description:
        capabilities.add(AgentCapability.REFACTORING)
    if "devops" in description or "deploy" in description:
        capabilities.add(AgentCapability.DEVOPS)
    if "document" in description:
        capabilities.add(AgentCapability.DOCUMENTATION)
    if "api" in description:
        capabilities.add(AgentCapability.API_DESIGN)

    # Default to code generation if nothing matched
    if not capabilities:
        capabilities.add(AgentCapability.CODE_GENERATION)

    return capabilities


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def execute_swarm_workflow_from_goal(
    goal: str,
    source_task_id: int,
    workflow_context: Dict[str, Any],
    coordinator: Optional[SwarmCoordinator] = None
) -> SwarmWorkflow:
    """
    High-level function to execute a swarm workflow from a goal.

    Example:
        result = await execute_swarm_workflow_from_goal(
            goal="Build a REST API with authentication",
            source_task_id=123,
            workflow_context={"project_id": 456, "stack": "FastAPI"}
        )
    """
    coordinator = coordinator or SwarmCoordinator()

    # Decompose goal into tasks
    tasks = await decompose_goal_with_supreme_commander(goal, workflow_context)

    # Create workflow
    workflow = coordinator.create_workflow(
        workflow_id=f"swarm_{source_task_id}_{int(datetime.utcnow().timestamp())}",
        description=goal,
        source_task_id=source_task_id,
        tasks=tasks
    )

    # Execute workflow
    result = await coordinator.execute_workflow(workflow, workflow_context)

    return result


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

async def example_swarm_workflow():
    """
    Example of setting up and running a swarm workflow.

    This demonstrates:
    1. Creating specialized agents
    2. Registering them in the registry
    3. Creating a workflow with dependencies
    4. Executing the workflow with automatic delegation
    """
    from .agent_delegation import register_agent_from_template, AgentProfile

    # Step 1: Register specialized agents
    # (In production, these would be registered at startup)

    async def code_writer_handler(request: DelegationRequest) -> Dict[str, Any]:
        """Simulated code writer agent."""
        logger.info(f"Code Writer executing: {request.task_description}")
        await asyncio.sleep(1)  # Simulate work
        return {
            "code_generated": True,
            "files": ["main.py", "utils.py"],
            "handoff_summary": {
                "actions_taken": ["Generated code files"],
                "rationale": "Implemented requested functionality",
                "pending_items": ["Needs testing"],
                "status": "SUCCESS"
            }
        }

    async def test_writer_handler(request: DelegationRequest) -> Dict[str, Any]:
        """Simulated test writer agent."""
        logger.info(f"Test Writer executing: {request.task_description}")
        await asyncio.sleep(1)
        return {
            "tests_generated": True,
            "test_files": ["test_main.py"],
            "handoff_summary": {
                "actions_taken": ["Generated test files"],
                "rationale": "Created comprehensive test suite",
                "pending_items": [],
                "status": "SUCCESS"
            }
        }

    async def reviewer_handler(request: DelegationRequest) -> Dict[str, Any]:
        """Simulated code reviewer agent."""
        logger.info(f"Reviewer executing: {request.task_description}")
        await asyncio.sleep(1)
        return {
            "review_complete": True,
            "issues_found": 0,
            "handoff_summary": {
                "actions_taken": ["Reviewed code and tests"],
                "rationale": "Code quality is good",
                "pending_items": [],
                "status": "SUCCESS"
            }
        }

    # Register agents
    register_agent_from_template("code_writer", "aider_code_writer", code_writer_handler)
    register_agent_from_template("test_writer", "test_generator", test_writer_handler)
    register_agent_from_template("reviewer", "code_reviewer", reviewer_handler)

    # Step 2: Create swarm workflow with dependencies
    tasks = [
        SwarmTask(
            task_id="write_code",
            description="Write REST API endpoints",
            required_capabilities={AgentCapability.CODE_GENERATION, AgentCapability.API_DESIGN},
            priority=10
        ),
        SwarmTask(
            task_id="write_tests",
            description="Write tests for API endpoints",
            required_capabilities={AgentCapability.TESTING},
            depends_on=["write_code"],  # Depends on code being written first
            priority=8
        ),
        SwarmTask(
            task_id="review_code",
            description="Review code and tests for quality",
            required_capabilities={AgentCapability.CODE_REVIEW},
            depends_on=["write_code", "write_tests"],  # Depends on both
            priority=5
        )
    ]

    # Step 3: Execute workflow
    coordinator = SwarmCoordinator()

    workflow = coordinator.create_workflow(
        workflow_id="demo_workflow",
        description="Build REST API with tests",
        source_task_id=999,
        tasks=tasks
    )

    context = {
        "project_id": 123,
        "framework": "FastAPI",
        "requirements": "Authentication endpoints"
    }

    result = await coordinator.execute_workflow(workflow, context)

    # Step 4: Check results
    status = coordinator.get_workflow_status("demo_workflow")
    logger.info(f"Workflow Status: {status}")

    return result


# Entry point for testing
if __name__ == "__main__":
    # Run example
    asyncio.run(example_swarm_workflow())
