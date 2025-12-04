# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Strategy Configuration Schemas.

These Pydantic models define the user-facing configuration parameters
for each workflow strategy. They are used for:
1. Generating dynamic UI forms
2. Validating user input
3. Providing documentation/hints
4. Creating reusable configuration profiles

Distinct from workflow_state.py which handles internal runtime state.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum
from constants.models import ModelChoice

# Import Blueprint model for visual workflow configuration
try:
    from models.blueprint import Blueprint
except ImportError:
    # Blueprint support optional for backward compatibility
    Blueprint = None


# =============================================================================
# Sequential Strategy Configuration
# =============================================================================

class SequentialConfig(BaseModel):
    """
    Configuration for Sequential (Default) workflow strategy.
    
    Single-agent execution with retries and QA validation.
    """
    
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts before triggering HITL"
    )
    
    default_model: ModelChoice = Field(
        default="gpt-4o",
        description="Default LLM model to use for task execution"
    )
    
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Model temperature for response generation"
    )
    
    retry_base_delay_seconds: int = Field(
        default=5,
        ge=0,
        description="Base delay in seconds for exponential backoff between retries"
    )
    
    retry_max_delay_seconds: int = Field(
        default=300,
        ge=0,
        description="Maximum delay in seconds between retries"
    )
    
    enable_qa_validation: bool = Field(
        default=True,
        description="Enable automatic QA validation after execution"
    )
    
    strict_qa_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum QA score (0.0-1.0) required to pass validation"
    )
    
    enable_hitl: bool = Field(
        default=True,
        description="Enable Human-in-the-Loop intervention on failures"
    )

    # Structured output configuration
    output_schema: Optional[str] = Field(
        default=None,
        description="Structured output schema name (e.g., 'JiraTicketOutput', 'CodeReviewOutput'). When set, the workflow will return typed, validated output in this format."
    )

    # Optional blueprint for visual workflow configuration
    blueprint: Optional[Any] = Field(
        None,
        description="Visual workflow blueprint defining agent network structure"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "max_retries": 3,
                "default_model": "gpt-4o",  # GPT-4o for standard tasks
                "temperature": 0.7,
                "enable_qa_validation": True,
                "strict_qa_threshold": 0.7,
                "enable_hitl": True
            }
        }


# =============================================================================
# Roman Legion Strategy Configuration
# =============================================================================

class RomanLegionTier(BaseModel):
    """
    Configuration for a single tier in the Roman Legion hierarchy.
    
    Each tier represents a level of agent capability, with higher tiers
    using more powerful (and expensive) models.
    """
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Human-readable name for this tier (e.g., 'Hastati', 'Principes', 'Triarii')"
    )
    
    model: ModelChoice = Field(
        ...,
        description="LLM model identifier for this tier (e.g., 'gpt-4o-mini', 'gpt-4o', 'o1-mini')"
    )
    
    max_retries: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Maximum retry attempts at this tier before escalating"
    )
    
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Model temperature for this tier"
    )
    
    @validator('name')
    def validate_name(cls, v):
        """Ensure tier name is not empty after stripping."""
        if not v.strip():
            raise ValueError("Tier name cannot be empty")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Hastati",
                "model": "gpt-4o-mini",  # Economy model for basic tasks
                "max_retries": 2,
                "temperature": 0.7
            }
        }


