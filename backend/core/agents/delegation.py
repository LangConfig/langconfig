# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Agent Delegation System for LangConfig

This module enables agent-to-agent delegation based on capabilities.
It integrates with the existing HandoffSummary system for context continuity
while adding dynamic routing to specialized agents.

Key Features:
- Agent Registry: Track available agents and their capabilities
- Capability Matching: Route tasks to agents based on required skills
- Delegation Flow: Request → Match → Execute → Return with handoff
- Integration: Works with existing LangGraph workflow and HandoffSummary
"""

import logging
from typing import Dict, List, Any, Optional, Set, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


# =============================================================================
# AGENT CAPABILITIES
# =============================================================================

class AgentCapability(str, Enum):
    """Standard capabilities that agents can declare."""
    # Language/Runtime
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"

    # Domain
    BACKEND = "backend"
    FRONTEND = "frontend"
    DEVOPS = "devops"
    DATABASE = "database"
    API_DESIGN = "api_design"

    # Operations
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"

    # Infrastructure
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    TERRAFORM = "terraform"
    CI_CD = "ci_cd"

    # Analysis
    SECURITY_AUDIT = "security_audit"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    ARCHITECTURE_DESIGN = "architecture_design"

    # Tools
    GIT = "git"
    AIDER = "aider"
    MCP_FILESYSTEM = "mcp_filesystem"
    MCP_CODE_ANALYSIS = "mcp_code_analysis"


# =============================================================================
# DELEGATION MODELS
# =============================================================================

@dataclass
class AgentProfile:
    """Profile of an agent available for delegation."""
    agent_id: str
    name: str
    description: str
    capabilities: Set[AgentCapability]

    # Performance metadata
    specialization_score: Dict[AgentCapability, float] = field(default_factory=dict)
    success_rate: float = 1.0
    avg_response_time_seconds: float = 0.0
    total_tasks_completed: int = 0

    # Availability
    is_available: bool = True
    current_load: int = 0  # Number of concurrent tasks
    max_concurrent_tasks: int = 5

    # Agent configuration (from template)
    template_id: Optional[str] = None
    model: Optional[str] = None

    # Execution handler (callable that accepts DelegationRequest and returns result)
    handler: Optional[Callable[['DelegationRequest'], Awaitable[Dict[str, Any]]]] = None

    def can_handle(self, required_capabilities: Set[AgentCapability]) -> bool:
        """Check if agent has all required capabilities."""
        return required_capabilities.issubset(self.capabilities)

    def capability_score(self, required_capabilities: Set[AgentCapability]) -> float:
        """Calculate score for handling a task with required capabilities."""
        if not self.can_handle(required_capabilities):
            return 0.0

        # Base score: percentage of required capabilities
        base_score = 1.0

        # Bonus for specialization
        specialization_bonus = sum(
            self.specialization_score.get(cap, 0.5)
            for cap in required_capabilities
        ) / len(required_capabilities)

        # Penalty for current load
        load_penalty = 1.0 - (self.current_load / self.max_concurrent_tasks)

        # Consider success rate
        return base_score * specialization_bonus * load_penalty * self.success_rate


@dataclass
class DelegationRequest:
    """Request to delegate a task to a specialized agent."""
    request_id: str
    task_description: str
    required_capabilities: Set[AgentCapability]

    # Context from current workflow
    source_task_id: int
    source_agent_id: str
    workflow_context: Dict[str, Any]  # Includes handoff history, scratchpad, etc.

    # Execution parameters
    priority: int = 5  # 1-10, higher = more urgent
    timeout_seconds: float = 600.0
    max_retries: int = 2

    # Optional constraints
    preferred_agent_id: Optional[str] = None
    excluded_agent_ids: Set[str] = field(default_factory=set)

    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DelegationResult:
    """Result of a delegated task."""
    request_id: str
    agent_id: str
    status: str  # SUCCESS, FAILURE, TIMEOUT, REJECTED

    # Result data
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # Handoff summary for context continuity
    handoff_summary: Optional[Dict[str, Any]] = None

    # Metadata
    execution_time_seconds: float = 0.0
    retry_count: int = 0
    completed_at: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# AGENT REGISTRY
# =============================================================================

class AgentRegistry:
    """
    Central registry for all available agents.

    Agents register themselves with capabilities and handlers.
    The registry matches delegation requests to suitable agents.
    """

    def __init__(self):
        self._agents: Dict[str, AgentProfile] = {}
        self._capability_index: Dict[AgentCapability, Set[str]] = {}
        self._lock = asyncio.Lock()

    def register_agent(self, profile: AgentProfile) -> None:
        """Register an agent in the registry."""
        self._agents[profile.agent_id] = profile

        # Update capability index
        for capability in profile.capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = set()
            self._capability_index[capability].add(profile.agent_id)

        logger.info(f"Registered agent '{profile.name}' ({profile.agent_id}) with {len(profile.capabilities)} capabilities")

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from the registry."""
        if agent_id in self._agents:
            profile = self._agents[agent_id]

            # Remove from capability index
            for capability in profile.capabilities:
                if capability in self._capability_index:
                    self._capability_index[capability].discard(agent_id)

            del self._agents[agent_id]
            logger.info(f"Unregistered agent {agent_id}")

    def get_agent(self, agent_id: str) -> Optional[AgentProfile]:
        """Get agent profile by ID."""
        return self._agents.get(agent_id)

    def find_capable_agents(
        self,
        required_capabilities: Set[AgentCapability],
        exclude_agent_ids: Optional[Set[str]] = None
    ) -> List[AgentProfile]:
        """Find all agents that have the required capabilities."""
        exclude_agent_ids = exclude_agent_ids or set()

        # Start with agents that have at least one required capability
        candidate_ids = set()
        for capability in required_capabilities:
            candidate_ids.update(self._capability_index.get(capability, set()))

        # Filter to agents that have ALL required capabilities
        capable_agents = []
        for agent_id in candidate_ids:
            if agent_id in exclude_agent_ids:
                continue

            profile = self._agents.get(agent_id)
            if profile and profile.is_available and profile.can_handle(required_capabilities):
                capable_agents.append(profile)

        return capable_agents

    def select_best_agent(
        self,
        required_capabilities: Set[AgentCapability],
        preferred_agent_id: Optional[str] = None,
        exclude_agent_ids: Optional[Set[str]] = None
    ) -> Optional[AgentProfile]:
        """
        Select the best agent for a task based on capabilities and performance.

        Selection criteria:
        1. Preferred agent (if specified and capable)
        2. Highest capability score
        3. Lowest current load
        4. Highest success rate
        """
        # Check preferred agent first
        if preferred_agent_id:
            profile = self.get_agent(preferred_agent_id)
            if profile and profile.is_available and profile.can_handle(required_capabilities):
                return profile

        # Find capable agents
        capable_agents = self.find_capable_agents(required_capabilities, exclude_agent_ids)

        if not capable_agents:
            return None

        # Score and rank agents
        scored_agents = [
            (agent, agent.capability_score(required_capabilities))
            for agent in capable_agents
        ]

        # Sort by score (highest first)
        scored_agents.sort(key=lambda x: x[1], reverse=True)

        best_agent = scored_agents[0][0]
        logger.info(
            f"Selected agent '{best_agent.name}' (score: {scored_agents[0][1]:.2f}) "
            f"from {len(capable_agents)} capable agents"
        )

        return best_agent

    async def update_agent_metrics(
        self,
        agent_id: str,
        success: bool,
        execution_time: float
    ) -> None:
        """Update agent performance metrics after task completion."""
        async with self._lock:
            profile = self._agents.get(agent_id)
            if not profile:
                return

            # Update task count
            profile.total_tasks_completed += 1

            # Update success rate (exponential moving average)
            alpha = 0.1  # Smoothing factor
            new_success = 1.0 if success else 0.0
            profile.success_rate = (alpha * new_success) + ((1 - alpha) * profile.success_rate)

            # Update avg response time (exponential moving average)
            profile.avg_response_time_seconds = (
                (alpha * execution_time) + ((1 - alpha) * profile.avg_response_time_seconds)
            )

            logger.debug(
                f"Updated metrics for {agent_id}: "
                f"success_rate={profile.success_rate:.2f}, "
                f"avg_time={profile.avg_response_time_seconds:.1f}s"
            )

    async def increment_load(self, agent_id: str) -> None:
        """Increment agent's current load."""
        async with self._lock:
            profile = self._agents.get(agent_id)
            if profile:
                profile.current_load += 1

    async def decrement_load(self, agent_id: str) -> None:
        """Decrement agent's current load."""
        async with self._lock:
            profile = self._agents.get(agent_id)
            if profile:
                profile.current_load = max(0, profile.current_load - 1)

    def list_all_agents(self) -> List[AgentProfile]:
        """List all registered agents."""
        return list(self._agents.values())

    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the registry."""
        total_agents = len(self._agents)
        available_agents = sum(1 for a in self._agents.values() if a.is_available)

        capability_counts = {
            cap.value: len(agent_ids)
            for cap, agent_ids in self._capability_index.items()
        }

        return {
            "total_agents": total_agents,
            "available_agents": available_agents,
            "capability_coverage": capability_counts,
            "avg_success_rate": sum(a.success_rate for a in self._agents.values()) / total_agents if total_agents > 0 else 0.0
        }


# =============================================================================
# DELEGATION BROKER
# =============================================================================

class DelegationBroker:
    """
    Handles the delegation workflow: routing, execution, result aggregation.

    This is the main interface for requesting agent delegation.
    """

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._active_delegations: Dict[str, DelegationRequest] = {}
        self._delegation_results: Dict[str, DelegationResult] = {}

    async def delegate_task(self, request: DelegationRequest) -> DelegationResult:
        """
        Delegate a task to a specialized agent.

        Flow:
        1. Select best agent based on capabilities
        2. Execute task via agent's handler
        3. Return result with handoff summary
        4. Update agent metrics
        """
        logger.info(
            f"Processing delegation request {request.request_id} for task {request.source_task_id} "
            f"requiring capabilities: {[c.value for c in request.required_capabilities]}"
        )

        self._active_delegations[request.request_id] = request

        try:
            # Select agent
            agent = self.registry.select_best_agent(
                required_capabilities=request.required_capabilities,
                preferred_agent_id=request.preferred_agent_id,
                exclude_agent_ids=request.excluded_agent_ids
            )

            if not agent:
                logger.error(f"No capable agent found for request {request.request_id}")
                return DelegationResult(
                    request_id=request.request_id,
                    agent_id="none",
                    status="REJECTED",
                    error=f"No agent available with required capabilities: {[c.value for c in request.required_capabilities]}"
                )

            # Check if agent has handler
            if not agent.handler:
                logger.error(f"Agent {agent.agent_id} has no execution handler")
                return DelegationResult(
                    request_id=request.request_id,
                    agent_id=agent.agent_id,
                    status="REJECTED",
                    error="Agent has no execution handler configured"
                )

            # Increment agent load
            await self.registry.increment_load(agent.agent_id)

            # Execute with timeout
            start_time = datetime.utcnow()
            try:
                result_data = await asyncio.wait_for(
                    agent.handler(request),
                    timeout=request.timeout_seconds
                )

                execution_time = (datetime.utcnow() - start_time).total_seconds()

                # Create success result
                result = DelegationResult(
                    request_id=request.request_id,
                    agent_id=agent.agent_id,
                    status="SUCCESS",
                    result=result_data,
                    handoff_summary=result_data.get("handoff_summary"),
                    execution_time_seconds=execution_time
                )

                # Update metrics
                await self.registry.update_agent_metrics(agent.agent_id, success=True, execution_time=execution_time)

                logger.info(
                    f"Delegation {request.request_id} completed successfully by {agent.name} "
                    f"in {execution_time:.1f}s"
                )

            except asyncio.TimeoutError:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                logger.error(f"Delegation {request.request_id} timed out after {execution_time:.1f}s")

                result = DelegationResult(
                    request_id=request.request_id,
                    agent_id=agent.agent_id,
                    status="TIMEOUT",
                    error=f"Task execution timed out after {request.timeout_seconds}s",
                    execution_time_seconds=execution_time
                )

                await self.registry.update_agent_metrics(agent.agent_id, success=False, execution_time=execution_time)

            except Exception as e:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                logger.error(f"Delegation {request.request_id} failed: {e}")

                result = DelegationResult(
                    request_id=request.request_id,
                    agent_id=agent.agent_id,
                    status="FAILURE",
                    error=str(e),
                    execution_time_seconds=execution_time
                )

                await self.registry.update_agent_metrics(agent.agent_id, success=False, execution_time=execution_time)

            finally:
                # Decrement agent load
                await self.registry.decrement_load(agent.agent_id)

            # Store result
            self._delegation_results[request.request_id] = result
            return result

        finally:
            # Clean up active delegation tracking
            self._active_delegations.pop(request.request_id, None)

    async def delegate_with_retry(self, request: DelegationRequest) -> DelegationResult:
        """Delegate a task with automatic retry on failure."""
        for attempt in range(request.max_retries + 1):
            result = await self.delegate_task(request)

            if result.status == "SUCCESS":
                return result

            if attempt < request.max_retries:
                logger.warning(
                    f"Delegation {request.request_id} failed (attempt {attempt + 1}/{request.max_retries + 1}). "
                    f"Retrying..."
                )
                # Exclude the failed agent from next attempt
                if result.agent_id != "none":
                    request.excluded_agent_ids.add(result.agent_id)
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        result.retry_count = request.max_retries
        return result

    def get_active_delegations(self) -> List[DelegationRequest]:
        """Get list of currently active delegations."""
        return list(self._active_delegations.values())

    def get_delegation_result(self, request_id: str) -> Optional[DelegationResult]:
        """Get result of a completed delegation."""
        return self._delegation_results.get(request_id)


# =============================================================================
# GLOBAL REGISTRY AND BROKER
# =============================================================================

_global_registry: Optional[AgentRegistry] = None
_global_broker: Optional[DelegationBroker] = None


def get_agent_registry() -> AgentRegistry:
    """Get or create the global agent registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
        logger.info("Initialized global agent registry")
    return _global_registry


