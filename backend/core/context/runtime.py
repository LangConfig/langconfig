# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Runtime Context for LangGraph v1.0

Implements the modern context pattern that replaces config["configurable"].
Runtime context provides type-safe, structured access to execution metadata.

v1.0 Pattern:
    agent.invoke(
        {"messages": [...]},
        context=Context(user_id="123", session_id="abc")
    )

Old Pattern (deprecated):
    agent.invoke(
        {"messages": [...]},
        config={"configurable": {"user_id": "123"}}
    )

Example:
    >>> from dataclasses import dataclass
    >>> from core.context.runtime import RuntimeContext
    >>>
    >>> @dataclass
    >>> class MyContext(RuntimeContext):
    ...     user_id: str
    ...     session_id: str
    ...     user_role: str = "user"
    >>>
    >>> context = MyContext(user_id="123", session_id="abc", user_role="expert")
    >>> agent.invoke(state, context=context)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# Base Runtime Context
# =============================================================================

@dataclass
class RuntimeContext:
    """
    Base class for runtime context in v1.0.

    Runtime context provides type-safe access to execution metadata
    without polluting the agent state.

    Usage:
        @dataclass
        class MyContext(RuntimeContext):
            custom_field: str

        agent.invoke(state, context=MyContext(custom_field="value"))
    """

    # Common fields that most contexts will need
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentRuntimeContext(RuntimeContext):
    """
    Runtime context for agent execution.

    Contains metadata about the current execution environment,
    user, project, and task.

    Example:
        >>> context = AgentRuntimeContext(
        ...     user_id="user_123",
        ...     project_id=1,
        ...     task_id=456,
        ...     session_id="session_abc"
        ... )
        >>> agent.invoke(state, context=context)
    """

    # User context
    user_id: Optional[str] = None
    user_role: str = "user"  # "user", "expert", "admin", etc.
    user_preferences: Dict[str, Any] = field(default_factory=dict)

    # Project context
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    task_id: Optional[int] = None
    task_type: Optional[str] = None  # "code", "research", "design", etc.

    # Session context
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    thread_id: Optional[str] = None  # For checkpointing

    # Execution context
    environment: str = "production"  # "development", "staging", "production"
    debug_mode: bool = False
    verbose: bool = False

    # Feature flags
    enable_summarization: bool = True
    enable_hitl: bool = False
    enable_cost_tracking: bool = True

    # Limits and constraints
    max_iterations: int = 10
    max_tokens: Optional[int] = None
    timeout_seconds: Optional[int] = None

    # Custom metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowRuntimeContext(AgentRuntimeContext):
    """
    Extended runtime context for workflow execution.

    Adds workflow-specific fields like strategy, tier, and execution mode.

    Example:
        >>> context = WorkflowRuntimeContext(
        ...     user_id="user_123",
        ...     project_id=1,
        ...     workflow_strategy="roman_legion",
        ...     current_tier="principes"
        ... )
    """

    # Workflow context
    workflow_id: Optional[str] = None
    workflow_strategy: Optional[str] = None  # "default", "roman_legion", etc.
    current_tier: Optional[str] = None  # For tiered strategies
    execution_mode: str = "normal"  # "normal", "fast", "thorough"

    # Retry and recovery
    retry_count: int = 0
    max_retries: int = 3
    enable_auto_retry: bool = True

    # Resource limits
    cost_limit: Optional[float] = None  # Max cost in dollars
    token_budget: Optional[int] = None  # Max tokens
    time_budget_seconds: Optional[int] = None  # Max execution time


# =============================================================================
# Context Builder (Convenience)
# =============================================================================

class RuntimeContextBuilder:
    """
    Builder for creating runtime contexts with sensible defaults.

    Example:
        >>> context = (RuntimeContextBuilder()
        ...     .for_user("user_123", role="expert")
        ...     .for_project(1, task_id=456)
        ...     .with_session("session_abc")
        ...     .with_limits(max_iterations=5, timeout_seconds=300)
        ...     .build())
    """

    def __init__(self):
        self._data = {}

    def for_user(self, user_id: str, role: str = "user", preferences: Optional[Dict] = None) -> "RuntimeContextBuilder":
        """Set user context."""
        self._data["user_id"] = user_id
        self._data["user_role"] = role
        if preferences:
            self._data["user_preferences"] = preferences
        return self

    def for_project(self, project_id: int, project_name: Optional[str] = None, task_id: Optional[int] = None) -> "RuntimeContextBuilder":
        """Set project context."""
        self._data["project_id"] = project_id
        if project_name:
            self._data["project_name"] = project_name
        if task_id:
            self._data["task_id"] = task_id
        return self

    def with_session(self, session_id: str, conversation_id: Optional[str] = None, thread_id: Optional[str] = None) -> "RuntimeContextBuilder":
        """Set session context."""
        self._data["session_id"] = session_id
        if conversation_id:
            self._data["conversation_id"] = conversation_id
        if thread_id:
            self._data["thread_id"] = thread_id
        return self

    def with_workflow(self, workflow_id: str, strategy: Optional[str] = None, mode: str = "normal") -> "RuntimeContextBuilder":
        """Set workflow context."""
        self._data["workflow_id"] = workflow_id
        if strategy:
            self._data["workflow_strategy"] = strategy
        self._data["execution_mode"] = mode
        return self

    def with_limits(
        self,
        max_iterations: Optional[int] = None,
        max_tokens: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        cost_limit: Optional[float] = None
    ) -> "RuntimeContextBuilder":
        """Set execution limits."""
        if max_iterations:
            self._data["max_iterations"] = max_iterations
        if max_tokens:
            self._data["max_tokens"] = max_tokens
        if timeout_seconds:
            self._data["timeout_seconds"] = timeout_seconds
        if cost_limit:
            self._data["cost_limit"] = cost_limit
        return self

    def with_features(
        self,
        enable_summarization: bool = True,
        enable_hitl: bool = False,
        enable_cost_tracking: bool = True
    ) -> "RuntimeContextBuilder":
        """Set feature flags."""
        self._data["enable_summarization"] = enable_summarization
        self._data["enable_hitl"] = enable_hitl
        self._data["enable_cost_tracking"] = enable_cost_tracking
        return self

    def debug(self, enabled: bool = True, verbose: bool = False) -> "RuntimeContextBuilder":
        """Enable debug mode."""
        self._data["debug_mode"] = enabled
        self._data["verbose"] = verbose
        return self

    def with_metadata(self, **metadata) -> "RuntimeContextBuilder":
        """Add custom metadata."""
        if "metadata" not in self._data:
            self._data["metadata"] = {}
        self._data["metadata"].update(metadata)
        return self

    def build(self, context_class=AgentRuntimeContext) -> RuntimeContext:
        """Build the runtime context."""
        return context_class(**self._data)

    def build_workflow_context(self) -> WorkflowRuntimeContext:
        """Build workflow-specific context."""
        return self.build(WorkflowRuntimeContext)


