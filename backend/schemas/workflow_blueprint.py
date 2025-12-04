# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Blueprint Schemas for Dynamic LangGraph Construction.

This module defines JSON-serializable blueprints that describe the structure
of workflow graphs for each strategy. These blueprints enable:

1. Dynamic graph construction at runtime
2. Strategy-specific workflow topologies  
3. UI visualization of workflow structure
4. User customization 

Instead of one massive static graph with all possible paths, we build
strategy-specific graphs on-demand from these blueprints.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any, Union
from enum import Enum


class ContextStrategy(str, Enum):
    """Context retrieval strategies from pgvector."""
    SEMANTIC = "semantic"  # Pure vector similarity
    KEYWORD = "keyword"  # Full-text search
    HYBRID = "hybrid"  # Combination of both
    GRAPH = "graph"  # Code graph-aware retrieval


class ContextRefreshStrategy(str, Enum):
    """When to refresh context during workflow execution."""
    PER_NODE = "per_node"  # Query fresh context at each node
    PER_WORKFLOW = "per_workflow"  # Query once at start
    ON_DEMAND = "on_demand"  # Only when explicitly requested


class ContextFilters(BaseModel):
    """Filters for context document retrieval."""
    
    tags: Optional[List[str]] = Field(
        None,
        description="Only include documents with these tags"
    )
    
    file_patterns: Optional[List[str]] = Field(
        None,
        description="Glob patterns to include (e.g., ['*.py', 'src/**'])"
    )
    
    exclude_patterns: Optional[List[str]] = Field(
        None,
        description="Glob patterns to exclude (e.g., ['*.test.js'])"
    )
    
    min_similarity: Optional[float] = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for retrieval (0.0-1.0)"
    )
    
    max_age_days: Optional[int] = Field(
        None,
        ge=0,
        description="Only include documents indexed within N days"
    )
    
    languages: Optional[List[str]] = Field(
        None,
        description="Programming languages to include (e.g., ['python', 'typescript'])"
    )


class ContextConfig(BaseModel):
    """Comprehensive context configuration for a node."""
    
    enable_context: bool = Field(
        True,
        description="Whether to retrieve context documents for this node"
    )
    
    context_limit: int = Field(
        5,
        ge=0,
        le=50,
        description="Maximum number of context documents to retrieve"
    )
    
    context_strategy: ContextStrategy = Field(
        ContextStrategy.SEMANTIC,
        description="Strategy for retrieving context documents"
    )
    
    pinned_document_ids: Optional[List[int]] = Field(
        None,
        description="Document IDs to always include in context (bypasses retrieval)"
    )
    
    context_filters: Optional[ContextFilters] = Field(
        None,
        description="Filters to apply during context retrieval"
    )
    
    context_refresh_strategy: ContextRefreshStrategy = Field(
        ContextRefreshStrategy.PER_NODE,
        description="When to refresh context during workflow"
    )
    
    log_context_usage: bool = Field(
        True,
        description="Log context usage metrics for observability"
    )
    
    token_budget: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum tokens to allocate for context (auto-truncate if exceeded)"
    )
    
    include_code_graph: bool = Field(
        False,
        description="Include code dependency graph in context"
    )
    
    context_window_overlap: int = Field(
        50,
        ge=0,
        le=500,
        description="Character overlap between context chunks"
    )