class RomanLegionConfig(BaseModel):
    """
    Configuration for Roman Legion hierarchical escalation strategy.
    
    Tasks start at the lowest tier and escalate to higher tiers upon failure.
    Each tier uses progressively more capable (and expensive) models.
    """
    
    tiers: List[RomanLegionTier] = Field(
        ...,
        min_items=1,
        max_items=10,
        description="Ordered list of escalation tiers (lowest to highest capability)"
    )
    
    enable_tier_escalation: bool = Field(
        default=True,
        description="Enable automatic escalation to next tier on failure"
    )
    
    enable_qa_gate: bool = Field(
        default=True,
        description="Require QA validation at each tier before considering success"
    )
    
    auto_revert_on_failure: bool = Field(
        default=True,
        description="Automatically revert codebase changes before retry/escalation"
    )
    
    enable_hitl: bool = Field(
        default=True,
        description="Trigger HITL when all tiers are exhausted"
    )

    output_schema: Optional[str] = Field(
        default=None,
        description="Structured output schema name (e.g., 'JiraTicketOutput', 'CodeReviewOutput')"
    )

    # Optional blueprint for visual workflow configuration
    blueprint: Optional[Any] = Field(
        None,
        description="Visual workflow blueprint defining agent network structure"
    )
    
    @validator('tiers')
    def validate_tiers(cls, v):
        """Ensure tier configuration is valid."""
        if not v:
            raise ValueError("At least one tier must be configured")
        
        # Check for duplicate tier names
        tier_names = [tier.name for tier in v]
        if len(tier_names) != len(set(tier_names)):
            raise ValueError("Tier names must be unique")
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "tiers": [
                    {"name": "Hastati", "model": "gpt-4o-mini", "max_retries": 2, "temperature": 0.7},
                    {"name": "Principes", "model": "gpt-4o", "max_retries": 1, "temperature": 0.7},
                    {"name": "Triarii", "model": "claude-sonnet-4-20250514", "max_retries": 1, "temperature": 0.5}
                ],
                "enable_tier_escalation": True,
                "enable_qa_gate": True,
                "auto_revert_on_failure": True,
                "enable_hitl": True
            }
        }


# =============================================================================
# Quorum Sensing Strategy Configuration
# =============================================================================

class ConsensusMethodEnum(str, Enum):
    """Consensus methods for selecting winning submission."""
    MAJORITY_VOTE = "MAJORITY_VOTE"
    WEIGHTED_SCORE = "WEIGHTED_SCORE"
    UNANIMOUS = "UNANIMOUS"
    RANKED_CHOICE = "RANKED_CHOICE"


class QuorumSensingConfig(BaseModel):
    """
    Configuration for Quorum Sensing parallel consensus strategy.
    
    Multiple agents work simultaneously on the same task, with the best
    solution selected through democratic consensus.
    """
    
    parallel_agents: int = Field(
        default=3,
        ge=2,
        le=10,
        description="Number of parallel agents to spawn for execution"
    )
    
    minimum_quorum: int = Field(
        default=2,
        ge=1,
        description="Minimum number of completions required to proceed with consensus"
    )
    
    models: List[str] = Field(
        default=["gpt-4o", "gpt-4o", "gpt-4o"],  # GPT-4o for parallel execution
        min_items=1,
        description="List of models to use for parallel agents (can repeat for diversity through randomness)"
    )
    
    consensus_method: ConsensusMethodEnum = Field(
        default=ConsensusMethodEnum.WEIGHTED_SCORE,
        description="Method for selecting the winning submission from parallel results"
    )
    
    timeout_seconds: int = Field(
        default=600,
        ge=60,
        le=3600,
        description="Maximum time to wait for parallel agents to complete"
    )
    
    enable_diversity: bool = Field(
        default=True,
        description="Use different models for better solution diversity"
    )
    
    auto_merge_winner: bool = Field(
        default=True,
        description="Automatically merge the winning submission's git branch"
    )
    
    enable_hitl: bool = Field(
        default=True,
        description="Trigger HITL if no submissions pass consensus"
    )

    output_schema: Optional[str] = Field(
        default=None,
        description="Structured output schema name (e.g., 'JiraTicketOutput', 'CodeReviewOutput')"
    )

    # Optional blueprint for visual workflow configuration
    blueprint: Optional[Any] = Field(
        None,
        description="Visual workflow blueprint defining agent network structure"
    )
    
    @validator('minimum_quorum')
    def validate_quorum(cls, v, values):
        """Ensure quorum doesn't exceed parallel_agents."""
        parallel_agents = values.get('parallel_agents', 3)
        if v > parallel_agents:
            raise ValueError(
                f"minimum_quorum ({v}) cannot exceed parallel_agents ({parallel_agents})"
            )
        return v
    
    @validator('models')
    def validate_models(cls, v, values):
        """Ensure we have enough models for parallel agents."""
        parallel_agents = values.get('parallel_agents', 3)
        if len(v) < parallel_agents:
            # Duplicate models to match parallel_agents count
            while len(v) < parallel_agents:
                v.extend(v)
            v = v[:parallel_agents]
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "parallel_agents": 3,
                "minimum_quorum": 2,
                "models": ["gpt-4o", "claude-sonnet-3.5", "gpt-4o"],
                "consensus_method": "WEIGHTED_SCORE",
                "timeout_seconds": 600,
                "enable_diversity": True,
                "auto_merge_winner": True,
                "enable_hitl": True
            }
        }


