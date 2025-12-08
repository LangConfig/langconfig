# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Context Window Management Service

LangChain 1.1 enhanced context window management for workflow agents.
Provides intelligent message trimming, filtering, summarization, and
tool loadout optimization to maximize effective context usage.

Strategies:
1. trim_messages - Token-based message trimming (LangChain built-in)
2. filter_messages - Filter by message type/role (LangChain built-in)
3. Summarization - Compress old context into summaries
4. Tool Loadout - Dynamic tool selection based on task
5. Context Quarantine - Isolate large/irrelevant context sections
"""

import logging
from typing import List, Dict, Any, Optional, Callable, Sequence, Literal, Union
from enum import Enum

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
    filter_messages,
)
from langchain_core.language_models import BaseChatModel
import tiktoken

logger = logging.getLogger(__name__)


class ContextStrategy(str, Enum):
    """Available context management strategies"""
    RECENT = "recent"  # Keep most recent messages (sliding window)
    SMART = "smart"    # Hybrid: recent + semantic + banked
    FULL = "full"      # All messages (warning: may exceed limits)
    SUMMARY = "summary"  # Summarize older context
    QUARANTINE = "quarantine"  # Isolate large context sections


class ContextWindowManager:
    """
    LangChain 1.1 Context Window Manager.

    Provides intelligent context management to prevent context limit errors
    and optimize LLM token usage.
    """

    # Default token limits by model (conservative estimates)
    MODEL_TOKEN_LIMITS = {
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        "claude-3-5-sonnet": 200000,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "gemini-1.5-pro": 1000000,
        "gemini-1.5-flash": 1000000,
        "gemini-2.0-flash": 1000000,
    }

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        model_name: str = "gpt-4o",
        strategy: ContextStrategy = ContextStrategy.SMART,
        preserve_system_message: bool = True,
        summarization_threshold: int = 50,  # Summarize after N messages
    ):
        """
        Initialize context window manager.

        Args:
            max_tokens: Maximum context tokens (default: auto-detect from model)
            model_name: Model name for token limit detection
            strategy: Context management strategy
            preserve_system_message: Always keep system message when trimming
            summarization_threshold: Number of messages before triggering summarization
        """
        self.model_name = model_name
        self.strategy = strategy
        self.preserve_system_message = preserve_system_message
        self.summarization_threshold = summarization_threshold

        # Auto-detect max tokens from model
        if max_tokens:
            self.max_tokens = max_tokens
        else:
            self.max_tokens = self._get_model_token_limit(model_name)

        # Reserve tokens for new response (conservative)
        self.output_reserve = min(4096, self.max_tokens // 4)
        self.available_context_tokens = self.max_tokens - self.output_reserve

        # Token encoder
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoder = None

        logger.info(
            f"ContextWindowManager initialized: model={model_name}, "
            f"max_tokens={self.max_tokens}, available={self.available_context_tokens}"
        )

    def _get_model_token_limit(self, model_name: str) -> int:
        """Get token limit for a model, with fallback"""
        model_lower = model_name.lower()

        for model_key, limit in self.MODEL_TOKEN_LIMITS.items():
            if model_key in model_lower:
                return limit

        # Conservative default
        logger.warning(f"Unknown model '{model_name}', using 32k token limit")
        return 32000

    def count_tokens(self, messages: List[BaseMessage]) -> int:
        """
        Count tokens in a message list.

        Uses tiktoken for accurate counting with fallback to character estimation.
        """
        if not messages:
            return 0

        total_tokens = 0

        for message in messages:
            content = message.content if hasattr(message, 'content') else str(message)

            if self.encoder:
                total_tokens += len(self.encoder.encode(str(content)))
            else:
                # Fallback: ~4 chars per token
                total_tokens += len(str(content)) // 4

            # Add overhead for message structure
            total_tokens += 4

        return total_tokens

    def count_tokens_str(self, text: str) -> int:
        """Count tokens in a string"""
        if not text:
            return 0
        if self.encoder:
            return len(self.encoder.encode(text))
        return len(text) // 4

    def trim_to_token_limit(
        self,
        messages: List[BaseMessage],
        max_tokens: Optional[int] = None,
        strategy: Literal["first", "last"] = "last",
        include_system: bool = True,
        start_on: Optional[Literal["human", "ai"]] = "human",
    ) -> List[BaseMessage]:
        """
        Trim messages to fit within token limit using LangChain's trim_messages.

        Args:
            messages: List of messages to trim
            max_tokens: Max tokens (default: self.available_context_tokens)
            strategy: "first" (keep oldest) or "last" (keep newest)
            include_system: Keep system message when trimming
            start_on: Require conversation to start with "human" or "ai"

        Returns:
            Trimmed message list within token budget
        """
        if not messages:
            return []

        max_tokens = max_tokens or self.available_context_tokens

        # Use LangChain's built-in trim_messages
        try:
            trimmed = trim_messages(
                messages,
                max_tokens=max_tokens,
                strategy=strategy,
                token_counter=self.count_tokens,
                include_system=include_system,
                start_on=start_on,
                allow_partial=False,
            )

            original_tokens = self.count_tokens(messages)
            trimmed_tokens = self.count_tokens(trimmed)

            if len(trimmed) < len(messages):
                logger.info(
                    f"Trimmed messages: {len(messages)} → {len(trimmed)}, "
                    f"tokens: {original_tokens} → {trimmed_tokens}"
                )

            return trimmed

        except Exception as e:
            logger.warning(f"LangChain trim_messages failed: {e}, using fallback")
            return self._fallback_trim(messages, max_tokens, strategy)

    def _fallback_trim(
        self,
        messages: List[BaseMessage],
        max_tokens: int,
        strategy: str = "last"
    ) -> List[BaseMessage]:
        """Fallback trimming when LangChain trim_messages fails"""
        if strategy == "last":
            # Keep most recent messages
            trimmed = []
            current_tokens = 0

            for msg in reversed(messages):
                msg_tokens = self.count_tokens([msg])
                if current_tokens + msg_tokens <= max_tokens:
                    trimmed.insert(0, msg)
                    current_tokens += msg_tokens
                else:
                    break

            return trimmed
        else:
            # Keep oldest messages
            trimmed = []
            current_tokens = 0

            for msg in messages:
                msg_tokens = self.count_tokens([msg])
                if current_tokens + msg_tokens <= max_tokens:
                    trimmed.append(msg)
                    current_tokens += msg_tokens
                else:
                    break

            return trimmed

    def filter_by_type(
        self,
        messages: List[BaseMessage],
        include_types: Optional[List[type]] = None,
        exclude_types: Optional[List[type]] = None,
        include_names: Optional[List[str]] = None,
        exclude_names: Optional[List[str]] = None,
    ) -> List[BaseMessage]:
        """
        Filter messages by type or name using LangChain's filter_messages.

        Args:
            messages: Messages to filter
            include_types: Message types to include (e.g., [HumanMessage, AIMessage])
            exclude_types: Message types to exclude (e.g., [ToolMessage])
            include_names: Message names to include
            exclude_names: Message names to exclude

        Returns:
            Filtered message list
        """
        if not messages:
            return []

        try:
            return filter_messages(
                messages,
                include_types=include_types,
                exclude_types=exclude_types,
                include_names=include_names,
                exclude_names=exclude_names,
            )
        except Exception as e:
            logger.warning(f"filter_messages failed: {e}, returning original")
            return messages

    def quarantine_large_content(
        self,
        messages: List[BaseMessage],
        max_message_tokens: int = 2000,
        placeholder_text: str = "[Content quarantined: {tokens} tokens]"
    ) -> List[BaseMessage]:
        """
        Quarantine (replace) messages that exceed a token threshold.

        Useful for isolating large tool outputs or code blocks that might
        consume too much context but aren't immediately relevant.

        Args:
            messages: Messages to process
            max_message_tokens: Max tokens per individual message
            placeholder_text: Text to replace large content with

        Returns:
            Messages with large content replaced by placeholders
        """
        quarantined = []

        for msg in messages:
            msg_tokens = self.count_tokens([msg])

            if msg_tokens > max_message_tokens:
                # Create placeholder message of same type
                placeholder = placeholder_text.format(tokens=msg_tokens)

                if isinstance(msg, HumanMessage):
                    quarantined.append(HumanMessage(content=placeholder))
                elif isinstance(msg, AIMessage):
                    quarantined.append(AIMessage(content=placeholder))
                elif isinstance(msg, ToolMessage):
                    quarantined.append(ToolMessage(
                        content=placeholder,
                        tool_call_id=getattr(msg, 'tool_call_id', 'unknown')
                    ))
                else:
                    quarantined.append(msg)  # Keep as-is

                logger.info(f"Quarantined large message: {msg_tokens} tokens")
            else:
                quarantined.append(msg)

        return quarantined

    async def summarize_context(
        self,
        messages: List[BaseMessage],
        summarization_llm: Optional[BaseChatModel] = None,
        keep_recent: int = 10,
    ) -> List[BaseMessage]:
        """
        Summarize older messages while keeping recent ones verbatim.

        Args:
            messages: Full message history
            summarization_llm: LLM to use for summarization (default: GPT-4o-mini)
            keep_recent: Number of recent messages to keep unchanged

        Returns:
            [SystemMessage(summary), ...recent_messages]
        """
        if len(messages) <= keep_recent:
            return messages

        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # Build text for summarization
        conversation_text = "\n".join([
            f"{msg.__class__.__name__}: {str(msg.content)[:500]}"
            for msg in old_messages[:50]  # Limit to 50 for summarization
        ])

        try:
            if summarization_llm is None:
                from langchain_openai import ChatOpenAI
                summarization_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

            summary_prompt = [
                SystemMessage(content="""You are a conversation summarizer.