class NodeType(str, Enum):
    """
    Types of nodes that can appear in a workflow graph.

    IMPORTANT: Parallelism in LangConfig
    ====================================
    There are TWO distinct types of parallelism in LangConfig:

    1. Tool-Level Parallelism (Built into LangGraph):
       - One agent calling multiple tools simultaneously
       - Handled automatically by LangGraph's ToolNode
       - Controlled via `enable_parallel_tools` agent configuration flag
       - Example: "Get weather in SF, NYC, and LA" → 3 parallel API calls
       - Implementation: When an LLM generates multiple ToolCall objects,
         LangGraph's ToolNode executes them concurrently using asyncio
       - No custom code needed - this is the default behavior

    2. Agent-Level Parallelism (Custom Workflow Orchestration):
       - Multiple independent agents running in parallel
       - Implemented using PARALLEL_AGENT_EXECUTOR node type
       - Uses asyncio.gather() on multiple agent invocations
       - Example: Spawning 5 research agents to investigate different topics
       - Implementation: Strategy methods like execute_parallel_research()
       - This is a legitimate workflow pattern not covered by LangGraph

    The PARALLEL_AGENT_EXECUTOR node type represents agent-level parallelism (type #2).
    It does NOT implement tool-level parallelism, which is already built into LangGraph.
    """
    # Core System Nodes
    START = "start"
    END = "end"
    ROUTER = "router"  # Conditional routing based on state

    # Agent Nodes - Reasoning & Planning
    AGENT_PLANNER = "agent_planner"  # Breaks down complex tasks
    AGENT_RESEARCHER = "agent_researcher"  # Conducts research (web, docs, etc.)
    AGENT_ANALYST = "agent_analyst"  # Analyzes data/information
    AGENT_WRITER = "agent_writer"  # Creates content/documentation
    AGENT_CRITIC = "agent_critic"  # Reviews and critiques output
    AGENT_CODER = "agent_coder"  # Writes/modifies code
    AGENT_QA = "agent_qa"  # Tests and validates
    AGENT_CUSTOM = "agent_custom"  # User-defined agent

    # Data & Context Nodes
    CONTEXT_ASSEMBLY = "context_assembly"  # Gathers relevant context
    CONTEXT_SYNTHESIS = "context_synthesis"  # Combines/summarizes context
    MEMORY_SEARCH = "memory_search"  # Searches long-term memory
    MEMORY_STORE = "memory_store"  # Stores to long-term memory
    WEB_SEARCH = "web_search"  # Web search tool
    CODE_SEARCH = "code_search"  # Searches codebase
    DOCUMENT_RETRIEVAL = "document_retrieval"  # RAG retrieval

    # Processing Nodes
    MODEL_ROUTER = "model_router"  # Routes to optimal model (cost/performance)
    PARALLEL_AGENT_EXECUTOR = "parallel_agent_executor"  # Spawns multiple independent agents in parallel (agent-level, not tool-level)
    AGGREGATOR = "aggregator"  # Combines multiple outputs
    VALIDATOR = "validator"  # Validates output against criteria
    TRANSFORMER = "transformer"  # Transforms data format

    # Control Flow Nodes
    HUMAN_REVIEW = "human_review"  # HITL approval gate
    LOOP = "loop"  # Iteration/retry logic
    BRANCH = "branch"  # Conditional branching
    GATE = "gate"  # Wait for multiple inputs

    # Legacy (deprecated - will be removed)
    INITIALIZE = "initialize"
    EXECUTE = "execute"
    VALIDATE = "validate"
    SYNTHESIZE_CONTEXT = "synthesize_context"
    HANDLE_HITL = "handle_hitl"
    RETRY = "retry"
    COMPLETE = "complete"
    

class BlueprintNode(BaseModel):
    """
    Defines a single node in the workflow graph.
    
    The node_id links to the actual implementation function, either:
    1. Generic workflow_nodes.py function (e.g., "initialize_workflow_node")
    2. Strategy handler method (e.g., strategy.prepare_execution)
    """
    
    node_id: str = Field(
        ...,
        description="Unique identifier for this node in the graph",
        min_length=1,
        max_length=50
    )
    
    display_name: str = Field(
        ...,
        description="Human-readable name for UI display",
        min_length=1,
        max_length=100
    )
    
    node_type: NodeType = Field(
        ...,
        description="Type of node (determines behavior)"
    )
    
    handler_function: str = Field(
        ...,
        description="Function to execute for this node. Format: 'module.function' or 'strategy.method'",
        min_length=1
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata for UI rendering (icons, colors, etc.)"
    )
    
    agent_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional agent-specific configuration for this node (model, temperature, system_prompt, etc.)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "execute_code",
                "display_name": "Execute Code",
                "node_type": "execute",
                "handler_function": "workflow_nodes.execute_code_node",
                "metadata": {"icon": "code", "color": "blue"},
                "agent_config": {
                    "model": "gpt-4o",
                    "temperature": 0.7,
                    "system_prompt": "You are a code execution specialist.",
                    "max_retries": 2
                }
            }
        }


class EdgeType(str, Enum):
    """Types of edges connecting nodes."""
    DIRECT = "direct"  # Simple A -> B transition
    CONDITIONAL = "conditional"  # A -> (condition) -> B or C


class BlueprintEdge(BaseModel):
    """
    Defines an edge (connection) between nodes.
    
    Edges can be:
    - Direct: source -> target
    - Conditional: source -> [routing function] -> multiple targets
    """
    
    source_id: str = Field(
        ...,
        description="Node ID that this edge originates from"
    )
    
    edge_type: EdgeType = Field(
        default=EdgeType.DIRECT,
        description="Type of edge"
    )
    
    # For DIRECT edges
    target_id: Optional[str] = Field(
        None,
        description="Target node ID (for direct edges). Use '__END__' for terminal edges"
    )
    
    # For CONDITIONAL edges
    condition_function: Optional[str] = Field(
        None,
        description="Routing function that returns the key for routing_map. Format: 'module.function'"
    )
    
    routing_map: Optional[Dict[str, str]] = Field(
        None,
        description="Map of condition result -> target node ID"
    )
    
    @validator('routing_map', always=True)
    def validate_edge_consistency(cls, v, values):
        """Ensure edge has either target_id or (condition_function + routing_map)."""
        edge_type = values.get('edge_type')
        target_id = values.get('target_id')
        condition_function = values.get('condition_function')
        routing_map = v
        
        if edge_type == EdgeType.DIRECT:
            if not target_id:
                raise ValueError("Direct edges must have target_id")
        elif edge_type == EdgeType.CONDITIONAL:
            if not condition_function or not routing_map:
                raise ValueError("Conditional edges must have condition_function and routing_map")
        
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "source_id": "execute_code",
                    "edge_type": "direct",
                    "target_id": "validate"
                },
                {
                    "source_id": "validate",
                    "edge_type": "conditional",
                    "condition_function": "workflow_graph.route_after_validation",
                    "routing_map": {
                        "complete": "complete_workflow",
                        "hitl": "handle_hitl",
                        "retry": "retry_workflow",
                        "end": "__END__"
                    }
                }
            ]
        }


