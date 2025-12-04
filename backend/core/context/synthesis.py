# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Context Synthesis for LangGraph Orchestration

This module provides functions to assemble complete context packages
just-in-time for agent execution, combining static and dynamic context
with smart compaction when needed.

Enhanced with:
- Improved token counting with fallback
- Global LLM instance for compaction (lazy initialization)
- Refined compaction prompt with XML tags
- Minimum history budget enforcement
- Hard truncation fallback if compaction still exceeds budget
- XML-tagged context assembly for clearer structure
"""

import logging
import tiktoken
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables.config import RunnableConfig

from .graph_state import WorkflowState, HandoffSummary
from config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration and Initialization
# =============================================================================

# Use cl100k_base for modern models (OpenAI, Anthropic)
try:
    TOKENIZER = tiktoken.get_encoding("cl100k_base")
except Exception as e:
    logger.warning(f"Could not load cl100k_base tokenizer: {e}. Token counting might be inaccurate.")
    TOKENIZER = None  # Will use fallback


MAX_SCRATCHPAD_TOKENS = 4000  # Budget for the dynamic scratchpad
MIN_HISTORY_BUDGET = 800  # Minimum tokens to preserve for history

# Global LLM instance for compaction - initialized lazily
_compaction_llm: Optional[BaseChatModel] = None

# Refined Compaction Prompt (Context Engineering)
COMPACTION_PROMPT = """
You are the Context Synthesis Agent. Compress the historical Workflow Scratchpad while preserving critical information for the next agent.

# GOAL
Reduce the token count of the provided context to under {max_tokens} tokens.

# COMPRESSION STRATEGY
1. **Summarize Early History:** Concisely summarize the oldest entries.
2. **Preserve Key Details:** Retain architectural decisions, error resolutions, and pending items verbatim if possible.
3. **Maintain Actionability:** Ensure the compressed context allows the next agent to understand the current state.
4. **Format:** Output only the compressed context. No meta-commentary.

# HISTORICAL CONTEXT (To be compressed):
<context_to_compress>
{context_to_compress}
</context_to_compress>