Create a concise summary (under 500 words) of the key points:
- Important decisions made
- Key facts established
- Context needed for future reference
Focus on actionable information."""),
                HumanMessage(content=f"Summarize this conversation:\n\n{conversation_text}")
            ]

            result = await summarization_llm.ainvoke(summary_prompt)
            summary = result.content if hasattr(result, 'content') else str(result)

            # Create new message list with summary
            summary_message = SystemMessage(
                content=f"## Previous Conversation Summary\n\n{summary}"
            )

            logger.info(
                f"Summarized {len(old_messages)} messages into {self.count_tokens_str(summary)} tokens"
            )

            return [summary_message] + recent_messages

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            # Fallback: just trim
            return self.trim_to_token_limit(messages)

    def apply_strategy(
        self,
        messages: List[BaseMessage],
        strategy: Optional[ContextStrategy] = None,
        max_tokens: Optional[int] = None,
    ) -> List[BaseMessage]:
        """
        Apply a context management strategy to messages.

        Args:
            messages: Messages to process
            strategy: Strategy to apply (default: self.strategy)
            max_tokens: Token limit (default: self.available_context_tokens)

        Returns:
            Processed messages
        """
        strategy = strategy or self.strategy
        max_tokens = max_tokens or self.available_context_tokens

        current_tokens = self.count_tokens(messages)

        # If already under limit, no processing needed
        if current_tokens <= max_tokens:
            return messages

        logger.info(
            f"Applying {strategy.value} strategy: {current_tokens} → {max_tokens} tokens"
        )

        if strategy == ContextStrategy.RECENT:
            return self.trim_to_token_limit(messages, max_tokens, strategy="last")

        elif strategy == ContextStrategy.FULL:
            # User wants all messages - just warn
            logger.warning(
                f"FULL strategy requested but context exceeds limit: "
                f"{current_tokens} > {max_tokens}"
            )
            return messages

        elif strategy == ContextStrategy.QUARANTINE:
            # First quarantine large messages
            quarantined = self.quarantine_large_content(messages)
            # Then trim if still over limit
            return self.trim_to_token_limit(quarantined, max_tokens)

        elif strategy == ContextStrategy.SMART:
            # Multi-step approach:
            # 1. Quarantine very large messages
            processed = self.quarantine_large_content(messages, max_message_tokens=4000)

            # 2. Filter out tool messages if over limit
            if self.count_tokens(processed) > max_tokens:
                # Keep only human, AI, and system messages
                processed = self.filter_by_type(
                    processed,
                    include_types=[HumanMessage, AIMessage, SystemMessage]
                )

            # 3. Trim to fit
            return self.trim_to_token_limit(processed, max_tokens)

        else:  # SUMMARY - requires async
            logger.warning("SUMMARY strategy requires async - using SMART instead")
            return self.apply_strategy(messages, ContextStrategy.SMART, max_tokens)

    async def apply_strategy_async(
        self,
        messages: List[BaseMessage],
        strategy: Optional[ContextStrategy] = None,
        max_tokens: Optional[int] = None,
        summarization_llm: Optional[BaseChatModel] = None,
    ) -> List[BaseMessage]:
        """
        Apply context strategy with async support (needed for summarization).
        """
        strategy = strategy or self.strategy

        if strategy == ContextStrategy.SUMMARY:
            current_tokens = self.count_tokens(messages)
            max_tokens = max_tokens or self.available_context_tokens

            if current_tokens > max_tokens or len(messages) > self.summarization_threshold:
                return await self.summarize_context(
                    messages,
                    summarization_llm=summarization_llm
                )
            return messages
        else:
            # Other strategies are sync
            return self.apply_strategy(messages, strategy, max_tokens)


class DynamicToolLoadout:
    """
    Dynamic Tool Loadout Manager.

    Selects which tools to load based on the current task context,
    reducing token overhead from tool definitions.
    """

    def __init__(
        self,
        all_tools: Dict[str, Any],
        max_tools: int = 10,
        category_mappings: Optional[Dict[str, List[str]]] = None,
    ):
        """
        Initialize tool loadout manager.

        Args:
            all_tools: Dictionary of tool_id -> tool instance
            max_tools: Maximum number of tools to load per invocation
            category_mappings: Mapping of keywords to tool categories
        """
        self.all_tools = all_tools
        self.max_tools = max_tools
        self.category_mappings = category_mappings or self._default_mappings()

    def _default_mappings(self) -> Dict[str, List[str]]:
        """Default keyword to tool category mappings"""
        return {
            "code": ["file_read", "file_write", "search_code", "run_command"],
            "file": ["file_read", "file_write", "list_directory", "search_files"],
            "web": ["web_search", "url_fetch", "browser"],
            "database": ["sql_query", "database_schema"],
            "deploy": ["run_command", "docker", "kubernetes"],
            "test": ["run_tests", "run_command"],
            "document": ["file_read", "file_write", "search_files"],
            "research": ["web_search", "url_fetch", "calculator"],
        }

    def select_tools(
        self,
        task_description: str,
        force_include: Optional[List[str]] = None,
        force_exclude: Optional[List[str]] = None,
    ) -> List[Any]:
        """
        Select tools based on task context.

        Args:
            task_description: Description of the current task
            force_include: Tools to always include
            force_exclude: Tools to never include

        Returns:
            List of selected tool instances
        """
        force_include = force_include or []
        force_exclude = force_exclude or []

        selected_ids = set(force_include)
        task_lower = task_description.lower()

        # Match keywords to tool categories
        for keyword, tool_ids in self.category_mappings.items():
            if keyword in task_lower:
                selected_ids.update(tool_ids)

        # Remove excluded tools
        selected_ids -= set(force_exclude)

        # Limit to max_tools
        selected_ids = list(selected_ids)[:self.max_tools]

        # Return tool instances
        selected_tools = []
        for tool_id in selected_ids:
            if tool_id in self.all_tools:
                selected_tools.append(self.all_tools[tool_id])

        logger.info(f"Selected {len(selected_tools)} tools for task: {selected_ids}")

        return selected_tools


# Module-level convenience functions
_default_manager: Optional[ContextWindowManager] = None


def get_context_manager(
    model_name: str = "gpt-4o",
    max_tokens: Optional[int] = None,
    strategy: ContextStrategy = ContextStrategy.SMART,
) -> ContextWindowManager:
    """Get or create a context window manager instance"""
    global _default_manager

    if _default_manager is None or _default_manager.model_name != model_name:
        _default_manager = ContextWindowManager(
            model_name=model_name,
            max_tokens=max_tokens,
            strategy=strategy,
        )

    return _default_manager


def trim_messages_to_limit(
    messages: List[BaseMessage],
    max_tokens: int,
    strategy: str = "last",
    model_name: str = "gpt-4o",
) -> List[BaseMessage]:
    """Convenience function to trim messages to a token limit"""
    manager = get_context_manager(model_name=model_name)
    return manager.trim_to_token_limit(
        messages,
        max_tokens=max_tokens,
        strategy=strategy,
    )


def count_message_tokens(
    messages: List[BaseMessage],
    model_name: str = "gpt-4o",
) -> int:
    """Convenience function to count tokens in messages"""
    manager = get_context_manager(model_name=model_name)
    return manager.count_tokens(messages)
