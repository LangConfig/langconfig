# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangChain v1.0 Standard Content Blocks Support

Provides unified access to modern LLM features across providers:
- Reasoning traces (extended thinking)
- Citations and sources
- Built-in tools (web search, code interpreters)
- Text content
- Tool calls
- Structured outputs

The content_blocks property introduces a standard representation that works
across Anthropic, OpenAI, Google, AWS Bedrock, and other providers.

Example:
    >>> from langchain_anthropic import ChatAnthropic
    >>> from core.context.content_blocks import extract_content_blocks, format_content_blocks
    >>>
    >>> model = ChatAnthropic(model="claude-sonnet-4-5")
    >>> response = model.invoke("What's the capital of France?")
    >>>
    >>> # Access content blocks in a provider-agnostic way
    >>> blocks = extract_content_blocks(response)
    >>> for block in blocks:
    ...     if block["type"] == "reasoning":
    ...         print(f"Model reasoning: {block['reasoning']}")
    ...     elif block["type"] == "text":
    ...         print(f"Response: {block['text']}")

Supported Provider Integrations:
- langchain-anthropic
- langchain-aws (Bedrock)
- langchain-openai
- langchain-google-genai
- langchain-ollama
"""

import logging
from typing import Any, Dict, List, Optional, Union
from langchain.messages import BaseMessage, AIMessage

logger = logging.getLogger(__name__)


# =============================================================================
# Content Block Types
# =============================================================================

class ContentBlockType:
    """Standard content block types in v1.0."""
    TEXT = "text"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    CITATION = "citation"
    IMAGE = "image"
    THINKING = "thinking"  # Extended thinking for o1 models
    # MCP multimodal content types
    AUDIO = "audio"
    FILE = "file"
    RESOURCE = "resource"  # For embedded MCP resources


# =============================================================================
# Content Block Extraction
# =============================================================================

def extract_content_blocks(message: BaseMessage) -> List[Dict[str, Any]]:
    """
    Extract standard content blocks from a message.

    Provides unified access to content blocks across different providers.
    Supports lazy loading - only processes if content_blocks property is accessed.

    Args:
        message: Message instance (AIMessage, HumanMessage, etc.)

    Returns:
        List of content block dictionaries with type-specific fields

    Example:
        >>> blocks = extract_content_blocks(ai_message)
        >>> for block in blocks:
        ...     if block["type"] == "text":
        ...         print(block["text"])
        ...     elif block["type"] == "reasoning":
        ...         print(f"Reasoning: {block['reasoning']}")
    """

    # Check if message has native content_blocks support (v1.0+)
    if hasattr(message, 'content_blocks'):
        try:
            # Lazy loading - this triggers block extraction
            return list(message.content_blocks)
        except Exception as e:
            logger.warning(f"Error accessing content_blocks: {e}")
            return _extract_fallback_blocks(message)

    # Fallback for messages without native content_blocks
    return _extract_fallback_blocks(message)


def _extract_fallback_blocks(message: BaseMessage) -> List[Dict[str, Any]]:
    """
    Fallback extraction for messages without native content_blocks.

    Manually extracts common block types from message attributes.
    """
    blocks = []

    # Extract text content
    if hasattr(message, 'content') and isinstance(message.content, str):
        blocks.append({
            "type": ContentBlockType.TEXT,
            "text": message.content
        })

    # Extract tool calls (if AIMessage)
    if isinstance(message, AIMessage) and hasattr(message, 'tool_calls'):
        tool_calls = message.tool_calls or []
        for tool_call in tool_calls:
            blocks.append({
                "type": ContentBlockType.TOOL_CALL,
                "id": tool_call.get("id"),
                "name": tool_call.get("name"),
                "args": tool_call.get("args", {})
            })

    # Extract reasoning/thinking from response_metadata
    if hasattr(message, 'response_metadata'):
        metadata = message.response_metadata or {}

        # Anthropic extended thinking
        if "thinking" in metadata:
            blocks.append({
                "type": ContentBlockType.THINKING,
                "content": metadata["thinking"]
            })

        # Reasoning traces
        if "reasoning" in metadata:
            blocks.append({
                "type": ContentBlockType.REASONING,
                "reasoning": metadata["reasoning"]
            })

    return blocks


# =============================================================================
# Content Block Filtering
# =============================================================================

def filter_blocks_by_type(blocks: List[Dict[str, Any]], block_type: str) -> List[Dict[str, Any]]:
    """
    Filter content blocks by type.

    Args:
        blocks: List of content blocks
        block_type: Type to filter for (e.g., "text", "reasoning", "tool_call")

    Returns:
        Filtered list of blocks matching the type

    Example:
        >>> blocks = extract_content_blocks(message)
        >>> text_blocks = filter_blocks_by_type(blocks, "text")
        >>> reasoning_blocks = filter_blocks_by_type(blocks, "reasoning")
    """
    return [block for block in blocks if block.get("type") == block_type]


def get_text_content(blocks: List[Dict[str, Any]]) -> str:
    """
    Extract all text content from blocks.

    Args:
        blocks: List of content blocks

    Returns:
        Concatenated text from all text blocks

    Example:
        >>> blocks = extract_content_blocks(message)
        >>> text = get_text_content(blocks)
    """
    text_blocks = filter_blocks_by_type(blocks, ContentBlockType.TEXT)
    return "\n".join(block.get("text", "") for block in text_blocks)


def get_reasoning(blocks: List[Dict[str, Any]]) -> Optional[str]:
    """
    Extract reasoning content from blocks.

    Args:
        blocks: List of content blocks

    Returns:
        Reasoning content if present, None otherwise

    Example:
        >>> blocks = extract_content_blocks(message)
        >>> reasoning = get_reasoning(blocks)
        >>> if reasoning:
        ...     print(f"Model's reasoning: {reasoning}")
    """
    reasoning_blocks = filter_blocks_by_type(blocks, ContentBlockType.REASONING)
    if reasoning_blocks:
        return reasoning_blocks[0].get("reasoning")

    # Also check thinking blocks (o1 models)
    thinking_blocks = filter_blocks_by_type(blocks, ContentBlockType.THINKING)
    if thinking_blocks:
        return thinking_blocks[0].get("content")

    return None


def get_tool_calls(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract tool calls from blocks.

    Args:
        blocks: List of content blocks

    Returns:
        List of tool call blocks

    Example:
        >>> blocks = extract_content_blocks(message)
        >>> tool_calls = get_tool_calls(blocks)
        >>> for call in tool_calls:
        ...     print(f"Tool: {call['name']}({call['args']})")
    """
    return filter_blocks_by_type(blocks, ContentBlockType.TOOL_CALL)


