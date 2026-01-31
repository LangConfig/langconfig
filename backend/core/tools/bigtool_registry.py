"""
langgraph-bigtool integration for dynamic tool search.

When an agent has many tools (15+), binding all upfront degrades performance.
langgraph-bigtool provides a "tool search" meta-tool that queries a registry
and dynamically loads relevant tools at runtime.

API note (langgraph-bigtool 0.0.3):
    create_agent(llm, tool_registry, ...) -> StateGraph
    tool_registry is dict[str, Union[BaseTool, Callable]]
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

try:
    from langgraph_bigtool import create_agent
    BIGTOOL_AVAILABLE = True
except ImportError:
    BIGTOOL_AVAILABLE = False
    logger.info("langgraph-bigtool not installed. Dynamic tool search unavailable.")

BIGTOOL_SUGGESTION_THRESHOLD = 15


def build_bigtool_agent(
    model: BaseChatModel,
    tools: List[BaseTool],
    system_prompt: Optional[str] = None,
) -> Any:
    """Build an agent with dynamic tool search via langgraph-bigtool.

    Instead of binding all tools upfront, this creates a StateGraph agent
    equipped with a tool-retrieval meta-tool. The agent dynamically searches
    the registry and loads only the relevant tools at each step.

    Args:
        model: The chat model (LLM) to use.
        tools: List of LangChain tools to register.
        system_prompt: Optional system prompt (not directly supported by
            create_agent; callers can prepend to messages if needed).

    Returns:
        A LangGraph StateGraph ready to be compiled and invoked.

    Raises:
        ImportError: If langgraph-bigtool is not installed.
    """
    if not BIGTOOL_AVAILABLE:
        raise ImportError(
            "langgraph-bigtool is required. Install with: pip install langgraph-bigtool"
        )

    # Build the tool registry dict expected by create_agent
    tool_registry: Dict[str, Any] = {tool.name: tool for tool in tools}

    logger.info(f"[BIGTOOL] Building agent with {len(tool_registry)} tools in registry")

    return create_agent(model, tool_registry)


def should_suggest_bigtool(tool_count: int) -> bool:
    """Return True if tool count is high enough to benefit from bigtool.

    Args:
        tool_count: Number of tools the agent will use.

    Returns:
        True if bigtool is available AND tool_count >= threshold (15).
    """
    return BIGTOOL_AVAILABLE and tool_count >= BIGTOOL_SUGGESTION_THRESHOLD