# COMPRESSED CONTEXT:
"""

# =============================================================================
# Helper Functions
# =============================================================================


def get_token_count(text: str) -> int:
    """Helper to calculate token count with fallback."""
    if TOKENIZER and hasattr(TOKENIZER, 'encode'):
        return len(TOKENIZER.encode(text))
    # Fallback: rough estimate using word count * 1.3
    return int(len(text.split()) * 1.3)


def get_compaction_llm() -> BaseChatModel:
    """
    Initializes or retrieves the LLM used for context compaction (Resource-Aware Optimization).

    Uses a fast, cost-effective model for compression tasks.
    """
    global _compaction_llm

    if _compaction_llm is None:
        # Default to gpt-4o-mini for fast, cheap compression
        model_name = getattr(settings, 'COMPACTOR_MODEL_NAME', 'gpt-4o-mini')

        logger.info(f"Initializing Context Compactor LLM: {model_name}")

        try:
            # Initialize using configuration settings (Supports standard API or LiteLLM proxy)
            llm_params = {
                "model": model_name,
                "temperature": 0.1,  # Low temperature for deterministic summaries
                "max_tokens": MAX_SCRATCHPAD_TOKENS + 500,  # Ensure output capacity
            }

            # Add API key if available
            if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
                llm_params["api_key"] = settings.OPENAI_API_KEY

            # Add base URL if available (for LiteLLM proxy)
            if hasattr(settings, 'OPENAI_API_BASE') and settings.OPENAI_API_BASE:
                llm_params["base_url"] = settings.OPENAI_API_BASE

            _compaction_llm = ChatOpenAI(**llm_params)

        except Exception as e:
            logger.error(f"Failed to initialize Context Compactor LLM: {e}")
            raise RuntimeError("Context Compactor LLM initialization failed.") from e

    return _compaction_llm


def format_handoff_to_text(summary: HandoffSummary) -> str:
    """Convert a structured HandoffSummary to readable text."""
    new_entry = f"\n--- Task {summary.get('task_id')} Handoff (Attempt {summary.get('attempt')}) ---\n"
    new_entry += f"**Status:** {summary.get('status')}\n"

    if summary.get("actions_taken"):
        new_entry += "**Actions Taken:**\n" + "\n".join([f"- {a}" for a in summary.get("actions_taken", [])]) + "\n"

    if summary.get("rationale"):
        new_entry += f"**Rationale:** {summary.get('rationale')}\n"

    if summary.get("pending_items"):
        new_entry += "**Pending Items:**\n" + "\n".join([f"- {p}" for p in summary.get("pending_items", [])]) + "\n"

    return new_entry


def _truncate_text(text: str, budget: int, error_context: bool = False) -> str:
    """
    Helper for fallback truncation (keeps the most recent context).

    Args:
        text: Text to truncate
        budget: Token budget
        error_context: Whether this is due to an error (adds note)

    Returns:
        Truncated text
    """
    prefix = f"... [Older entries truncated{' due to error' if error_context else ''}] ...\n"
    budget_for_prefix = get_token_count(prefix)
    budget -= budget_for_prefix

    if TOKENIZER and hasattr(TOKENIZER, 'encode') and hasattr(TOKENIZER, 'decode'):
        try:
            tokens = TOKENIZER.encode(text)
            truncated_tokens = tokens[-budget:]
            truncated_text = TOKENIZER.decode(truncated_tokens)
        except Exception as e:
            logger.warning(f"Token truncation failed: {e}, using word-based fallback")
            words = text.split()
            truncated_words = words[-budget:]
            truncated_text = " ".join(truncated_words)
    else:
        # Fallback for basic tokenizer
        words = text.split()
        truncated_words = words[-budget:]
        truncated_text = " ".join(truncated_words)

    return prefix + truncated_text


# =============================================================================
# LangGraph Node: Context Synthesis and Compaction
# =============================================================================

async def node_synthesize_context(state: WorkflowState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Dedicated LangGraph node for Context Synthesis with Smart Compaction.

    This node processes the latest handoff and manages the workflow scratchpad
    token budget using intelligent compression when necessary.

    Args:
        state: Current workflow state
        config: LangGraph runtime configuration (v1.0 requirement)

    Returns:
        State updates with synthesized context
    """
    logger.info(f"[NODE: SYNTHESIZE CONTEXT] Processing for task {state['task_id']}")

    latest_handoff = state.get("latest_handoff")
    if not latest_handoff:
        logger.debug("No latest handoff to synthesize")
        return {}  # Nothing new to synthesize

    current_scratchpad = state.get("workflow_scratchpad", "")
    new_entry_text = format_handoff_to_text(latest_handoff)

    # 1. Update History (Append structured data)
    history = state.get("handoff_history", []).copy()
    history.append(latest_handoff)

    # 2. Check Token Budget
    combined_text = current_scratchpad + "\n" + new_entry_text
    combined_tokens_count = get_token_count(combined_text)

    if combined_tokens_count <= MAX_SCRATCHPAD_TOKENS:
        # Fits within budget, simply append
        logger.debug(f"Scratchpad within budget ({combined_tokens_count}/{MAX_SCRATCHPAD_TOKENS} tokens)")
        return {
            "workflow_scratchpad": combined_text,
            "handoff_history": history,
            "latest_handoff": None  # Clear the temporary storage
        }

    # 3. Smart Compaction (Budget exceeded)
    logger.info(
        f"Scratchpad budget exceeded ({combined_tokens_count}/{MAX_SCRATCHPAD_TOKENS} tokens). "
        f"Initiating Smart Compaction."
    )

    # Strategy: Keep the latest entry intact, compress the older history.
    new_entry_tokens_len = get_token_count(new_entry_text)
    history_budget = MAX_SCRATCHPAD_TOKENS - new_entry_tokens_len

    if history_budget < MIN_HISTORY_BUDGET:
        logger.warning(f"History budget too low ({history_budget}). Enforcing minimum: {MIN_HISTORY_BUDGET}.")
        history_budget = MIN_HISTORY_BUDGET

    # Execute LLM for compression
    prompt = COMPACTION_PROMPT.format(
        max_tokens=history_budget,
        context_to_compress=current_scratchpad
    )

    try:
        compactor_llm = get_compaction_llm()

        # Execute LLM for compression (Asynchronous)
        logger.debug(f"Executing Smart Compaction with {history_budget} token budget")
        response = await compactor_llm.ainvoke(prompt)
        compressed_history = response.content

        logger.info(
            f"Smart Compaction successful, compressed to ~{get_token_count(compressed_history)} tokens"
        )

    except Exception as e:
        # Fallback: Simple truncation if LLM fails (Resilience)
        logger.warning(f"Smart Compaction failed: {e}. Falling back to truncation.")
        compressed_history = _truncate_text(current_scratchpad, history_budget, error_context=True)

    # Combine compressed history with the new entry
    final_scratchpad = compressed_history + "\n" + new_entry_text
    final_tokens_count = get_token_count(final_scratchpad)

    # Final safety check
    if final_tokens_count > MAX_SCRATCHPAD_TOKENS:
        logger.warning(
            f"Compaction still exceeded budget ({final_tokens_count}/{MAX_SCRATCHPAD_TOKENS}). "
            f"Performing hard truncation."
        )
        final_scratchpad = _truncate_text(final_scratchpad, MAX_SCRATCHPAD_TOKENS)
        final_tokens_count = get_token_count(final_scratchpad)

    logger.info(f"Context synthesis complete: {final_tokens_count}/{MAX_SCRATCHPAD_TOKENS} tokens")

    return {
        "workflow_scratchpad": final_scratchpad,
        "handoff_history": history,
        "latest_handoff": None  # Clear temporary storage
    }