# =============================================================================
# Context Utilities
# =============================================================================

def extract_context_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract runtime context from old-style config (backward compatibility).

    Converts config["configurable"] to context-compatible dict.

    Args:
        config: Old-style config with configurable dict

    Returns:
        Dict suitable for creating RuntimeContext

    Example:
        >>> config = {"configurable": {"user_id": "123", "project_id": 1}}
        >>> context_data = extract_context_from_config(config)
        >>> context = AgentRuntimeContext(**context_data)
    """
    configurable = config.get("configurable", {})

    # Map old keys to new keys
    context_data = {}

    # User context
    if "user_id" in configurable:
        context_data["user_id"] = configurable["user_id"]
    if "user_role" in configurable:
        context_data["user_role"] = configurable["user_role"]

    # Project context
    if "project_id" in configurable:
        context_data["project_id"] = configurable["project_id"]
    if "task_id" in configurable:
        context_data["task_id"] = configurable["task_id"]

    # Session context
    if "session_id" in configurable:
        context_data["session_id"] = configurable["session_id"]
    if "thread_id" in configurable:
        context_data["thread_id"] = configurable["thread_id"]

    return context_data


def create_config_from_context(context: RuntimeContext) -> Dict[str, Any]:
    """
    Create old-style config from runtime context (backward compatibility).

    Converts RuntimeContext to config["configurable"] format.

    Args:
        context: Runtime context instance

    Returns:
        Config dict with configurable section

    Example:
        >>> context = AgentRuntimeContext(user_id="123", project_id=1)
        >>> config = create_config_from_context(context)
        >>> # config = {"configurable": {"user_id": "123", "project_id": 1}}
    """
    configurable = {}

    # Extract fields from context
    if hasattr(context, "user_id") and context.user_id:
        configurable["user_id"] = context.user_id
    if hasattr(context, "user_role"):
        configurable["user_role"] = context.user_role
    if hasattr(context, "project_id") and context.project_id:
        configurable["project_id"] = context.project_id
    if hasattr(context, "task_id") and context.task_id:
        configurable["task_id"] = context.task_id
    if hasattr(context, "session_id") and context.session_id:
        configurable["session_id"] = context.session_id
    if hasattr(context, "thread_id") and context.thread_id:
        configurable["thread_id"] = context.thread_id

    return {"configurable": configurable}


# =============================================================================
# Context Validation
# =============================================================================

def validate_context(context: RuntimeContext, required_fields: Optional[List[str]] = None) -> None:
    """
    Validate runtime context has required fields.

    Args:
        context: Runtime context to validate
        required_fields: List of required field names

    Raises:
        ValueError: If required fields are missing

    Example:
        >>> context = AgentRuntimeContext(user_id="123")
        >>> validate_context(context, required_fields=["user_id", "project_id"])
        ValueError: Missing required context fields: project_id
    """
    if not required_fields:
        return

    missing = []
    for field in required_fields:
        if not hasattr(context, field) or getattr(context, field) is None:
            missing.append(field)

    if missing:
        raise ValueError(f"Missing required context fields: {', '.join(missing)}")


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Example 1: Simple context
    context1 = AgentRuntimeContext(
        user_id="user_123",
        project_id=1,
        task_id=456
    )

    print("Example 1:", context1)

    # Example 2: Using builder
    context2 = (RuntimeContextBuilder()
        .for_user("user_123", role="expert")
        .for_project(1, task_id=456)
        .with_session("session_abc")
        .with_limits(max_iterations=5, timeout_seconds=300)
        .debug(enabled=True)
        .build())

    print("Example 2:", context2)

    # Example 3: Workflow context
    context3 = (RuntimeContextBuilder()
        .for_user("user_123")
        .for_project(1)
        .with_workflow("wf_123", strategy="roman_legion")
        .build_workflow_context())

    print("Example 3:", context3)

    # Example 4: Backward compatibility
    old_config = {
        "configurable": {
            "user_id": "123",
            "project_id": 1,
            "task_id": 456
        }
    }

    context_data = extract_context_from_config(old_config)
    context4 = AgentRuntimeContext(**context_data)

    print("Example 4:", context4)

    # Convert back to old format
    new_config = create_config_from_context(context4)
    print("Converted back:", new_config)
