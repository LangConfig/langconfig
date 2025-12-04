# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Pydantic schemas for workflow-specific state management.

Each workflow strategy maintains its own state structure stored in
the Task.workflow_state JSON field. These schemas provide validation
and type safety for strategy-specific state.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime

from models.workflow import (
    AgentTier,
    ConsensusMethod,
    StigmergySignalType,
    WorkflowStateStatus
)


# =============================================================================
# Base Workflow State
# =============================================================================

class BaseWorkflowState(BaseModel):
    """
    Base state shared across all workflow strategies.
    
    This provides common fields that all strategies use.
    """
    status: WorkflowStateStatus = WorkflowStateStatus.INITIALIZING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    
    class Config:
        use_enum_values = True


# =============================================================================
# DEFAULT_SEQUENTIAL Strategy State
# =============================================================================

class SequentialWorkflowState(BaseWorkflowState):
    """
    State for the default sequential workflow strategy.
    
    This represents the current single-agent retry-based approach.
    """
    retry_count: int = 0
    max_retries: int = 3
    last_failure_reason: Optional[str] = None
    validation_attempts: int = 0
    
    @validator('retry_count')
    def validate_retry_count(cls, v, values):
        max_retries = values.get('max_retries', 3)
        if v < 0:
            raise ValueError("retry_count cannot be negative")
        if v > max_retries:
            raise ValueError(f"retry_count cannot exceed max_retries ({max_retries})")
        return v


# =============================================================================
# ROMAN_LEGION Strategy State
# =============================================================================