class WorkflowBlueprint(BaseModel):
    """
    Complete blueprint defining a workflow graph structure.
    
    This is a declarative, JSON-serializable definition that can be:
    1. Stored in the database (for custom workflows)
    2. Version controlled (for built-in strategies)
    3. Sent to frontend (for visualization)
    4. Used to construct LangGraph instances at runtime
    """
    
    strategy_type: str = Field(
        ...,
        description="WorkflowStrategy enum value this blueprint implements"
    )
    
    name: str = Field(
        ...,
        description="Human-readable name for this workflow",
        min_length=1,
        max_length=100
    )
    
    description: Optional[str] = Field(
        None,
        description="Detailed description of this workflow"
    )
    
    version: str = Field(
        default="1.0.0",
        description="Blueprint version for compatibility tracking"
    )
    
    nodes: List[BlueprintNode] = Field(
        ...,
        min_items=1,
        description="List of nodes in the workflow graph"
    )
    
    edges: List[BlueprintEdge] = Field(
        ...,
        min_items=1,
        description="List of edges connecting nodes"
    )
    
    entry_point_id: str = Field(
        ...,
        description="Node ID to start execution from"
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata (author, tags, etc.)"
    )
    
    @validator('nodes')
    def validate_node_ids_unique(cls, v):
        """Ensure all node IDs are unique."""
        node_ids = [node.node_id for node in v]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Node IDs must be unique")
        return v
    
    @validator('entry_point_id')
    def validate_entry_point_exists(cls, v, values):
        """Ensure entry_point_id references an actual node."""
        nodes = values.get('nodes', [])
        node_ids = {node.node_id for node in nodes}
        if v not in node_ids:
            raise ValueError(f"entry_point_id '{v}' must reference an existing node")
        return v
    
    @validator('edges')
    def validate_edge_references(cls, v, values):
        """Ensure all edges reference valid nodes."""
        nodes = values.get('nodes', [])
        node_ids = {node.node_id for node in nodes}
        node_ids.add("__END__")  # Special terminal node
        
        for edge in v:
            if edge.source_id not in node_ids:
                raise ValueError(f"Edge source_id '{edge.source_id}' references non-existent node")
            
            if edge.edge_type == EdgeType.DIRECT:
                if edge.target_id and edge.target_id not in node_ids:
                    raise ValueError(f"Edge target_id '{edge.target_id}' references non-existent node")
            
            elif edge.edge_type == EdgeType.CONDITIONAL:
                for target in edge.routing_map.values():
                    if target not in node_ids:
                        raise ValueError(f"Routing target '{target}' references non-existent node")
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "strategy_type": "DEFAULT_SEQUENTIAL",
                "name": "Sequential Execution",
                "description": "Single-agent execution with retries",
                "version": "1.0.0",
                "entry_point_id": "initialize",
                "nodes": [
                    {
                        "node_id": "initialize",
                        "display_name": "Initialize Workflow",
                        "node_type": "initialize",
                        "handler_function": "workflow_nodes.initialize_workflow_node"
                    },
                    {
                        "node_id": "execute_code",
                        "display_name": "Execute Code",
                        "node_type": "execute",
                        "handler_function": "workflow_nodes.execute_code_node"
                    }
                ],
                "edges": [
                    {
                        "source_id": "initialize",
                        "edge_type": "direct",
                        "target_id": "execute_code"
                    }
                ]
            }
        }


class BlueprintLibrary(BaseModel):
    """
    Collection of blueprints, useful for storing multiple strategy definitions.
    """
    
    blueprints: List[WorkflowBlueprint] = Field(
        ...,
        description="List of workflow blueprints"
    )
    
    @validator('blueprints')
    def validate_unique_strategies(cls, v):
        """Ensure each strategy_type appears only once."""
        strategy_types = [bp.strategy_type for bp in v]
        if len(strategy_types) != len(set(strategy_types)):
            raise ValueError("Each strategy_type must appear only once in the library")
        return v