# =============================================================================
# Stigmergy Strategy Configuration (Future)
# =============================================================================

class StigmergyConfig(BaseModel):
    """
    Configuration for Stigmergy environmental coordination strategy.
    
    NOTE: This is a placeholder for future implementation.
    Stigmergy requires significant architectural changes.
    """
    
    max_agents: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of concurrent agents in the swarm"
    )
    
    max_cycles: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum coordination cycles before forcing convergence"
    )
    
    signal_sensitivity: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Threshold for agents to react to environmental signals"
    )
    
    convergence_threshold: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Quality threshold to consider solution converged"
    )
    
    output_schema: Optional[str] = Field(
        default=None,
        description="Structured output schema name (e.g., \'JiraTicketOutput\', \'CodeReviewOutput\')"
    )

    # Optional blueprint for visual workflow configuration
    blueprint: Optional[Any] = Field(
        None,
        description="Visual workflow blueprint defining agent network structure"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "max_agents": 5,
                "max_cycles": 10,
                "signal_sensitivity": 0.7,
                "convergence_threshold": 0.9
            }
        }


# =============================================================================
# Deep Research Strategy Configuration
# =============================================================================

class DeepResearchConfig(BaseModel):
    """
    Configuration for Deep Research workflow strategy.

    Multi-agent collaboration with planning, parallel research, writing, and reflection.
    """

    max_reflection_iterations: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of critique-revision cycles before finalizing report"
    )

    planner_model: ModelChoice = Field(
        default="claude-3.5-sonnet",
        description="Model for decomposing research topics into sub-questions"
    )

    researcher_model: ModelChoice = Field(
        default="gpt-4o-mini",
        description="Model for conducting parallel research tasks"
    )

    writer_model: ModelChoice = Field(
        default="claude-3.5-sonnet",
        description="Model for synthesizing research into comprehensive reports"
    )

    critic_model: ModelChoice = Field(
        default="gpt-4o",
        description="Model for evaluating report quality and providing feedback"
    )

    enable_web_search: bool = Field(
        default=True,
        description="Enable web search capabilities for researchers"
    )

    enable_critique: bool = Field(
        default=True,
        description="Enable critic agent for iterative refinement"
    )

    min_sub_questions: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Minimum number of research sub-questions to generate"
    )

    max_sub_questions: int = Field(
        default=8,
        ge=1,
        le=15,
        description="Maximum number of research sub-questions to generate"
    )

    blueprint: Optional[Any] = Field(
        None,
        description="Visual workflow blueprint defining agent network structure"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "max_reflection_iterations": 3,
                "planner_model": "claude-3-5-sonnet-20240620",
                "researcher_model": "gpt-4o-mini",
                "writer_model": "claude-3-5-sonnet-20240620",
                "critic_model": "gpt-4o",
                "enable_web_search": True,
                "enable_critique": True
            }
        }


# =============================================================================
# Learning Research Strategy Configuration
# =============================================================================

class LearningResearchConfig(BaseModel):
    """
    Configuration for Learning Research workflow strategy.

    5-stage research with memory integration: Internal Review → Plan → Research → Synthesize → Assimilate.
    """

    enable_internal_review: bool = Field(
        default=True,
        description="Enable internal memory review before external research"
    )

    enable_memory_storage: bool = Field(
        default=True,
        description="Enable knowledge assimilation back into project memory"
    )

    enable_web_search: bool = Field(
        default=True,
        description="Enable web search for external research"
    )

    internal_reviewer_model: ModelChoice = Field(
        default="gpt-4o",
        description="Model for searching and reviewing internal project memory"
    )

    planner_model: ModelChoice = Field(
        default="claude-3.5-sonnet",
        description="Model for identifying knowledge gaps and planning research"
    )

    researcher_model: ModelChoice = Field(
        default="gpt-4o-mini",
        description="Model for conducting external research on knowledge gaps"
    )

    synthesizer_model: ModelChoice = Field(
        default="claude-3.5-sonnet",
        description="Model for synthesizing internal + external knowledge into reports"
    )

    curator_model: ModelChoice = Field(
        default="gpt-4o",
        description="Model for extracting insights and storing in memory"
    )

    memory_importance_threshold: int = Field(
        default=7,
        ge=1,
        le=10,
        description="Minimum importance score (1-10) for storing insights in memory"
    )

    blueprint: Optional[Any] = Field(
        None,
        description="Visual workflow blueprint defining agent network structure"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "enable_internal_review": True,
                "enable_memory_storage": True,
                "enable_web_search": True,
                "internal_reviewer_model": "gpt-4o",
                "planner_model": "claude-3-5-sonnet-20240620",
                "researcher_model": "gpt-4o-mini",
                "synthesizer_model": "claude-3-5-sonnet-20240620",
                "curator_model": "gpt-4o",
                "memory_importance_threshold": 7
            }
        }