# =============================================================================
# Content Block Formatting
# =============================================================================

def format_content_blocks(blocks: List[Dict[str, Any]], include_reasoning: bool = True) -> str:
    """
    Format content blocks into a human-readable string.

    Args:
        blocks: List of content blocks
        include_reasoning: Whether to include reasoning/thinking blocks

    Returns:
        Formatted string representation

    Example:
        >>> blocks = extract_content_blocks(message)
        >>> formatted = format_content_blocks(blocks)
        >>> print(formatted)
    """
    parts = []

    for block in blocks:
        block_type = block.get("type")

        if block_type == ContentBlockType.TEXT:
            parts.append(block.get("text", ""))

        elif block_type == ContentBlockType.REASONING and include_reasoning:
            reasoning = block.get("reasoning", "")
            parts.append(f"[Reasoning: {reasoning}]")

        elif block_type == ContentBlockType.THINKING and include_reasoning:
            thinking = block.get("content", "")
            parts.append(f"[Thinking: {thinking}]")

        elif block_type == ContentBlockType.TOOL_CALL:
            name = block.get("name", "unknown")
            args = block.get("args", {})
            parts.append(f"[Tool Call: {name}({args})]")

        elif block_type == ContentBlockType.CITATION:
            source = block.get("source", "")
            parts.append(f"[Citation: {source}]")

    return "\n".join(parts)


# =============================================================================
# Content Block Middleware
# =============================================================================

