# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Models - Simplified for LangConfig
"""
from sqlalchemy import Column, Integer, String, JSON, Enum as SQLEnum, DateTime, Text, ForeignKey, Boolean, Float
from sqlalchemy.orm import validates, relationship
from db.database import Base
from core.versioning import OptimisticLockMixin
from enum import Enum
import datetime

class WorkflowStrategy(str, Enum):
    """Available workflow orchestration strategies"""
    DEFAULT_SEQUENTIAL = "default_sequential"
    ROMAN_LEGION = "roman_legion"
    QUORUM_SENSING = "quorum_sensing"
    STIGMERGY = "stigmergy"
    DEEP_RESEARCH = "deep_research"
    LEARNING_RESEARCH = "learning_research"
    SUPERVISOR_DEVELOPMENT = "supervisor_development"
    SUPERVISOR_CODE_REVIEW = "supervisor_code_review"
    SUPERVISOR_ARCHITECTURE = "supervisor_architecture"
    RLM = "rlm"
    RLM_RAG_HYBRID = "rlm_rag_hybrid"

class WorkflowProfile(Base, OptimisticLockMixin):
    """
    User-defined workflow configuration profiles.
    Allows saving custom strategy configurations for reuse.
    """
    __tablename__ = "workflow_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # Profile metadata
    name = Column(String(100), index=True, nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Project association
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True, index=True)

    # Strategy type (deprecated - kept for backward compatibility)
    strategy_type = Column(
        SQLEnum(WorkflowStrategy, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        default=WorkflowStrategy.DEFAULT_SEQUENTIAL.value,
        index=True
    )

    # Configuration JSON (validated against strategy's config schema)
    # Note: Node-level agent configs include custom_tools: List[str] field
    configuration = Column(JSON, nullable=False)

    # Schema output configuration (Full/Compact/Minimal)
    schema_output_config = Column(JSON, nullable=True, default=None)

    # Structured output schema name (e.g., "JiraTicketOutput")
    output_schema = Column(String, nullable=True, default=None)

    # Optional: Visual workflow blueprint
    blueprint = Column(JSON, nullable=True)

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False
    )

    # Export status tracking 
    export_status = Column(String(50), nullable=True)  # 'pending', 'in_progress', 'completed', 'failed'
    export_error = Column(Text, nullable=True)  # Error message if export failed
    last_export_at = Column(DateTime(timezone=True), nullable=True)  # Last successful export timestamp

    @validates('name')
    def validate_name(self, key, value):
        """Ensure name is not empty"""
        if not value or not value.strip():
            raise ValueError("Profile name cannot be empty")
        return value.strip()

    def __repr__(self):
        return f"<WorkflowProfile(id={self.id}, name='{self.name}', strategy={self.strategy_type.value})>"


# =============================================================================
# Workflow State Enums
# =============================================================================

class WorkflowStateStatus(str, Enum):
    """Flexible workflow status that applies across all strategies."""
    # Initialization
    INITIALIZING = "INITIALIZING"
    AWAITING_TIER_DECISION = "AWAITING_TIER_DECISION"

    # Execution phases
    EXECUTING_TIER_1 = "EXECUTING_TIER_1"
    EXECUTING_TIER_2 = "EXECUTING_TIER_2"
    EXECUTING_TIER_3 = "EXECUTING_TIER_3"
    EXECUTING_PARALLEL = "EXECUTING_PARALLEL"
    EXECUTING_STIGMERGIC = "EXECUTING_STIGMERGIC"

    # Coordination phases
    AWAITING_QUORUM = "AWAITING_QUORUM"
    VOTING = "VOTING"
    SYNCHRONIZING = "SYNCHRONIZING"

    # Validation
    VALIDATING = "VALIDATING"
    AWAITING_QA = "AWAITING_QA"

    # Completion states
    PASSED = "PASSED"
    FAILED = "FAILED"
    CONSENSUS_REACHED = "CONSENSUS_REACHED"

    # HITL states
    AWAITING_HITL = "AWAITING_HITL"
    HITL_REVIEWING = "HITL_REVIEWING"

    # Error states
    TIER_EXHAUSTED = "TIER_EXHAUSTED"
    QUORUM_FAILED = "QUORUM_FAILED"
    TIMEOUT = "TIMEOUT"


class AgentTier(str, Enum):
    """Agent capability tiers for Roman Legion strategy."""
    AUXILIA = "AUXILIA"  # Tier 1: Fast, cheap, basic reasoning
    LEGIONARIES = "LEGIONARIES"  # Tier 2: Balanced, standard complexity
    PRAETORIANS = "PRAETORIANS"  # Tier 3: Powerful, expensive, expert reasoning


class ConsensusMethod(str, Enum):
    """Methods for reaching consensus in Quorum Sensing strategy."""
    MAJORITY_VOTE = "MAJORITY_VOTE"
    UNANIMOUS = "UNANIMOUS"
    WEIGHTED_SCORE = "WEIGHTED_SCORE"
    RANKED_CHOICE = "RANKED_CHOICE"


class StigmergySignalType(str, Enum):
    """Types of environmental signals in Stigmergy strategy."""
    FILE_CREATED = "FILE_CREATED"
    FILE_MODIFIED = "FILE_MODIFIED"
    TEST_PASSED = "TEST_PASSED"
    TEST_FAILED = "TEST_FAILED"
    BUILD_SUCCEEDED = "BUILD_SUCCEEDED"
    BUILD_FAILED = "BUILD_FAILED"
    LINT_WARNING = "LINT_WARNING"
    CODE_SMELL = "CODE_SMELL"


# =============================================================================
# Workflow Versioning Models
# =============================================================================

class WorkflowVersion(Base):
    """
    Workflow version snapshots for version control and comparison.

    Each time a workflow configuration is saved (manually or auto-saved on node changes),
    a new version is created with a snapshot of the complete configuration.
    """
    __tablename__ = "workflow_versions"

    id = Column(Integer, primary_key=True, index=True)

    # Reference to the workflow profile
    workflow_id = Column(Integer, ForeignKey("workflow_profiles.id"), nullable=False, index=True)

    # Version number (auto-incremented for each workflow)
    version_number = Column(Integer, nullable=False)

    # Complete workflow configuration snapshot (includes nodes, edges, settings)
    config_snapshot = Column(JSON, nullable=False)

    # User notes about this version (optional)
    notes = Column(Text, nullable=True)

    # Changelog - auto-generated description of what changed
    changelog = Column(Text, nullable=True)

    # Whether this is the currently active version
    is_current = Column(Boolean, default=False, nullable=False)

    # Metadata
    created_by = Column(String(100), nullable=True)  # User ID or name
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    executions = relationship("WorkflowExecution", back_populates="version", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorkflowVersion(id={self.id}, workflow_id={self.workflow_id}, v{self.version_number})>"


class WorkflowExecution(Base):
    """
    Records of workflow executions tied to specific versions.

    Tracks execution results, performance metrics, and costs for each workflow run.
    This allows comparing outputs and performance across different workflow versions.
    """
    __tablename__ = "workflow_executions"

    id = Column(Integer, primary_key=True, index=True)

    # Reference to workflow and version
    workflow_id = Column(Integer, ForeignKey("workflow_profiles.id"), nullable=False, index=True)
    version_id = Column(Integer, ForeignKey("workflow_versions.id"), nullable=False, index=True)

    # Execution results (complete output from the workflow)
    execution_results = Column(JSON, nullable=False)

    # Performance metrics
    token_usage = Column(JSON, nullable=True)  # {input_tokens, output_tokens, total_tokens}
    cost = Column(Float, nullable=True)  # Estimated cost in USD
    execution_time = Column(Float, nullable=True)  # Duration in seconds

    # Status
    status = Column(String(50), nullable=False, default="success")  # success, failed, partial, etc.
    error_message = Column(Text, nullable=True)  # Error details if failed

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    version = relationship("WorkflowVersion", back_populates="executions")

    def __repr__(self):
        return f"<WorkflowExecution(id={self.id}, workflow_id={self.workflow_id}, version_id={self.version_id}, status={self.status})>"