# =============================================================================
# RLM (Recursive Language Model) Strategy Configuration
# =============================================================================

class RLMREPLType(str, Enum):
    """REPL environment types for RLM execution."""
    PYTHON = "python"
    IPYTHON = "ipython"
    RESTRICTED_PYTHON = "restricted_python"


class RLMConfig(BaseModel):
    """
    Configuration for RLM (Recursive Language Model) strategy.
    
    Enables agents to handle unbounded context by recursively decomposing
    analysis tasks and interacting with context via a Python REPL.
    """
    
    max_recursion_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum depth of recursive LM calls (1 = no recursion, just REPL)"
    )
    
    context_chunk_size: int = Field(
        default=50000,
        ge=1000,
        le=500000,
        description="Target size in characters for context chunks passed to recursive calls"
    )
    
    repl_type: RLMREPLType = Field(
        default=RLMREPLType.RESTRICTED_PYTHON,
        description="Type of Python REPL environment (restricted recommended for security)"
    )
    
    enable_parallelization: bool = Field(
        default=True,
        description="Allow parallel execution of independent recursive calls"
    )
    
    recursion_model: ModelChoice = Field(
        default="gpt-4o-mini",
        description="Model for recursive sub-analysis (cheaper model for efficiency)"
    )
    
    synthesis_model: ModelChoice = Field(
        default="gpt-4o",
        description="Model for root-level synthesis and final answer generation"
    )
    
    enable_code_execution: bool = Field(
        default=True,
        description="Allow agents to execute Python code in REPL for context manipulation"
    )
    
    timeout_per_depth: int = Field(
        default=120,
        ge=30,
        le=600,
        description="Maximum execution time in seconds per recursion depth level"
    )
    
    allowed_imports: List[str] = Field(
        default=["re", "json", "math", "datetime", "collections"],
        description="Python modules allowed in REPL (for security)"
    )
    
    enable_cost_tracking: bool = Field(
        default=True,
        description="Track and log token usage and cost per recursion level"
    )
    
    blueprint: Optional[Any] = Field(
        None,
        description="Visual workflow blueprint defining agent network structure"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "max_recursion_depth": 3,
                "context_chunk_size": 50000,
                "repl_type": "restricted_python",
                "enable_parallelization": True,
                "recursion_model": "gpt-4o-mini",
                "synthesis_model": "gpt-4o",
                "enable_code_execution": True,
                "timeout_per_depth": 120,
                "enable_cost_tracking": True
            }
        }


