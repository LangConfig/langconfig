# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Model Hooks for LangConfig Agent Factory

Implements pre/post-model hooks for context injection, output validation,
and request/response transformation. This is a LangChain v1-alpha feature
that enables powerful runtime modifications without changing agent logic.

Use Cases:
- Context injection (add timestamps, user info, project metadata)
- Output validation (ensure responses meet quality standards)
- Request transformation (add system context, enhance prompts)
- Response transformation (format, sanitize, enrich outputs)
- Logging and monitoring (track model usage, performance)

Example:
    >>> from core.models.hooks import TimestampHook, ValidationHook
    >>> hooks = [TimestampHook(), ValidationHook(min_length=10)]
    >>> agent = AgentFactory.create_agent(
    ...     agent_config={"model_hooks": hooks, ...},
    ...     ...
    ... )
"""

import logging
import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from abc import ABC, abstractmethod
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda

logger = logging.getLogger(__name__)


# =============================================================================
# Base Hook Classes
# =============================================================================

class ModelHook(ABC):
    """
    Base class for model hooks.

    Hooks can intercept and modify model inputs/outputs at runtime.
    """

    @abstractmethod
    def pre_model(self, messages: List[BaseMessage], config: Dict[str, Any]) -> List[BaseMessage]:
        """
        Called BEFORE the model processes messages.

        Args:
            messages: Input messages to the model
            config: Runtime configuration

        Returns:
            Modified messages (or original if no changes)
        """
        pass

    @abstractmethod
    def post_model(self, response: AIMessage, config: Dict[str, Any]) -> AIMessage:
        """
        Called AFTER the model generates a response.

        Args:
            response: Model's response message
            config: Runtime configuration

        Returns:
            Modified response (or original if no changes)
        """
        pass


# =============================================================================
# Built-in Hooks
# =============================================================================

class TimestampHook(ModelHook):
    """
    Adds timestamps to model context.

    Injects current timestamp into system messages so the model knows
    the current date/time for time-sensitive queries.

    Example:
        >>> hook = TimestampHook()
        >>> # Model will receive: "Current time: 2025-10-08 10:30:00 UTC"
    """

    def __init__(self, timezone: str = "UTC", format: str = "%Y-%m-%d %H:%M:%S"):
        self.timezone = timezone
        self.format = format

    def pre_model(self, messages: List[BaseMessage], config: Dict[str, Any]) -> List[BaseMessage]:
        """Add timestamp to context."""
        timestamp = datetime.utcnow().strftime(self.format)

        # Add timestamp as system message at the beginning
        timestamp_msg = SystemMessage(
            content=f"Current time: {timestamp} {self.timezone}"
        )

        # Insert after any existing system messages
        insert_idx = 0
        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage):
                insert_idx = i + 1
            else:
                break

        modified = messages.copy()
        modified.insert(insert_idx, timestamp_msg)

        logger.debug(f"Added timestamp: {timestamp} {self.timezone}")
        return modified

    def post_model(self, response: AIMessage, config: Dict[str, Any]) -> AIMessage:
        """No post-processing needed."""
        return response


class ProjectContextHook(ModelHook):
    """
    Injects project and task metadata into model context.

    Adds information about the current project, task, and user
    to help the model understand the broader context.

    Example:
        >>> hook = ProjectContextHook()
        >>> # Model receives: "Project: MyApp, Task: #123, User: john@example.com"
    """

    def pre_model(self, messages: List[BaseMessage], config: Dict[str, Any]) -> List[BaseMessage]:
        """Add project/task context."""

        # Extract context from config
        project_id = config.get("project_id")
        task_id = config.get("task_id")
        user_id = config.get("user_id")

        if not (project_id or task_id):
            return messages  # No context to add

        # Build context message
        context_parts = []
        if project_id:
            context_parts.append(f"Project ID: {project_id}")
        if task_id:
            context_parts.append(f"Task ID: {task_id}")
        if user_id:
            context_parts.append(f"User: {user_id}")

        context_msg = SystemMessage(
            content=f"Context: {', '.join(context_parts)}"
        )

        # Insert after system messages
        insert_idx = 0
        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage):
                insert_idx = i + 1
            else:
                break

        modified = messages.copy()
        modified.insert(insert_idx, context_msg)

        logger.debug(f"Added project context: {', '.join(context_parts)}")
        return modified

    def post_model(self, response: AIMessage, config: Dict[str, Any]) -> AIMessage:
        """No post-processing needed."""
        return response


class ValidationHook(ModelHook):
    """
    Validates model outputs for quality and safety.

    Checks responses for:
    - Minimum/maximum length
    - Prohibited content
    - Required patterns
    - Format validation

    Example:
        >>> hook = ValidationHook(
        ...     min_length=10,
        ...     max_length=5000,
        ...     prohibited_patterns=["DELETE FROM", "DROP TABLE"]
        ... )
    """

    def __init__(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        prohibited_patterns: Optional[List[str]] = None,
        required_patterns: Optional[List[str]] = None
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.prohibited_patterns = prohibited_patterns or []
        self.required_patterns = required_patterns or []

    def pre_model(self, messages: List[BaseMessage], config: Dict[str, Any]) -> List[BaseMessage]:
        """No pre-processing needed."""
        return messages

    def post_model(self, response: AIMessage, config: Dict[str, Any]) -> AIMessage:
        """Validate response."""
        content = response.content

        # Length validation
        if self.min_length and len(content) < self.min_length:
            logger.warning(f"Response too short: {len(content)} < {self.min_length}")
            # Add warning to response
            response.content = f"[WARNING: Response may be incomplete]\n\n{content}"

        if self.max_length and len(content) > self.max_length:
            logger.warning(f"Response too long: {len(content)} > {self.max_length}")
            # Truncate
            response.content = content[:self.max_length] + "\n\n[Response truncated due to length]"

        # Prohibited content check
        for pattern in self.prohibited_patterns:
            if pattern.lower() in content.lower():
                logger.error(f"Prohibited pattern detected: {pattern}")
                response.content = f"[ERROR: Response contained prohibited content and was blocked]\n\nPattern: {pattern}"

        # Required patterns check
        for pattern in self.required_patterns:
            if pattern.lower() not in content.lower():
                logger.warning(f"Required pattern missing: {pattern}")
                response.content = f"[WARNING: Response may be missing required information]\n\n{content}"

        return response


class LoggingHook(ModelHook):
    """
    Logs model inputs/outputs for monitoring and debugging.

    Tracks:
    - Token usage
    - Latency
    - Model selection
    - Request/response patterns

    Example:
        >>> hook = LoggingHook(log_inputs=True, log_outputs=True)
    """

    def __init__(
        self,
        log_inputs: bool = True,
        log_outputs: bool = True,
        log_tokens: bool = True,
        max_log_length: int = 500
    ):
        self.log_inputs = log_inputs
        self.log_outputs = log_outputs
        self.log_tokens = log_tokens
        self.max_log_length = max_log_length
        self._start_time = None

    def pre_model(self, messages: List[BaseMessage], config: Dict[str, Any]) -> List[BaseMessage]:
        """Log input messages."""
        self._start_time = time.time()

        if self.log_inputs:
            total_chars = sum(len(m.content) for m in messages)
            logger.info(f"📥 Model Input: {len(messages)} messages, ~{total_chars} chars")

            # Log last message (usually the user query)
            if messages:
                last_msg = messages[-1]
                content_preview = last_msg.content[:self.max_log_length]
                if len(last_msg.content) > self.max_log_length:
                    content_preview += "..."
                logger.debug(f"Last message: {content_preview}")

        return messages

    def post_model(self, response: AIMessage, config: Dict[str, Any]) -> AIMessage:
        """Log output response."""

        if self.log_outputs:
            # Calculate latency
            latency = time.time() - self._start_time if self._start_time else 0

            logger.info(f"📤 Model Output: {len(response.content)} chars, {latency:.2f}s")

            # Log response preview
            content_preview = response.content[:self.max_log_length]
            if len(response.content) > self.max_log_length:
                content_preview += "..."
            logger.debug(f"Response: {content_preview}")

        if self.log_tokens and hasattr(response, 'response_metadata'):
            metadata = response.response_metadata
            if 'token_usage' in metadata:
                usage = metadata['token_usage']
                logger.info(f"💰 Token Usage: {usage}")

        return response


class CostTrackingHook(ModelHook):
    """
    Tracks estimated costs for model usage.

    Accumulates cost estimates based on token usage and model pricing.
    Useful for monitoring and budgeting.

    Example:
        >>> hook = CostTrackingHook()
        >>> # After execution
        >>> print(f"Total cost: ${hook.total_cost:.4f}")
    """

    def __init__(self):
        self.total_cost = 0.0
        self.call_count = 0

        # Cost per 1K tokens (approximate)
        self.costs = {
            "gpt-4o-mini": 0.00015,
            "gpt-4o": 0.0025,
            "gpt-5": 0.010,
            "claude-sonnet-4-5-20250929": 0.003,
            "claude-3.5-sonnet": 0.003,
            "gemini-2.5-pro": 0.0035,
            "o1-preview": 0.015
        }

    def pre_model(self, messages: List[BaseMessage], config: Dict[str, Any]) -> List[BaseMessage]:
        """Track input tokens."""
        self.call_count += 1
        return messages

    def post_model(self, response: AIMessage, config: Dict[str, Any]) -> AIMessage:
        """Calculate and track cost."""

        if hasattr(response, 'response_metadata'):
            metadata = response.response_metadata

            if 'token_usage' in metadata:
                usage = metadata['token_usage']
                total_tokens = usage.get('total_tokens', 0)

                # Get model name from config
                model_name = config.get('model', 'gpt-4o')
                cost_per_1k = self.costs.get(model_name, 0.0025)  # Default to gpt-4o

                # Calculate cost
                call_cost = (total_tokens / 1000) * cost_per_1k
                self.total_cost += call_cost

                logger.info(f"💵 Cost this call: ${call_cost:.6f} (Total: ${self.total_cost:.6f})")

        return response

    def get_stats(self) -> Dict[str, Any]:
        """Get cost statistics."""
        return {
            "total_cost": self.total_cost,
            "call_count": self.call_count,
            "avg_cost_per_call": self.total_cost / self.call_count if self.call_count > 0 else 0
        }


# =============================================================================
# Hook Manager
# =============================================================================

class HookManager:
    """
    Manages and applies multiple hooks to model calls.

    Chains hooks together and ensures proper execution order.
    """

    def __init__(self, hooks: List[ModelHook]):
        self.hooks = hooks
        logger.info(f"Initialized HookManager with {len(hooks)} hooks")

    def apply_pre_hooks(self, messages: List[BaseMessage], config: Dict[str, Any]) -> List[BaseMessage]:
        """Apply all pre-model hooks in order."""
        modified = messages

        for hook in self.hooks:
            try:
                modified = hook.pre_model(modified, config)
            except Exception as e:
                logger.error(f"Error in pre-hook {hook.__class__.__name__}: {e}")
                # Continue with other hooks

        return modified

    def apply_post_hooks(self, response: AIMessage, config: Dict[str, Any]) -> AIMessage:
        """Apply all post-model hooks in order."""
        modified = response

        for hook in self.hooks:
            try:
                modified = hook.post_model(modified, config)
            except Exception as e:
                logger.error(f"Error in post-hook {hook.__class__.__name__}: {e}")
                # Continue with other hooks

        return modified


# =============================================================================
# Helper Functions
# =============================================================================

def create_hook_from_config(hook_config: Dict[str, Any]) -> ModelHook:
    """
    Create a hook instance from configuration.

    Args:
        hook_config: Dictionary with 'type' and optional parameters

    Returns:
        Hook instance

    Example:
        >>> config = {"type": "timestamp", "timezone": "PST"}
        >>> hook = create_hook_from_config(config)
    """

    hook_type = hook_config.get("type", "").lower()

    if hook_type == "timestamp":
        return TimestampHook(
            timezone=hook_config.get("timezone", "UTC"),
            format=hook_config.get("format", "%Y-%m-%d %H:%M:%S")
        )

    elif hook_type == "project_context":
        return ProjectContextHook()

    elif hook_type == "validation":
        return ValidationHook(
            min_length=hook_config.get("min_length"),
            max_length=hook_config.get("max_length"),
            prohibited_patterns=hook_config.get("prohibited_patterns"),
            required_patterns=hook_config.get("required_patterns")
        )

    elif hook_type == "logging":
        return LoggingHook(
            log_inputs=hook_config.get("log_inputs", True),
            log_outputs=hook_config.get("log_outputs", True),
            log_tokens=hook_config.get("log_tokens", True),
            max_log_length=hook_config.get("max_log_length", 500)
        )

    elif hook_type == "cost_tracking":
        return CostTrackingHook()

    else:
        raise ValueError(f"Unknown hook type: {hook_type}")


def get_default_hooks() -> List[ModelHook]:
    """
    Get recommended default hooks for most agents.

    Returns:
        List of default hook instances
    """
    return [
        TimestampHook(),
        ProjectContextHook(),
        LoggingHook(log_inputs=True, log_outputs=True),
    ]