# =============================================================================
# Context Assembly
# =============================================================================

async def assemble_context_package(state: WorkflowState) -> str:
    """
    Combines the synthesized scratchpad (dynamic) with the static context.
    Prioritizes dynamic context for better agent attention (Context Engineering).

    Uses XML tags for clear delineation between context types.

    Args:
        state: Current workflow state

    Returns:
        Complete context package with XML-tagged sections
    """
    logger.debug(f"Assembling context package for task {state['task_id']}")

    scratchpad = state.get("workflow_scratchpad", "")
    static_context = state.get("static_context_package", "")

    package = ""

    # 1. Dynamic Context (High Priority - Placed First) - Uses XML tags for clear delineation
    if scratchpad:
        package += f"""<dynamic_context_scratchpad>
DESCRIPTION: Recent history of the workflow, actions by previous agents, rationale, and pending items.
CONTENT:
{scratchpad.strip()}
</dynamic_context_scratchpad>

"""

    # 2. Static Context (Background Knowledge)
    if static_context:
        package += f"""<static_context>
DESCRIPTION: Foundational project information, RAG results, architectural guidelines.
CONTENT:
{static_context.strip()}
</static_context>
"""

    total_tokens = get_token_count(package)
    logger.debug(f"Assembled context package: {total_tokens} tokens")

    return package.strip()


# =============================================================================
# Context Preparation Helpers
# =============================================================================