class RLMRAGHybridConfig(BaseModel):
    """
    Configuration for RLM + RAG Hybrid strategy.
    
    Combines vector search (RAG) for context narrowing with RLM for
    recursive analysis. Ideal for massive codebases and documents.
    """
    
    max_recursion_depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum depth of recursive calls (lower than pure RLM due to pre-filtered context)"
    )
    
    rag_top_k: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Number of vector search results to retrieve before RLM analysis"
    )
    
    context_chunk_size: int = Field(
        default=50000,
        ge=1000,
        le=500000,
        description="Target size in characters for context chunks"
    )
    
    repl_type: RLMREPLType = Field(
        default=RLMREPLType.RESTRICTED_PYTHON,
        description="Type of Python REPL environment"
    )
    
    enable_parallelization: bool = Field(
        default=True,
        description="Allow parallel execution of recursive calls"
    )
    
    recursion_model: ModelChoice = Field(
        default="gpt-4o-mini",
        description="Model for recursive analysis"
    )
    
    synthesis_model: ModelChoice = Field(
        default="gpt-4o",
        description="Model for final synthesis"
    )
    
    enable_hyde: bool = Field(
        default=True,
        description="Use HyDE (Hypothetical Document Embeddings) for better retrieval"
    )
    
    enable_dna_augmentation: bool = Field(
        default=True,
        description="Augment HyDE prompts with project DNA for context-aware retrieval"
    )
    
    timeout_per_depth: int = Field(
        default=120,
        ge=30,
        le=600,
        description="Maximum execution time in seconds per depth level"
    )
    
    allowed_imports: List[str] = Field(
        default=["re", "json", "math", "datetime", "collections"],
        description="Python modules allowed in REPL"
    )
    
    enable_cost_tracking: bool = Field(
        default=True,
        description="Track token usage and costs"
    )
    
    rag_rerank: bool = Field(
        default=True,
        description="Rerank retrieved chunks before passing to RLM"
    )
    
    blueprint: Optional[Any] = Field(
        None,
        description="Visual workflow blueprint defining agent network structure"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "max_recursion_depth": 2,
                "rag_top_k": 50,
                "context_chunk_size": 50000,
                "repl_type": "restricted_python",
                "enable_parallelization": True,
                "recursion_model": "gpt-4o-mini",
                "synthesis_model": "gpt-4o",
                "enable_hyde": True,
                "enable_dna_augmentation": True,
                "timeout_per_depth": 120,
                "enable_cost_tracking": True,
                "rag_rerank": True
            }
        }


# =============================================================================
# Factory and Utilities
# =============================================================================

def get_default_config(strategy: str) -> BaseModel:
    """
    Get default configuration for a strategy.
    
    Args:
        strategy: WorkflowStrategy enum value as string
        
    Returns:
        Default configuration instance for the strategy
    """
    from models.workflow_strategy import WorkflowStrategy
    
    strategy_enum = WorkflowStrategy(strategy)
    
    config_map = {
        WorkflowStrategy.DEFAULT_SEQUENTIAL: SequentialConfig(),
        WorkflowStrategy.ROMAN_LEGION: RomanLegionConfig(
            tiers=[
                RomanLegionTier(name="Hastati", model="gpt-4o-mini", max_retries=2),
                RomanLegionTier(name="Principes", model="gpt-4o", max_retries=1),
                RomanLegionTier(name="Triarii", model="o1-mini", max_retries=1)
            ]
        ),
        WorkflowStrategy.QUORUM_SENSING: QuorumSensingConfig(),
        WorkflowStrategy.STIGMERGY: StigmergyConfig(),
        WorkflowStrategy.DEEP_RESEARCH: DeepResearchConfig(),
        WorkflowStrategy.LEARNING_RESEARCH: LearningResearchConfig(),
        WorkflowStrategy.RLM: RLMConfig(),
        WorkflowStrategy.RLM_RAG_HYBRID: RLMRAGHybridConfig()
    }

    return config_map.get(strategy_enum, SequentialConfig())


class SchemaOutputMode(str, Enum):
    """Schema output detail modes."""
    FULL = "full"  # Complete schema with all metadata
    MINIMAL = "minimal"  # Only required fields and types
    COMPACT = "compact"  # No descriptions or examples


class SchemaOutputConfig(BaseModel):
    """
    Configuration for schema output formatting.

    Controls how workflow configuration schemas are generated and returned.
    Used by frontend to customize form generation and by API consumers
    who need different levels of schema detail.
    """

    mode: SchemaOutputMode = Field(
        default=SchemaOutputMode.FULL,
        description="Schema detail level"
    )

    include_descriptions: bool = Field(
        default=True,
        description="Include field descriptions in schema"
    )

    include_examples: bool = Field(
        default=True,
        description="Include example values in schema"
    )

    include_defaults: bool = Field(
        default=True,
        description="Include default values in schema"
    )

    include_constraints: bool = Field(
        default=True,
        description="Include validation constraints (min, max, enum, etc.)"
    )

    include_titles: bool = Field(
        default=True,
        description="Include field titles"
    )

    ref_template: Optional[str] = Field(
        default=None,
        description="Custom $ref template for definitions (e.g., '#/components/schemas/{model}')"
    )


