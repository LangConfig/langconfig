# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangGraph v1.0 Middleware System for LangConfig

Implements the modern middleware pattern that replaces hooks in v1.0.
Middleware provides more powerful and composable patterns for:
- Dynamic prompts with @dynamic_prompt decorator
- Pre/post model hooks via before_model() and after_model()
- Tool error handling with wrap_tool_call()
- Custom state management via state_schema
- Message summarization and HITL gates

Migration from Hooks:
- pre_model() → before_model()
- post_model() → after_model()
- More composable and reusable
- Can define custom state extensions

Example:
    >>> from core.middleware.core import TimestampMiddleware, SummarizationMiddleware
    >>>
    >>> agent = create_agent(
    ...     model="anthropic:claude-sonnet-4-5",
    ...     tools=tools,
    ...     middleware=[
    ...         TimestampMiddleware(),
    ...         SummarizationMiddleware(model="anthropic:claude-sonnet-4-5", max_tokens_before_summary=1000)
    ...     ]
    ... )
"""

import logging
import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import wraps

# v1.0 imports
from langchain.agents import AgentState
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain.chat_models import init_chat_model
from typing_extensions import NotRequired

logger = logging.getLogger(__name__)


# =============================================================================
# Base Middleware Classes (v1.0 Pattern)
# =============================================================================

class AgentMiddleware(ABC):
    """
    Base class for LangGraph v1.0 middleware.

    Middleware provides powerful hooks into the agent execution lifecycle:
    - before_agent(): Called before agent starts (load memory, validate input)
    - before_model(): Modify state before each model call
    - wrap_model_call(): Wrap entire model invocation
    - wrap_tool_call(): Handle tool errors and retries
    - after_model(): Modify state after each model call
    - after_agent(): Called after agent completes (save results, cleanup)

    Middleware can also define custom state extensions via state_schema.
    """

    # Default state schema - matches LangChain's official implementation
    # Subclasses can override this to extend state with custom fields
    state_schema: type = AgentState

    # Additional tools registered by this middleware (empty by default)
    tools: List[BaseTool] = []

    def __init__(self):
        """Initialize middleware with a unique name."""
        # Set name to class name by default (can be overridden)
        if not hasattr(self, 'name'):
            self.name = self.__class__.__name__

    def before_agent(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """
        Called BEFORE the agent starts execution.

        Use cases:
        - Load conversation memory
        - Validate initial input
        - Initialize tracking/metrics
        - Setup resources

        Args:
            state: Initial agent state
            runtime: Runtime context (model, tools, config)

        Returns:
            State updates (dict) or None for no changes
        """
        return None

    async def abefore_agent(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Async version of before_agent. By default, calls the sync version."""
        return self.before_agent(state, runtime)

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """
        Called BEFORE the model is invoked.

        Use cases:
        - Add context to messages
        - Modify prompts dynamically
        - Check preconditions
        - Summarize long conversations

        Args:
            state: Current agent state
            runtime: Runtime context (model, tools, config)

        Returns:
            State updates (dict) or None for no changes
        """
        return None

    async def abefore_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Async version of before_model. By default, calls the sync version."""
        return self.before_model(state, runtime)

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """
        Called AFTER the model responds.

        Use cases:
        - Validate outputs
        - Transform responses
        - Track metrics
        - Implement HITL gates

        Args:
            state: Current agent state (with model response)
            runtime: Runtime context

        Returns:
            State updates (dict) or None for no changes
        """
        return None

    async def aafter_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Async version of after_model. By default, calls the sync version."""
        return self.after_model(state, runtime)

    def wrap_model_call(self, request: Any, handler: Callable) -> Any:
        """
        Wrap the entire model call with custom logic.

        Use cases:
        - Dynamic model selection
        - Retry logic
        - Fallbacks
        - Cost optimization

        Args:
            request: Model request object
            handler: Function to invoke model (call this to proceed)

        Returns:
            Model response (after calling handler)

        Example:
            >>> def wrap_model_call(self, request, handler):
            ...     # Add custom logic
            ...     if complex_task(request):
            ...         request = request.replace(model="gpt-5")
            ...     return handler(request)
        """
        # Default: just call the handler
        return handler(request)

    async def awrap_model_call(self, request: Any, handler: Callable) -> Any:
        """
        Async version of wrap_model_call for LangChain 1.0 compatibility.

        The handler is an async function that must be awaited.
        By default, just awaits the handler directly.
        """
        # Default: just await the async handler
        return await handler(request)

    def wrap_tool_call(self, request: Any, handler: Callable) -> Any:
        """
        Wrap individual tool calls for error handling.

        Use cases:
        - Retry failed tool calls
        - Validate tool inputs
        - Log tool usage
        - Handle exceptions gracefully

        Args:
            request: Tool call request containing tool_name, tool_input, etc.
            handler: Function to invoke tool

        Returns:
            Tool result (or error message)
        """
        # Default: just call the handler
        return handler(request)

    async def awrap_tool_call(self, request: Any, handler: Callable) -> Any:
        """
        Async version of wrap_tool_call for LangChain 1.0 compatibility.

        Properly awaits the async handler.
        """
        # Default: just await the async handler
        return await handler(request)

    def after_agent(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """
        Called AFTER the agent completes execution.

        Use cases:
        - Save conversation to memory/database
        - Generate final reports
        - Cleanup resources
        - Log final metrics

        Args:
            state: Final agent state
            runtime: Runtime context

        Returns:
            State updates (dict) or None for no changes
        """
        return None

    async def aafter_agent(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Async version of after_agent. By default, calls the sync version."""
        return self.after_agent(state, runtime)


# =============================================================================
# Dynamic Prompt Decorator (v1.0 Feature)
# =============================================================================

def dynamic_prompt(func: Callable) -> Callable:
    """
    Decorator for creating dynamic prompts that adapt to runtime context.

    Dynamic prompts can access:
    - request.state: Current agent state
    - request.runtime.context: Runtime context (user_id, session, etc.)
    - request.messages: Conversation history

    Example:
        >>> @dynamic_prompt
        ... def adaptive_prompt(request) -> str:
        ...     user_role = request.runtime.context.user_role
        ...     base = "You are a helpful assistant."
        ...
        ...     if user_role == "expert":
        ...         return f"{base} Provide detailed technical responses."
        ...     elif user_role == "beginner":
        ...         return f"{base} Explain concepts simply."
        ...     else:
        ...         return base
        ...
        ... agent = create_agent(
        ...     model="openai:gpt-4o",
        ...     tools=tools,
        ...     middleware=[adaptive_prompt]
        ... )
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    # Mark as dynamic prompt
    wrapper._is_dynamic_prompt = True
    return wrapper


# =============================================================================
# Built-in Middleware (Ported from Hooks + New v1.0 Features)
# =============================================================================

class TimestampMiddleware(AgentMiddleware):
    """
    Adds current timestamp to model context.

    Injects timestamp so the model knows current date/time for time-sensitive queries.

    Example:
        >>> middleware = [TimestampMiddleware(timezone="PST")]
    """

    def __init__(self, timezone: str = "UTC", format: str = "%Y-%m-%d %H:%M:%S"):
        super().__init__()
        self.timezone = timezone
        self.format = format

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Add timestamp to messages."""
        messages = state.get("messages", [])

        timestamp = datetime.utcnow().strftime(self.format)
        # Changed to HumanMessage to avoid "multiple system messages" error with Claude API
        timestamp_msg = HumanMessage(
            content=f"Current time: {timestamp} {self.timezone}"
        )

        # Insert after system messages
        insert_idx = 0
        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage):
                insert_idx = i + 1
            else:
                break

        updated_messages = messages.copy()
        updated_messages.insert(insert_idx, timestamp_msg)

        logger.debug(f"Added timestamp: {timestamp} {self.timezone}")

        return {"messages": updated_messages}


class ProjectContextMiddleware(AgentMiddleware):
    """
    Injects project and task metadata into model context.

    Example:
        >>> middleware = [ProjectContextMiddleware()]
    """

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Add project/task context."""

        # Try to get context from runtime
        context = getattr(runtime, 'context', {})
        project_id = getattr(context, 'project_id', None)
        task_id = getattr(context, 'task_id', None)
        user_id = getattr(context, 'user_id', None)

        if not (project_id or task_id):
            return None

        # Build context message
        context_parts = []
        if project_id:
            context_parts.append(f"Project ID: {project_id}")
        if task_id:
            context_parts.append(f"Task ID: {task_id}")
        if user_id:
            context_parts.append(f"User: {user_id}")

        messages = state.get("messages", [])
        # Changed to HumanMessage to avoid "multiple system messages" error with Claude API
        context_msg = HumanMessage(
            content=f"Context: {', '.join(context_parts)}"
        )

        # Insert after system messages
        insert_idx = 0
        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage):
                insert_idx = i + 1
            else:
                break

        updated_messages = messages.copy()
        updated_messages.insert(insert_idx, context_msg)

        logger.debug(f"Added project context: {', '.join(context_parts)}")

        return {"messages": updated_messages}


class ValidationMiddleware(AgentMiddleware):
    """
    Validates model outputs for quality and safety.

    Checks responses for:
    - Minimum/maximum length
    - Prohibited content
    - Required patterns

    Example:
        >>> middleware = [
        ...     ValidationMiddleware(
        ...         min_length=10,
        ...         prohibited_patterns=["DELETE FROM", "DROP TABLE"]
        ...     )
        ... ]
    """

    def __init__(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        prohibited_patterns: Optional[List[str]] = None,
        required_patterns: Optional[List[str]] = None
    ):
        super().__init__()
        self.min_length = min_length
        self.max_length = max_length
        self.prohibited_patterns = prohibited_patterns or []
        self.required_patterns = required_patterns or []

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Validate response."""
        messages = state.get("messages", [])

        if not messages:
            return None

        last_message = messages[-1]

        if not isinstance(last_message, AIMessage):
            return None

        content = last_message.content
        modified_content = content

        # Length validation
        if self.min_length and len(content) < self.min_length:
            logger.warning(f"Response too short: {len(content)} < {self.min_length}")
            modified_content = f"[WARNING: Response may be incomplete]\n\n{content}"

        if self.max_length and len(content) > self.max_length:
            logger.warning(f"Response too long: {len(content)} > {self.max_length}")
            modified_content = content[:self.max_length] + "\n\n[Response truncated]"

        # Prohibited content check
        for pattern in self.prohibited_patterns:
            if pattern.lower() in content.lower():
                logger.error(f"Prohibited pattern detected: {pattern}")
                modified_content = f"[ERROR: Response contained prohibited content]\n\nPattern: {pattern}"

        # Required patterns check
        for pattern in self.required_patterns:
            if pattern.lower() not in content.lower():
                logger.warning(f"Required pattern missing: {pattern}")
                modified_content = f"[WARNING: Response may be missing required information]\n\n{content}"

        if modified_content != content:
            # Update message
            updated_messages = messages.copy()
            updated_messages[-1] = AIMessage(content=modified_content)
            return {"messages": updated_messages}

        return None


class LoggingMiddleware(AgentMiddleware):
    """
    Logs model inputs/outputs for monitoring.

    Tracks:
    - Request/response patterns
    - Latency
    - Token usage

    Example:
        >>> middleware = [LoggingMiddleware(log_inputs=True, log_outputs=True)]
    """

    def __init__(
        self,
        log_inputs: bool = True,
        log_outputs: bool = True,
        max_log_length: int = 500
    ):
        super().__init__()
        self.log_inputs = log_inputs
        self.log_outputs = log_outputs
        self.max_log_length = max_log_length
        self._start_time = None

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Log input."""
        self._start_time = time.time()

        if self.log_inputs:
            messages = state.get("messages", [])
            total_chars = sum(len(m.content) for m in messages if hasattr(m, 'content'))
            logger.info(f"📥 Model Input: {len(messages)} messages, ~{total_chars} chars")

            if messages:
                last_msg = messages[-1]
                content = getattr(last_msg, 'content', '')
                preview = content[:self.max_log_length]
                if len(content) > self.max_log_length:
                    preview += "..."
                logger.debug(f"Last message: {preview}")

        return None

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Log output."""

        if self.log_outputs:
            latency = time.time() - self._start_time if self._start_time else 0

            messages = state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                content = getattr(last_msg, 'content', '')
                logger.info(f"📤 Model Output: {len(content)} chars, {latency:.2f}s")

                preview = content[:self.max_log_length]
                if len(content) > self.max_log_length:
                    preview += "..."
                logger.debug(f"Response: {preview}")

        return None


class CostTrackingMiddleware(AgentMiddleware):
    """
    Comprehensive cost tracking for model usage, tools, and per-agent breakdowns.

    Tracks:
    - Total costs and token usage
    - Per-agent costs and token breakdowns
    - Tool usage costs (if tools have costs)
    - Prompt vs completion token ratios
    - Cost trends over time

    Example:
        >>> cost_tracker = CostTrackingMiddleware()
        >>> middleware = [cost_tracker]
        >>> # After execution:
        >>> stats = cost_tracker.get_stats()
        >>> print(f"Total cost: ${stats['total_cost']:.4f}")
        >>> print(f"By agent: {stats['cost_by_agent']}")
    """

    def __init__(self):
        super().__init__()
        self.total_cost = 0.0
        self.call_count = 0

        # Detailed tracking
        self.cost_by_agent = {}  # {agent_id: cost}
        self.tokens_by_agent = {}  # {agent_id: {'prompt': x, 'completion': y, 'total': z}}
        self.tool_calls = []  # [{tool: str, agent: str, timestamp: float}]
        self.cost_history = []  # [{timestamp, agent, cost, tokens}]

        # Cost per 1K tokens (updated 10/19/2025)
        self.costs = {
            "gpt-4o-mini": 0.00015,
            "gpt-4o": 0.0025,
            "gpt-5": 0.010,
            "claude-sonnet-4-5-20250929": 0.003,
            "claude-3.5-sonnet": 0.003,
            "gemini-2.5-pro": 0.0035,
            "o1-preview": 0.015
        }

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Track call and tool usage."""
        import time

        self.call_count += 1

        # Track tool calls if present in messages
        messages = state.get("messages", [])
        current_agent = state.get("current_step", "unknown")

        for msg in messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    self.tool_calls.append({
                        "tool": tool_call.get('name', 'unknown'),
                        "agent": current_agent,
                        "timestamp": time.time()
                    })

        return None

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Calculate comprehensive cost and token breakdown."""
        import time

        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        current_agent = state.get("current_step", "unknown")

        if hasattr(last_msg, 'response_metadata'):
            metadata = last_msg.response_metadata

            if 'token_usage' in metadata:
                usage = metadata['token_usage']
                total_tokens = usage.get('total_tokens', 0)
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)

                # Get model from runtime
                model_name = getattr(runtime, 'model', 'gpt-4o')
                if hasattr(model_name, 'model_name'):
                    model_name = model_name.model_name

                cost_per_1k = self.costs.get(model_name, 0.0025)
                call_cost = (total_tokens / 1000) * cost_per_1k
                self.total_cost += call_cost

                # Track per-agent costs
                if current_agent not in self.cost_by_agent:
                    self.cost_by_agent[current_agent] = 0.0
                self.cost_by_agent[current_agent] += call_cost

                # Track per-agent tokens
                if current_agent not in self.tokens_by_agent:
                    self.tokens_by_agent[current_agent] = {
                        'prompt': 0,
                        'completion': 0,
                        'total': 0
                    }
                self.tokens_by_agent[current_agent]['prompt'] += prompt_tokens
                self.tokens_by_agent[current_agent]['completion'] += completion_tokens
                self.tokens_by_agent[current_agent]['total'] += total_tokens

                # Track cost history
                self.cost_history.append({
                    'timestamp': time.time(),
                    'agent': current_agent,
                    'cost': call_cost,
                    'tokens': total_tokens,
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'model': model_name
                })

                logger.info(
                    f"💵 [{current_agent}] Cost: ${call_cost:.6f} "
                    f"(Tokens: {total_tokens} = {prompt_tokens}p + {completion_tokens}c) "
                    f"| Total: ${self.total_cost:.6f}"
                )

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cost statistics with breakdowns."""
        # Calculate most expensive agent
        most_expensive_agent = None
        if self.cost_by_agent:
            most_expensive_agent = max(self.cost_by_agent.items(), key=lambda x: x[1])

        # Calculate total tokens
        total_prompt_tokens = sum(t['prompt'] for t in self.tokens_by_agent.values())
        total_completion_tokens = sum(t['completion'] for t in self.tokens_by_agent.values())
        total_tokens = sum(t['total'] for t in self.tokens_by_agent.values())

        # Group tool calls by tool name
        tool_counts = {}
        for tc in self.tool_calls:
            tool_name = tc['tool']
            if tool_name not in tool_counts:
                tool_counts[tool_name] = 0
            tool_counts[tool_name] += 1

        return {
            # Overall metrics
            "total_cost": self.total_cost,
            "call_count": self.call_count,
            "avg_cost_per_call": self.total_cost / self.call_count if self.call_count > 0 else 0,

            # Token metrics
            "total_tokens": total_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "avg_tokens_per_call": total_tokens / self.call_count if self.call_count > 0 else 0,

            # Per-agent breakdowns
            "cost_by_agent": self.cost_by_agent,
            "tokens_by_agent": self.tokens_by_agent,
            "most_expensive_agent": {
                "name": most_expensive_agent[0],
                "cost": most_expensive_agent[1]
            } if most_expensive_agent else None,

            # Tool usage
            "tool_calls_count": len(self.tool_calls),
            "tool_calls_by_name": tool_counts,
            "tool_calls_details": self.tool_calls,

            # Cost history for trends
            "cost_history": self.cost_history
        }


# =============================================================================
# Advanced v1.0 Middleware
# =============================================================================

class SummarizationMiddleware(AgentMiddleware):
    """
    Automatically summarizes long conversations to stay within context limits.

    Built-in v1.0 middleware that prevents context overflow by:
    - Monitoring message history length
    - Summarizing old messages when threshold reached
    - Preserving recent messages for continuity

    Example:
        >>> middleware = [
        ...     SummarizationMiddleware(
        ...         model="anthropic:claude-sonnet-4-5",
        ...         max_tokens_before_summary=1000
        ...     )
        ... ]
    """

    def __init__(
        self,
        model: str,
        max_tokens_before_summary: int = 1000,
        keep_last_n_messages: int = 5
    ):
        super().__init__()
        self.model = model
        self.max_tokens_before_summary = max_tokens_before_summary
        self.keep_last_n_messages = keep_last_n_messages
        self._summarizer = None

    def _get_summarizer(self):
        """Lazy init summarizer model."""
        if self._summarizer is None:
            self._summarizer = init_chat_model(self.model)
        return self._summarizer

    def _estimate_tokens(self, messages: List[BaseMessage]) -> int:
        """Rough token estimate (4 chars = 1 token)."""
        total_chars = sum(len(m.content) for m in messages if hasattr(m, 'content'))
        return total_chars // 4

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Summarize if conversation is too long."""

        messages = state.get("messages", [])

        if len(messages) <= self.keep_last_n_messages:
            return None

        estimated_tokens = self._estimate_tokens(messages)

        if estimated_tokens < self.max_tokens_before_summary:
            return None

        logger.info(f"🔄 Summarizing conversation (~{estimated_tokens} tokens)")

        # Split: messages to summarize vs keep
        to_summarize = messages[:-self.keep_last_n_messages]
        to_keep = messages[-self.keep_last_n_messages:]

        # Create summary
        summary_prompt = (
            "Summarize the following conversation history concisely, "
            "preserving key information and context:\n\n"
        )
        for msg in to_summarize:
            summary_prompt += f"{msg.__class__.__name__}: {msg.content}\n\n"

        summarizer = self._get_summarizer()
        summary_response = summarizer.invoke([HumanMessage(content=summary_prompt)])

        # Create new message list with summary
        summary_msg = SystemMessage(
            content=f"[Summary of previous conversation]\n{summary_response.content}"
        )

        updated_messages = [summary_msg] + to_keep

        logger.info(f"✓ Summarized {len(to_summarize)} messages → 1 summary")

        return {"messages": updated_messages}


class HumanInTheLoopMiddleware(AgentMiddleware):
    """
    Implements human approval gates for sensitive tool calls.

    Built-in v1.0 middleware that pauses execution for human review before:
    - Executing dangerous operations
    - Making irreversible changes
    - Spending money or resources

    Example:
        >>> middleware = [
        ...     HumanInTheLoopMiddleware(
        ...         interrupt_on={
        ...             "send_email": True,
        ...             "delete_file": True,
        ...             "deploy_code": True
        ...         },
        ...         description="Please review before executing"
        ...     )
        ... ]

    Note: Requires checkpointing to be enabled for interrupts to work.
    """

    def __init__(
        self,
        interrupt_on: Dict[str, bool],
        description: str = "Human approval required"
    ):
        super().__init__()
        self.interrupt_on = interrupt_on
        self.description = description

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Check if tool calls require approval."""

        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]

        # Check if last message has tool calls
        if not isinstance(last_msg, AIMessage) or not hasattr(last_msg, 'tool_calls'):
            return None

        tool_calls = last_msg.tool_calls or []

        # Check if any tool requires approval
        requires_approval = False
        for tool_call in tool_calls:
            tool_name = tool_call.get('name', '')
            if self.interrupt_on.get(tool_name, False):
                requires_approval = True
                logger.warning(f"🚨 Tool '{tool_name}' requires human approval")

        if requires_approval:
            # Set interrupt flag (will be handled by LangGraph)
            return {
                "interrupt_requested": True,
                "interrupt_reason": self.description,
                "pending_tool_calls": tool_calls
            }

        return None