class ContentBlockMiddleware:
    """
    Middleware for logging and analyzing content blocks.

    Example:
        >>> from core.agents.factory import AgentFactory
        >>> from core.context.content_blocks import ContentBlockMiddleware
        >>>
        >>> middleware = ContentBlockMiddleware(
        ...     log_reasoning=True,
        ...     log_tool_calls=True
        ... )
    """

    def __init__(
        self,
        log_reasoning: bool = True,
        log_tool_calls: bool = True,
        log_citations: bool = False
    ):
        """
        Initialize content block middleware.

        Args:
            log_reasoning: Whether to log reasoning/thinking blocks
            log_tool_calls: Whether to log tool calls
            log_citations: Whether to log citations
        """
        self.log_reasoning = log_reasoning
        self.log_tool_calls = log_tool_calls
        self.log_citations = log_citations

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """
        Process content blocks after model responds.

        Logs interesting blocks based on configuration.
        """
        messages = state.get("messages", [])

        if not messages:
            return None

        last_message = messages[-1]

        if not isinstance(last_message, AIMessage):
            return None

        # Extract and process content blocks
        blocks = extract_content_blocks(last_message)

        if self.log_reasoning:
            reasoning = get_reasoning(blocks)
            if reasoning:
                logger.info(f"🧠 Model Reasoning: {reasoning[:200]}...")

        if self.log_tool_calls:
            tool_calls = get_tool_calls(blocks)
            if tool_calls:
                for call in tool_calls:
                    logger.info(f"🔧 Tool Call: {call['name']}({call['args']})")

        if self.log_citations:
            citations = filter_blocks_by_type(blocks, ContentBlockType.CITATION)
            if citations:
                for citation in citations:
                    logger.info(f"📚 Citation: {citation.get('source', 'unknown')}")

        # Don't modify state
        return None


# =============================================================================
# Utility Functions
# =============================================================================

def has_reasoning(message: BaseMessage) -> bool:
    """
    Check if message contains reasoning/thinking blocks.

    Args:
        message: Message to check

    Returns:
        True if reasoning present, False otherwise

    Example:
        >>> if has_reasoning(ai_message):
        ...     reasoning = get_reasoning(extract_content_blocks(ai_message))
        ...     print(f"Model reasoning: {reasoning}")
    """
    blocks = extract_content_blocks(message)
    return get_reasoning(blocks) is not None


def has_tool_calls(message: BaseMessage) -> bool:
    """
    Check if message contains tool calls.

    Args:
        message: Message to check

    Returns:
        True if tool calls present, False otherwise
    """
    blocks = extract_content_blocks(message)
    return len(get_tool_calls(blocks)) > 0


def count_blocks_by_type(blocks: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Count blocks by type.

    Args:
        blocks: List of content blocks

    Returns:
        Dictionary mapping block type to count

    Example:
        >>> blocks = extract_content_blocks(message)
        >>> counts = count_blocks_by_type(blocks)
        >>> print(f"Text blocks: {counts.get('text', 0)}")
        >>> print(f"Tool calls: {counts.get('tool_call', 0)}")
    """
    counts = {}
    for block in blocks:
        block_type = block.get("type", "unknown")
        counts[block_type] = counts.get(block_type, 0) + 1
    return counts


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Example with simulated message
    from langchain.messages import AIMessage

    # Create a mock message with content blocks
    message = AIMessage(
        content="The capital of France is Paris.",
        response_metadata={
            "reasoning": "I know this from my training data about geography.",
            "token_usage": {"total_tokens": 50}
        }
    )

    # Extract content blocks
    blocks = extract_content_blocks(message)

    print("Content Blocks:")
    print("=" * 50)

    for i, block in enumerate(blocks):
        print(f"{i + 1}. Type: {block['type']}")
        print(f"   Content: {block}")
        print()

    # Get specific content
    text = get_text_content(blocks)
    reasoning = get_reasoning(blocks)

    print(f"Text: {text}")
    print(f"Reasoning: {reasoning}")

    # Format all blocks
    formatted = format_content_blocks(blocks)
    print("\nFormatted:")
    print(formatted)