def _filter_schema(schema: Dict[str, Any], config: SchemaOutputConfig) -> Dict[str, Any]:
    """
    Filter schema based on output configuration.

    Args:
        schema: Original JSON schema
        config: Schema output configuration

    Returns:
        Filtered schema dictionary
    """
    if config.mode == SchemaOutputMode.MINIMAL:
        # Keep only essential fields
        filtered = {
            "type": schema.get("type"),
            "properties": {},
            "required": schema.get("required", [])
        }

        for prop_name, prop_schema in schema.get("properties", {}).items():
            filtered["properties"][prop_name] = {
                "type": prop_schema.get("type"),
            }
            # Keep enum values as they're essential
            if "enum" in prop_schema and config.include_constraints:
                filtered["properties"][prop_name]["enum"] = prop_schema["enum"]

        return filtered

    elif config.mode == SchemaOutputMode.COMPACT:
        # Remove verbose metadata but keep structure
        filtered = schema.copy()

        def remove_verbose_fields(obj):
            if isinstance(obj, dict):
                obj.pop("description", None)
                obj.pop("examples", None)
                obj.pop("title", None)
                for value in obj.values():
                    remove_verbose_fields(value)
            elif isinstance(obj, list):
                for item in obj:
                    remove_verbose_fields(item)

        remove_verbose_fields(filtered)
        return filtered

    # FULL mode - apply granular filters
    filtered = schema.copy()

    def filter_property(prop_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Filter individual property schema."""
        result = prop_schema.copy()

        if not config.include_descriptions:
            result.pop("description", None)

        if not config.include_examples:
            result.pop("examples", None)
            result.pop("example", None)

        if not config.include_defaults:
            result.pop("default", None)

        if not config.include_constraints:
            result.pop("minimum", None)
            result.pop("maximum", None)
            result.pop("minLength", None)
            result.pop("maxLength", None)
            result.pop("pattern", None)
            # Keep enum as it defines valid values

        if not config.include_titles:
            result.pop("title", None)

        # Recursively filter nested properties
        if "properties" in result:
            result["properties"] = {
                k: filter_property(v)
                for k, v in result["properties"].items()
            }

        if "items" in result and isinstance(result["items"], dict):
            result["items"] = filter_property(result["items"])

        return result

    if "properties" in filtered:
        filtered["properties"] = {
            k: filter_property(v)
            for k, v in filtered["properties"].items()
        }

    if not config.include_descriptions:
        filtered.pop("description", None)

    if not config.include_titles:
        filtered.pop("title", None)

    # Apply custom $ref template if provided
    if config.ref_template and "$defs" in filtered:
        filtered["components"] = {"schemas": filtered.pop("$defs")}

    return filtered


def get_config_schema(
    strategy: str,
    schema_config: Optional[SchemaOutputConfig] = None
) -> Dict[str, Any]:
    """
    Get JSON schema for a strategy's configuration.

    Used by frontend to generate dynamic forms.

    Args:
        strategy: WorkflowStrategy enum value as string
        schema_config: Optional configuration for schema output formatting

    Returns:
        JSON schema dictionary
    """
    from models.workflow_strategy import WorkflowStrategy

    strategy_enum = WorkflowStrategy(strategy)

    schema_map = {
        WorkflowStrategy.DEFAULT_SEQUENTIAL: SequentialConfig,
        WorkflowStrategy.ROMAN_LEGION: RomanLegionConfig,
        WorkflowStrategy.QUORUM_SENSING: QuorumSensingConfig,
        WorkflowStrategy.STIGMERGY: StigmergyConfig,
        WorkflowStrategy.DEEP_RESEARCH: DeepResearchConfig,
        WorkflowStrategy.LEARNING_RESEARCH: LearningResearchConfig,
        WorkflowStrategy.RLM: RLMConfig,
        WorkflowStrategy.RLM_RAG_HYBRID: RLMRAGHybridConfig
    }

    config_class = schema_map.get(strategy_enum, SequentialConfig)

    # Use model_json_schema() for Pydantic v2 compatibility
    # This properly generates enum values in the schema
    try:
        schema = config_class.model_json_schema()
    except AttributeError:
        # Fallback to schema() for Pydantic v1
        schema = config_class.schema()

    # Apply schema output configuration if provided
    if schema_config:
        schema = _filter_schema(schema, schema_config)

    return schema
