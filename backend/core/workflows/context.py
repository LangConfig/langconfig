# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Runtime Context (LangGraph v1.0)

Defines runtime configuration that is passed to workflows and tools at invocation time.
This configuration is NOT part of the checkpointed state - it's transient context that
can change between invocations without modifying the state schema.

Key Benefits:
- Clean separation of state (what) vs. configuration (how)
- User-specific credentials accessible to tools
- Dynamic model selection at runtime
- Feature flags without state pollution
- Access to long-term memory via runtime.store

Example Usage:
    >>> context = WorkflowContext(
    ...     user_id=123,
    ...     project_id=456,
    ...     model_name="gpt-4o",
    ...     jira_email="user@example.com",
    ...     jira_api_token="token123"
    ... )
    >>>
    >>> result = await workflow.ainvoke(
    ...     initial_state,
    ...     context=context  # Pass context separately from state
    ... )
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class UserRole(str, Enum):
    """User permission levels for tool access control."""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass
class WorkflowContext:
    """
    Runtime configuration for workflows (NOT part of checkpointed state).

    This context is passed to every node and tool, providing access to:
    - User identification and permissions
    - Model selection and parameters
    - Execution configuration
    - User-specific credentials
    - Feature flags

    Access in nodes:
        def my_node(state: State, runtime: Runtime[WorkflowContext]):
            user_id = runtime.context.user_id
            model = runtime.context.model_name

    Access in tools:
        @tool
        def my_tool(arg: str, runtime: ToolRuntime[WorkflowContext]):
            api_key = runtime.context.jira_api_token
    """

    # === User Identification ===
    user_id: int
    project_id: int
    session_id: Optional[str] = None
    user_role: UserRole = UserRole.EDITOR

    # === Model Configuration ===
    model_name: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    enable_model_routing: bool = True  # Use complexity-based routing

    # === Execution Configuration ===
    max_retries: int = 3
    enable_hitl: bool = True
    checkpoint_mode: str = "selective"  # "all", "selective", "minimal"
    timeout_seconds: int = 300

    # === Feature Flags ===
    enable_memory: bool = True  # Long-term memory via store
    enable_rag: bool = True  # Codebase RAG
    enable_cost_tracking: bool = True
    enable_validation: bool = True
    enable_pattern_learning: bool = True

    # === User Credentials (for tools) ===
    # Jira
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    jira_url: Optional[str] = None

    # GitHub
    github_token: Optional[str] = None
    github_username: Optional[str] = None

    # Slack
    slack_token: Optional[str] = None
    slack_webhook_url: Optional[str] = None

    # AWS
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = None

    # === Tool Configuration ===
    allowed_tools: Optional[List[str]] = None  # If set, restrict to these tools
    blocked_tools: Optional[List[str]] = None  # Tools to exclude
    mcp_tools_enabled: bool = True
    cli_tools_enabled: bool = True

    # === Middleware Configuration ===
    middleware_config: Dict[str, Any] = field(default_factory=dict)

    # === Custom Metadata ===
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    """
    Simplified context for tools that don't need full workflow context.

    Tools can use either WorkflowContext or ToolContext.
    ToolContext is lighter-weight for simple tools.

    Example:
        @tool
        def simple_tool(arg: str, runtime: ToolRuntime[ToolContext]):
            user_id = runtime.context.user_id
            # Access store
            data = runtime.store.get(("namespace",), "key")
    """

    user_id: int
    project_id: int
    enable_memory: bool = True


@dataclass
class AgentContext:
    """
    Context for individual agent nodes (when using create_agent).

    This extends WorkflowContext with agent-specific configuration.
    """

    # Base workflow context
    workflow_context: WorkflowContext

    # Agent-specific configuration
    agent_id: str
    agent_role: str
    system_prompt: str

    # Agent-specific tools
    available_tools: List[str] = field(default_factory=list)

    # Agent-specific middleware
    middleware: List[Any] = field(default_factory=list)

    @classmethod
    def from_workflow_context(
        cls,
        workflow_context: WorkflowContext,
        agent_id: str,
        agent_role: str,
        system_prompt: str,
        available_tools: Optional[List[str]] = None,
        middleware: Optional[List[Any]] = None
    ) -> "AgentContext":
        """Create AgentContext from WorkflowContext."""
        return cls(
            workflow_context=workflow_context,
            agent_id=agent_id,
            agent_role=agent_role,
            system_prompt=system_prompt,
            available_tools=available_tools or [],
            middleware=middleware or []
        )


# === Helper Functions ===

def create_default_context(
    user_id: int,
    project_id: int,
    **kwargs
) -> WorkflowContext:
    """
    Create a default WorkflowContext with sensible defaults.

    Args:
        user_id: User identifier
        project_id: Project identifier
        **kwargs: Override any default values

    Returns:
        WorkflowContext with defaults applied

    Example:
        >>> context = create_default_context(
        ...     user_id=123,
        ...     project_id=456,
        ...     model_name="claude-3-5-sonnet",
        ...     enable_hitl=False
        ... )
    """
    return WorkflowContext(
        user_id=user_id,
        project_id=project_id,
        **kwargs
    )


def context_from_request(request_data: Dict[str, Any]) -> WorkflowContext:
    """
    Create WorkflowContext from API request data.

    Args:
        request_data: Dictionary with user, project, and config data

    Returns:
        WorkflowContext instance

    Example:
        >>> request = {
        ...     "user_id": 123,
        ...     "project_id": 456,
        ...     "config": {
        ...         "model_name": "gpt-4o",
        ...         "enable_hitl": True
        ...     }
        ... }
        >>> context = context_from_request(request)
    """
    user_id = request_data["user_id"]
    project_id = request_data["project_id"]
    config = request_data.get("config", {})

    return WorkflowContext(
        user_id=user_id,
        project_id=project_id,
        **config
    )


def load_user_credentials(
    user_id: int,
    db_session: Any
) -> Dict[str, Optional[str]]:
    """
    Load user credentials from database for context.

    Args:
        user_id: User identifier
        db_session: Database session

    Returns:
        Dictionary of credential values

    Example:
        >>> creds = load_user_credentials(123, db)
        >>> context = WorkflowContext(
        ...     user_id=123,
        ...     project_id=456,
        ...     **creds
        ... )
    """
    # TODO: Implement actual database query
    # This is a placeholder that should query your user_credentials table

    return {
        "jira_email": None,
        "jira_api_token": None,
        "jira_url": None,
        "github_token": None,
        "github_username": None,
        "slack_token": None,
        "aws_access_key_id": None,
        "aws_secret_access_key": None,
        "aws_region": None,
    }