def prepare_agent_context(
    state: WorkflowState,
    include_latest_handoff: bool = True,
    additional_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Prepare a structured context dictionary for agent consumption.

    This provides a more structured alternative to the plain text context package.

    Args:
        state: Current workflow state
        include_latest_handoff: Whether to include the latest handoff summary
        additional_context: Optional additional context to include

    Returns:
        Structured context dictionary
    """
    context = {
        "task_id": state["task_id"],
        "project_id": state["project_id"],
        "directive": state["current_directive"],
        "classification": state["classification"].value,
        "executor_type": state["executor_type"].value,
        "retry_count": state["retry_count"],
        "static_context": state["static_context_package"],
        "workflow_scratchpad": state["workflow_scratchpad"],
    }

    # Include latest handoff if available and requested
    if include_latest_handoff and state.get("latest_handoff"):
        context["latest_handoff"] = state["latest_handoff"]

    # Include handoff history summary
    context["handoff_count"] = len(state["handoff_history"])
    if state["handoff_history"]:
        # Include summary of recent handoffs
        recent_handoffs = state["handoff_history"][-3:]  # Last 3 handoffs
        context["recent_handoffs"] = [
            {
                "status": h["status"],
                "rationale": h["rationale"],
                "actions_count": len(h["actions_taken"])
            }
            for h in recent_handoffs
        ]

    # Add any additional context
    if additional_context:
        context.update(additional_context)

    return context


async def update_context_with_handoff(
    state: WorkflowState,
    handoff_data: Dict[str, Any],
    auto_compact: bool = True
) -> WorkflowState:
    """
    Update the workflow state with a new handoff and optionally perform compaction.

    Args:
        state: Current workflow state to update
        handoff_data: Handoff summary data from the agent
        auto_compact: Whether to automatically perform compaction if needed

    Returns:
        Updated workflow state
    """
    from .graph_state import create_handoff_summary, add_handoff_to_state

    # Create structured handoff summary
    handoff = create_handoff_summary(
        task_id=state["task_id"],
        attempt=state["retry_count"] + 1,
        actions_taken=handoff_data.get("actions_taken", []),
        rationale=handoff_data.get("rationale", ""),
        pending_items=handoff_data.get("pending_items", []),
        status=handoff_data.get("status", "UNKNOWN")
    )

    # Check if we need compaction
    compacted_scratchpad = None
    if auto_compact:
        # Check if adding this handoff would exceed budget
        temp_text = state.get("workflow_scratchpad", "") + "\n" + format_handoff_to_text(handoff)
        if get_token_count(temp_text) > MAX_SCRATCHPAD_TOKENS:
            # Perform compaction via the synthesis node
            temp_state = state.copy()
            temp_state["latest_handoff"] = handoff
            synthesis_result = await node_synthesize_context(temp_state)
            compacted_scratchpad = synthesis_result.get("workflow_scratchpad")
            logger.info(f"Auto-compaction performed for task {state['task_id']}")

    # Add handoff to state
    updated_state = add_handoff_to_state(
        state,
        handoff,
        compacted_scratchpad
    )

    return updated_state


def extract_handoff_from_result(task_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract handoff summary data from Celery task result.

    This function handles different result formats and extracts the handoff
    summary data in a consistent format.

    Args:
        task_result: Result dictionary from Celery task

    Returns:
        Handoff data dictionary
    """
    # Try different locations where handoff data might be stored
    handoff_locations = [
        "result.handoff_summary",  # Standard location from our execute_task
        "handoff_summary",
        "summary",
        "agent_summary"
    ]

    for location in handoff_locations:
        handoff_data = _get_nested_value(task_result, location)
        if handoff_data and isinstance(handoff_data, dict):
            # Handle our new execute_task format directly
            if handoff_data and "key_observations" in handoff_data:
                # Convert our format to the expected format
                return {
                    "actions_taken": handoff_data.get("key_observations", ["Task completed"]),
                    "rationale": f"Executed with {handoff_data.get('tool_used', 'unknown tool')}",
                    "pending_items": [],
                    "status": "SUCCESS" if handoff_data.get("execution_duration_seconds", 0) > 0 else "UNKNOWN"
                }
            # Legacy format
            elif "actions_taken" in handoff_data:
                return handoff_data

    # Fallback: construct basic handoff from available data
    return {
        "actions_taken": task_result.get("actions", ["Task completed"]),
        "rationale": task_result.get("message", "No detailed rationale provided"),
        "pending_items": task_result.get("pending", []),
        "status": task_result.get("status", "COMPLETED")
    }


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Get nested value from dictionary using dot notation path."""
    keys = path.split('.')
    current = data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None

    return current