def get_delegation_broker() -> DelegationBroker:
    """Get or create the global delegation broker."""
    global _global_broker
    if _global_broker is None:
        registry = get_agent_registry()
        _global_broker = DelegationBroker(registry)
        logger.info("Initialized global delegation broker")
    return _global_broker


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def request_agent_help(
    task_description: str,
    required_capabilities: List[str],
    source_task_id: int,
    source_agent_id: str,
    workflow_context: Dict[str, Any],
    timeout_seconds: float = 600.0
) -> DelegationResult:
    """
    Convenience function to request help from a specialized agent.

    This is the main entry point for agent-to-agent delegation.
    """
    broker = get_delegation_broker()

    # Convert capability strings to enums
    capabilities = {AgentCapability(cap) for cap in required_capabilities}

    # Create delegation request
    request = DelegationRequest(
        request_id=f"del_{source_task_id}_{datetime.utcnow().timestamp()}",
        task_description=task_description,
        required_capabilities=capabilities,
        source_task_id=source_task_id,
        source_agent_id=source_agent_id,
        workflow_context=workflow_context,
        timeout_seconds=timeout_seconds
    )

    # Delegate with retry
    return await broker.delegate_with_retry(request)


def register_agent_from_template(
    agent_id: str,
    template_id: str,
    handler: Callable[[DelegationRequest], Awaitable[Dict[str, Any]]]
) -> AgentProfile:
    """
    Register an agent from a template in the agent registry.

    This bridges the Template Library with the Delegation System.
    """
    from .agent_templates import AgentTemplateRegistry

    template = AgentTemplateRegistry.get(template_id)
    if not template:
        raise ValueError(f"Template not found: {template_id}")

    # Map template to capabilities
    capability_mapping = {
        "aider_code_writer": {AgentCapability.CODE_GENERATION, AgentCapability.GIT, AgentCapability.AIDER},
        "architect_agent": {AgentCapability.ARCHITECTURE_DESIGN, AgentCapability.CODE_GENERATION},
        "refactor_specialist": {AgentCapability.REFACTORING, AgentCapability.CODE_REVIEW},
        "code_reviewer": {AgentCapability.CODE_REVIEW, AgentCapability.SECURITY_AUDIT},
        "test_generator": {AgentCapability.TESTING, AgentCapability.CODE_GENERATION},
        "qa_validator": {AgentCapability.TESTING, AgentCapability.CODE_REVIEW},
        "devops_automation": {AgentCapability.DEVOPS, AgentCapability.DOCKER, AgentCapability.KUBERNETES},
        "research_agent": {AgentCapability.DOCUMENTATION},
        "doc_writer": {AgentCapability.DOCUMENTATION}
    }

    capabilities = capability_mapping.get(template_id, {AgentCapability.CODE_GENERATION})

    # Create agent profile
    profile = AgentProfile(
        agent_id=agent_id,
        name=template.name,
        description=template.description,
        capabilities=capabilities,
        template_id=template_id,
        model=template.model,
        handler=handler
    )

    # Register in global registry
    registry = get_agent_registry()
    registry.register_agent(profile)

    logger.info(f"Registered agent '{profile.name}' from template '{template_id}'")

    return profile