# =============================================================================
# Tool Retry Middleware
# =============================================================================

class ToolRetryMiddleware(AgentMiddleware):
    """
    Automatically retries failed tool calls with exponential backoff.

    Example:
        >>> middleware = [
        ...     ToolRetryMiddleware(max_retries=3, backoff_factor=2.0)
        ... ]
    """

    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        super().__init__()
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def wrap_tool_call(self, tool_name: str, tool_input: Dict, handler: Callable) -> Any:
        """Retry tool calls on failure."""

        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = handler(tool_name, tool_input)

                if attempt > 0:
                    logger.info(f"✓ Tool '{tool_name}' succeeded on attempt {attempt + 1}")

                return result

            except Exception as e:
                last_error = e

                if attempt < self.max_retries - 1:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"Tool '{tool_name}' failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Tool '{tool_name}' failed after {self.max_retries} attempts: {e}"
                    )

        # All retries exhausted
        return f"Error: Tool '{tool_name}' failed after {self.max_retries} attempts. Last error: {last_error}"


# =============================================================================
# PII Middleware (v1.0 Built-in)
# =============================================================================

class PIIMiddleware(AgentMiddleware):
    """
    Redacts sensitive personally identifiable information (PII) before sending to models.

    Built-in v1.0 middleware that protects sensitive data by:
    - Detecting and redacting PII patterns (email, phone, SSN, credit cards, etc.)
    - Maintaining redaction mappings for potential restoration
    - Providing configurable pattern matching

    Example:
        >>> middleware = [
        ...     PIIMiddleware(
        ...         patterns=["email", "phone", "ssn", "credit_card"],
        ...         replacement="[REDACTED]"
        ...     )
        ... ]

    Supported pattern types:
    - email: Email addresses
    - phone: Phone numbers (various formats)
    - ssn: Social Security Numbers
    - credit_card: Credit card numbers
    - api_key: API keys and tokens
    - ip_address: IPv4/IPv6 addresses
    - url: URLs with sensitive tokens
    """

    # Pre-defined PII patterns
    PII_PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b',
        "ssn": r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b',
        "credit_card": r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b',
        "api_key": r'\b(?:api[_-]?key|apikey|access[_-]?token|secret[_-]?key)["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})["\']?\b',
        "ip_address": r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b|\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b',
        "url_token": r'(https?://[^\s]+[?&](token|key|secret|password)=)[^\s&]+',
        "password": r'\b(?:password|passwd|pwd)["\']?\s*[:=]\s*["\']?([^\s"\']+)["\']?\b',
    }

    def __init__(
        self,
        patterns: Optional[List[str]] = None,
        custom_patterns: Optional[Dict[str, str]] = None,
        replacement: str = "[REDACTED]",
        store_mappings: bool = False
    ):
        """
        Initialize PII middleware.

        Args:
            patterns: List of pattern names to use (e.g., ["email", "phone"])
                     If None, uses all built-in patterns
            custom_patterns: Additional custom regex patterns {name: pattern}
            replacement: Text to replace PII with
            store_mappings: Whether to store redaction mappings for restoration
        """
        super().__init__()
        import re

        self.replacement = replacement
        self.store_mappings = store_mappings
        self._redaction_map: Dict[str, str] = {}

        # Build active patterns
        self.active_patterns = {}

        if patterns is None:
            # Use all built-in patterns
            self.active_patterns = self.PII_PATTERNS.copy()
        else:
            # Use specified patterns
            for pattern_name in patterns:
                if pattern_name in self.PII_PATTERNS:
                    self.active_patterns[pattern_name] = self.PII_PATTERNS[pattern_name]
                else:
                    logger.warning(f"Unknown PII pattern: {pattern_name}")

        # Add custom patterns
        if custom_patterns:
            self.active_patterns.update(custom_patterns)

        # Compile patterns
        self.compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.active_patterns.items()
        }

        logger.info(f"PIIMiddleware initialized with patterns: {list(self.active_patterns.keys())}")

    def _redact_text(self, text: str) -> str:
        """Redact PII from text."""
        if not text:
            return text

        redacted_text = text

        for pattern_name, compiled_pattern in self.compiled_patterns.items():
            matches = compiled_pattern.findall(redacted_text)

            if matches:
                logger.debug(f"Found {len(matches)} instances of {pattern_name} PII")

                for match in matches:
                    # Handle tuple matches (from groups)
                    match_str = match if isinstance(match, str) else ''.join(match)

                    if self.store_mappings:
                        # Store original for potential restoration
                        self._redaction_map[f"{self.replacement}_{len(self._redaction_map)}"] = match_str
                        replacement = f"{self.replacement}_{len(self._redaction_map) - 1}"
                    else:
                        replacement = self.replacement

                    redacted_text = redacted_text.replace(match_str, replacement)

        return redacted_text

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Redact PII from messages before sending to model."""
        messages = state.get("messages", [])

        if not messages:
            return None

        updated_messages = []
        redacted_count = 0

        for msg in messages:
            if hasattr(msg, 'content') and isinstance(msg.content, str):
                original_content = msg.content
                redacted_content = self._redact_text(original_content)

                if redacted_content != original_content:
                    redacted_count += 1
                    # Create new message with redacted content
                    msg_class = msg.__class__
                    updated_msg = msg_class(content=redacted_content)
                    # Copy other attributes
                    if hasattr(msg, 'additional_kwargs'):
                        updated_msg.additional_kwargs = msg.additional_kwargs
                    updated_messages.append(updated_msg)
                else:
                    updated_messages.append(msg)
            else:
                updated_messages.append(msg)

        if redacted_count > 0:
            logger.info(f"🔒 Redacted PII from {redacted_count} message(s)")
            return {"messages": updated_messages}

        return None

    def get_redaction_map(self) -> Dict[str, str]:
        """Get the mapping of redacted values to originals."""
        return self._redaction_map.copy()

    def restore_text(self, redacted_text: str) -> str:
        """Restore original text from redacted version (if mappings stored)."""
        if not self.store_mappings:
            logger.warning("Cannot restore: store_mappings was not enabled")
            return redacted_text

        restored_text = redacted_text
        for redacted, original in self._redaction_map.items():
            restored_text = restored_text.replace(redacted, original)

        return restored_text


# =============================================================================
# Helper Functions
# =============================================================================

def get_default_middleware() -> List[AgentMiddleware]:
    """
    Get recommended default middleware for most agents.

    ✅ LangGraph v1.0: Includes dynamic prompts and tool selection middleware.

    Returns:
        List of default middleware instances
    """
    from core.middleware.tool_selection import (
        PermissionBasedToolMiddleware,
        ContextBasedToolMiddleware
    )
    from core.middleware.question_detection import (
        QuestionDetectionMiddleware
    )

    return [
        # Core middleware
        TimestampMiddleware(),
        ProjectContextMiddleware(),
        LoggingMiddleware(log_inputs=True, log_outputs=True),

        # TODO: Re-enable dynamic prompts once decorator calling issue is resolved
        # The @dynamic_prompt decorator makes functions non-callable from within other decorated functions
        # comprehensive_dynamic_prompt,

        # ✅ HITL: Detect when agents ask questions and trigger human-in-the-loop
        QuestionDetectionMiddleware(),

        # ✅ v1.0: Dynamic tool selection (filter by role & credentials)
        PermissionBasedToolMiddleware(),
        ContextBasedToolMiddleware(),
    ]


def create_middleware_from_config(middleware_config: Dict[str, Any]) -> AgentMiddleware:
    """
    Create middleware instance from configuration.

    Args:
        middleware_config: Dictionary with 'type' and optional parameters

    Returns:
        Middleware instance

    Example:
        >>> config = {"type": "timestamp", "timezone": "PST"}
        >>> middleware = create_middleware_from_config(config)
    """

    middleware_type = middleware_config.get("type", "").lower()

    if middleware_type == "timestamp":
        return TimestampMiddleware(
            timezone=middleware_config.get("timezone", "UTC"),
            format=middleware_config.get("format", "%Y-%m-%d %H:%M:%S")
        )

    elif middleware_type == "project_context":
        return ProjectContextMiddleware()

    elif middleware_type == "validation":
        return ValidationMiddleware(
            min_length=middleware_config.get("min_length"),
            max_length=middleware_config.get("max_length"),
            prohibited_patterns=middleware_config.get("prohibited_patterns"),
            required_patterns=middleware_config.get("required_patterns")
        )

    elif middleware_type == "logging":
        return LoggingMiddleware(
            log_inputs=middleware_config.get("log_inputs", True),
            log_outputs=middleware_config.get("log_outputs", True),
            max_log_length=middleware_config.get("max_log_length", 500)
        )

    elif middleware_type == "cost_tracking":
        return CostTrackingMiddleware()

    elif middleware_type == "summarization":
        return SummarizationMiddleware(
            model=middleware_config.get("model", "gpt-4o-mini"),
            max_tokens_before_summary=middleware_config.get("max_tokens_before_summary", 1000),
            keep_last_n_messages=middleware_config.get("keep_last_n_messages", 5)
        )

    elif middleware_type == "hitl" or middleware_type == "human_in_the_loop":
        return HumanInTheLoopMiddleware(
            interrupt_on=middleware_config.get("interrupt_on", {}),
            description=middleware_config.get("description", "Human approval required")
        )

    elif middleware_type == "tool_retry":
        return ToolRetryMiddleware(
            max_retries=middleware_config.get("max_retries", 3),
            backoff_factor=middleware_config.get("backoff_factor", 2.0)
        )

    elif middleware_type == "pii":
        return PIIMiddleware(
            patterns=middleware_config.get("patterns"),
            custom_patterns=middleware_config.get("custom_patterns"),
            replacement=middleware_config.get("replacement", "[REDACTED]"),
            store_mappings=middleware_config.get("store_mappings", False)
        )

    # =========================================================================
    # LangChain 1.1 Built-in Middleware
    # =========================================================================

    elif middleware_type == "model_retry":
        # LangChain 1.1: ModelRetryMiddleware for retrying failed model calls
        try:
            from langchain.agents.middleware import ModelRetryMiddleware
            return ModelRetryMiddleware(
                max_retries=middleware_config.get("max_retries", 3),
                backoff_factor=middleware_config.get("backoff_factor", 2.0),
                initial_delay=middleware_config.get("initial_delay", 1.0),
                on_failure=middleware_config.get("on_failure", "continue"),
            )
        except ImportError:
            logger.warning("ModelRetryMiddleware not available, falling back to ToolRetryMiddleware")
            return ToolRetryMiddleware(
                max_retries=middleware_config.get("max_retries", 3),
                backoff_factor=middleware_config.get("backoff_factor", 2.0)
            )

    elif middleware_type == "model_fallback":
        # LangChain 1.1: ModelFallbackMiddleware for falling back to cheaper models
        try:
            from langchain.agents.middleware import ModelFallbackMiddleware
            fallback_models = middleware_config.get("models", [])
            if fallback_models:
                return ModelFallbackMiddleware(*fallback_models)
            else:
                raise ValueError("model_fallback requires 'models' list in config")
        except ImportError:
            logger.warning("ModelFallbackMiddleware not available in this LangChain version")
            raise ValueError("model_fallback middleware requires LangChain 1.1+")

    elif middleware_type == "content_moderation":
        # LangChain 1.1: ContentModerationMiddleware for OpenAI moderation
        try:
            from langchain.agents.middleware import ContentModerationMiddleware
            return ContentModerationMiddleware(
                block_input=middleware_config.get("block_input", True),
                block_output=middleware_config.get("block_output", False),
            )
        except ImportError:
            logger.warning("ContentModerationMiddleware not available in this LangChain version")
            raise ValueError("content_moderation middleware requires LangChain 1.1+")

    elif middleware_type == "context_summarization":
        # LangChain 1.1: SummarizationMiddleware with dynamic trigger
        try:
            from langchain.agents.middleware import SummarizationMiddleware as LC11SummarizationMiddleware
            return LC11SummarizationMiddleware(
                model=middleware_config.get("model", "gpt-4o-mini"),
                trigger=middleware_config.get("trigger", ("fraction", 0.8)),
                keep=middleware_config.get("keep", ("messages", 10)),
            )
        except ImportError:
            # Fall back to our local SummarizationMiddleware
            return SummarizationMiddleware(
                model=middleware_config.get("model", "gpt-4o-mini"),
                max_tokens_before_summary=middleware_config.get("max_tokens_before_summary", 1000),
                keep_last_n_messages=middleware_config.get("keep_last_n_messages", 5)
            )

    else:
        raise ValueError(f"Unknown middleware type: {middleware_type}")


# =============================================================================
# Backward Compatibility Bridge
# =============================================================================

def migrate_hook_to_middleware(hook_instance) -> AgentMiddleware:
    """
    Converts old hook instances to middleware (backward compatibility).

    Args:
        hook_instance: Old ModelHook instance

    Returns:
        Equivalent middleware instance

    Example:
        >>> from core.models.hooks import TimestampHook
        >>> old_hook = TimestampHook()
        >>> new_middleware = migrate_hook_to_middleware(old_hook)
    """

    hook_class_name = hook_instance.__class__.__name__

    if hook_class_name == "TimestampHook":
        return TimestampMiddleware(
            timezone=hook_instance.timezone,
            format=hook_instance.format
        )

    elif hook_class_name == "ProjectContextHook":
        return ProjectContextMiddleware()

    elif hook_class_name == "ValidationHook":
        return ValidationMiddleware(
            min_length=hook_instance.min_length,
            max_length=hook_instance.max_length,
            prohibited_patterns=hook_instance.prohibited_patterns,
            required_patterns=hook_instance.required_patterns
        )

    elif hook_class_name == "LoggingHook":
        return LoggingMiddleware(
            log_inputs=hook_instance.log_inputs,
            log_outputs=hook_instance.log_outputs,
            max_log_length=hook_instance.max_log_length
        )

    elif hook_class_name == "CostTrackingHook":
        return CostTrackingMiddleware()

    else:
        logger.warning(f"Unknown hook type for migration: {hook_class_name}")
        # Return a pass-through middleware
        return AgentMiddleware()