class TierAttempt(BaseModel):
    """Record of a single attempt at a specific tier."""
    tier: AgentTier
    attempt_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    qa_feedback: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class RomanLegionState(BaseWorkflowState):
    """
    State for Roman Legion hierarchical workflow strategy.
    
    Tracks:
    - Current agent tier (Auxilia, Legionaries, Praetorians)
    - Attempts at each tier
    - QA feedback for tier escalation decisions
    - Tier progression history
    - Next action for routing (RETRY, ESCALATE, FAIL_HITL)
    """
    current_tier_index: int = 0  # 0=Hastati/Auxilia, 1=Principes/Legionaries, 2=Triarii/Praetorians
    tier_attempt_count: int = 0
    max_attempts_per_tier: int = 2
    
    # Explicit action determined by handle_failure, used by the router (Checklist Q1)
    next_action: Optional[str] = None
    
    # History of all attempts across tiers
    tier_history: List[TierAttempt] = Field(default_factory=list)
    
    # QA feedback that triggered escalation
    escalation_triggers: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Whether tier escalation is enabled
    enable_tier_escalation: bool = True
    
    # Whether QA gate is required before tier escalation
    enable_qa_gate: bool = True
    
    # QA agent feedback (for decision to escalate)
    qa_review: Optional[Dict[str, Any]] = None
    
    @validator('tier_attempt_count')
    def validate_tier_attempts(cls, v, values):
        max_attempts = values.get('max_attempts_per_tier', 2)
        if v < 0:
            raise ValueError("tier_attempt_count cannot be negative")
        if v > max_attempts:
            raise ValueError(f"tier_attempt_count cannot exceed max_attempts_per_tier ({max_attempts})")
        return v
    
    def add_tier_attempt(self, tier: AgentTier, success: bool, error: Optional[str] = None):
        """Record a tier attempt."""
        attempt = TierAttempt(
            tier=tier,
            attempt_number=self.tier_attempt_count + 1,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            success=success,
            error=error
        )
        self.tier_history.append(attempt)
        self.tier_attempt_count += 1
        self.updated_at = datetime.utcnow()
    
    def should_escalate_tier(self, max_tiers: int = 3) -> bool:
        """Determine if tier should be escalated."""
        if not self.enable_tier_escalation:
            return False
        
        # Check if we've exhausted attempts at current tier
        if self.tier_attempt_count >= self.max_attempts_per_tier:
            # Check if there's a higher tier available
            return self.current_tier_index < (max_tiers - 1)
        
        return False
    
    def escalate_to_next_tier(self, max_tiers: int = 3) -> bool:
        """
        Escalate to the next tier.
        
        Args:
            max_tiers: Maximum number of tiers available
        
        Returns:
            True if escalation successful, False if at highest tier
        """
        if self.current_tier_index >= (max_tiers - 1):
            return False
        
        current_tier = AgentTier.get_tier_by_index(self.current_tier_index)
        next_tier_index = self.current_tier_index + 1
        next_tier = AgentTier.get_tier_by_index(next_tier_index)
        
        # Record escalation trigger
        self.escalation_triggers.append({
            "from_tier": current_tier.value,
            "from_tier_index": self.current_tier_index,
            "to_tier": next_tier.value,
            "to_tier_index": next_tier_index,
            "reason": f"Exhausted {self.tier_attempt_count} attempts at {current_tier.value}",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Escalate
        self.current_tier_index = next_tier_index
        self.tier_attempt_count = 0
        self.status = WorkflowStateStatus[f"EXECUTING_TIER_{next_tier_index + 1}"]
        self.updated_at = datetime.utcnow()
        
        return True


# =============================================================================
# QUORUM_SENSING Strategy State
# =============================================================================

class ParallelRun(BaseModel):
    """Record of a single parallel agent execution."""
    run_id: str
    agent_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    solution: Optional[Dict[str, Any]] = None
    score: Optional[float] = None
    vote: Optional[str] = None  # For consensus voting


class QuorumSensingState(BaseWorkflowState):
    """
    State for Quorum Sensing parallel consensus strategy.
    
    Tracks:
    - Multiple parallel agent executions (TaskSubmission IDs)
    - Voting/consensus process
    - Solution rankings and scores
    """
    parallel_agents: int = 3
    minimum_quorum: int = 2
    consensus_method: ConsensusMethod = ConsensusMethod.MAJORITY_VOTE
    
    # Parallel execution tracking (Checklist Q2)
    submission_ids: List[int] = Field(default_factory=list)  # IDs of TaskSubmission records
    run_status: Dict[int, str] = Field(default_factory=dict)  # submission_id -> status
    parallel_run_ids: List[str] = Field(default_factory=list)  # Deprecated - use submission_ids
    parallel_runs: List[ParallelRun] = Field(default_factory=list)
    
    # Consensus tracking
    consensus_reached: bool = False
    winning_solution_id: Optional[str] = None
    votes: Dict[str, int] = Field(default_factory=dict)  # solution_id -> vote count
    
    # Timeout handling
    timeout_seconds: int = 600
    started_at: Optional[datetime] = None
    
    @validator('minimum_quorum')
    def validate_quorum(cls, v, values):
        parallel_agents = values.get('parallel_agents', 3)
        if v > parallel_agents:
            raise ValueError(f"minimum_quorum ({v}) cannot exceed parallel_agents ({parallel_agents})")
        if v < 1:
            raise ValueError("minimum_quorum must be at least 1")
        return v
    
    def add_parallel_run(self, run_id: str, agent_id: str):
        """Register a new parallel run."""
        run = ParallelRun(
            run_id=run_id,
            agent_id=agent_id,
            started_at=datetime.utcnow()
        )
        self.parallel_runs.append(run)
        self.parallel_run_ids.append(run_id)
        self.updated_at = datetime.utcnow()
    
    def complete_run(self, run_id: str, success: bool, solution: Optional[Dict[str, Any]] = None):
        """Mark a parallel run as completed."""
        for run in self.parallel_runs:
            if run.run_id == run_id:
                run.completed_at = datetime.utcnow()
                run.success = success
                run.solution = solution
                break
        self.updated_at = datetime.utcnow()
    
    def get_completed_runs_count(self) -> int:
        """Get count of completed runs."""
        return sum(1 for run in self.parallel_runs if run.completed_at is not None)
    
    def has_quorum(self) -> bool:
        """Check if minimum quorum of completions is reached."""
        completed = self.get_completed_runs_count()
        return completed >= self.minimum_quorum
    
    def is_timed_out(self) -> bool:
        """Check if parallel execution has timed out."""
        if self.started_at is None:
            return False
        elapsed = (datetime.utcnow() - self.started_at).total_seconds()
        return elapsed > self.timeout_seconds


# =============================================================================
# STIGMERGY Strategy State
# =============================================================================

class StigmergySignal(BaseModel):
    """Environmental signal left by an agent."""
    signal_id: str
    signal_type: StigmergySignalType
    agent_id: str
    timestamp: datetime
    location: str  # File path or context
    intensity: float = 1.0  # Signal strength (0.0 - 1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentActivity(BaseModel):
    """Record of agent activity in stigmergy system."""
    agent_id: str
    activated_at: datetime
    last_action: Optional[datetime] = None
    signals_detected: List[str] = Field(default_factory=list)  # signal_ids
    signals_emitted: List[str] = Field(default_factory=list)  # signal_ids
    active: bool = True


class StigmergyState(BaseWorkflowState):
    """
    State for Stigmergy indirect coordination strategy.
    
    Tracks:
    - Environmental signals (file changes, test results, etc.)
    - Active agents and their interactions with signals
    - Convergence toward solution
    """
    max_agents: int = 5
    max_cycles: int = 10
    current_cycle: int = 0
    
    # Signal tracking
    signal_history: List[StigmergySignal] = Field(default_factory=list)
    active_signals: Dict[str, StigmergySignal] = Field(default_factory=dict)  # signal_id -> signal
    
    # Agent tracking
    active_agents: List[str] = Field(default_factory=list)  # agent_ids
    agent_activities: List[AgentActivity] = Field(default_factory=list)
    
    # Convergence tracking
    signal_sensitivity: float = 0.7  # Threshold for agents to react to signals
    convergence_threshold: float = 0.9  # When to consider task complete
    convergence_score: float = 0.0
    
    # Solution emergence tracking
    solution_fragments: List[Dict[str, Any]] = Field(default_factory=list)
    
    @validator('signal_sensitivity', 'convergence_threshold', 'convergence_score')
    def validate_float_range(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Value must be between 0.0 and 1.0, got {v}")
        return v
    
    def emit_signal(self, agent_id: str, signal_type: StigmergySignalType, 
                    location: str, intensity: float = 1.0, 
                    metadata: Optional[Dict[str, Any]] = None):
        """Agent emits an environmental signal."""
        signal_id = f"signal_{len(self.signal_history)}"
        signal = StigmergySignal(
            signal_id=signal_id,
            signal_type=signal_type,
            agent_id=agent_id,
            timestamp=datetime.utcnow(),
            location=location,
            intensity=intensity,
            metadata=metadata or {}
        )
        
        self.signal_history.append(signal)
        self.active_signals[signal_id] = signal
        
        # Update agent activity
        for activity in self.agent_activities:
            if activity.agent_id == agent_id:
                activity.signals_emitted.append(signal_id)
                activity.last_action = datetime.utcnow()
                break
        
        self.updated_at = datetime.utcnow()
    
    def detect_signals(self, agent_id: str, location: str) -> List[StigmergySignal]:
        """Agent detects signals in their environment."""
        # Find signals at the same location above sensitivity threshold
        detected = []
        for signal in self.active_signals.values():
            if (signal.location == location and 
                signal.intensity >= self.signal_sensitivity and
                signal.agent_id != agent_id):  # Don't detect own signals
                detected.append(signal)
        
        # Update agent activity
        for activity in self.agent_activities:
            if activity.agent_id == agent_id:
                activity.signals_detected.extend([s.signal_id for s in detected])
                activity.last_action = datetime.utcnow()
                break
        
        return detected
    
    def calculate_convergence(self) -> float:
        """
        Calculate convergence score based on signal patterns.
        
        Higher score indicates agents are working coherently toward solution.
        """
        if not self.signal_history:
            return 0.0
        
        # Simple heuristic: ratio of positive signals (tests passing, builds succeeding)
        # to total signals
        positive_types = {
            StigmergySignalType.TEST_PASSED,
            StigmergySignalType.BUILD_SUCCEEDED,
            StigmergySignalType.FILE_CREATED
        }
        
        recent_signals = self.signal_history[-10:]  # Last 10 signals
        positive_count = sum(1 for s in recent_signals if s.signal_type in positive_types)
        
        self.convergence_score = positive_count / len(recent_signals)
        return self.convergence_score
    
    def has_converged(self) -> bool:
        """Check if system has converged to solution."""
        score = self.calculate_convergence()
        return score >= self.convergence_threshold


# =============================================================================
# Factory Functions
# =============================================================================

def create_initial_workflow_state(strategy: str) -> Dict[str, Any]:
    """
    Create initial workflow state for a given strategy.
    
    Args:
        strategy: WorkflowStrategy enum value
        
    Returns:
        Dictionary representation of initial state
    """
    from models.workflow_strategy import WorkflowStrategy
    
    strategy_enum = WorkflowStrategy(strategy)
    
    state_classes = {
        WorkflowStrategy.DEFAULT_SEQUENTIAL: SequentialWorkflowState,
        WorkflowStrategy.ROMAN_LEGION: RomanLegionState,
        WorkflowStrategy.QUORUM_SENSING: QuorumSensingState,
        WorkflowStrategy.STIGMERGY: StigmergyState
    }
    
    state_class = state_classes.get(strategy_enum, SequentialWorkflowState)
    initial_state = state_class()
    
    return initial_state.dict()


def parse_workflow_state(strategy: str, state_dict: Dict[str, Any]) -> BaseWorkflowState:
    """
    Parse workflow state dict into appropriate Pydantic model.
    
    Args:
        strategy: WorkflowStrategy enum value
        state_dict: Dictionary from Task.workflow_state
        
    Returns:
        Pydantic model instance
    """
    from models.workflow_strategy import WorkflowStrategy
    
    strategy_enum = WorkflowStrategy(strategy)
    
    state_classes = {
        WorkflowStrategy.DEFAULT_SEQUENTIAL: SequentialWorkflowState,
        WorkflowStrategy.ROMAN_LEGION: RomanLegionState,
        WorkflowStrategy.QUORUM_SENSING: QuorumSensingState,
        WorkflowStrategy.STIGMERGY: StigmergyState
    }
    
    state_class = state_classes.get(strategy_enum, SequentialWorkflowState)
    return state_class(**state_dict)
