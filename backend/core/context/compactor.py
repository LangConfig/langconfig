# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Smart Compaction Service for Context Window Management

This service implements intelligent context compaction using LLM summarization
to prevent exceeding context windows while preserving critical information.
"""

import logging
from typing import List, Optional, Tuple
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseLLM

from .graph_state import WorkflowState, HandoffSummary

logger = logging.getLogger(__name__)


class ContextCompactor:
    """Manages context window size through intelligent summarization."""
    
    def __init__(
        self,
        llm: BaseLLM,
        max_context_tokens: int = 8000,
        compaction_threshold: float = 0.75,
        preserve_recent_steps: int = 3
    ):
        """
        Initialize the context compactor.
        
        Args:
            llm: Language model for summarization (ideally local-qwen3 for efficiency)
            max_context_tokens: Maximum allowed context tokens
            compaction_threshold: Trigger compaction when context reaches this % of max
            preserve_recent_steps: Number of recent handoffs to keep uncompacted
        """
        self.llm = llm
        self.max_context_tokens = max_context_tokens
        self.compaction_threshold = compaction_threshold
        self.preserve_recent_steps = preserve_recent_steps
        
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Uses a rough approximation of 4 characters per token.
        For production, consider using tiktoken or the model's tokenizer.
        """
        return len(text) // 4
    
    def needs_compaction(self, state: WorkflowState) -> bool:
        """
        Determine if context compaction is needed.
        
        Args:
            state: Current workflow state
            
        Returns:
            True if compaction should be triggered
        """
        total_context = self._get_total_context(state)
        token_count = self.estimate_tokens(total_context)
        threshold_tokens = int(self.max_context_tokens * self.compaction_threshold)
        
        logger.debug(f"Context tokens: {token_count}/{self.max_context_tokens} (threshold: {threshold_tokens})")
        
        return token_count > threshold_tokens
    
    async def compact_context(self, state: WorkflowState) -> str:
        """
        Perform smart compaction of the workflow context.
        
        Args:
            state: Current workflow state
            
        Returns:
            Compacted scratchpad text
        """
        if not self.needs_compaction(state):
            return state["workflow_scratchpad"]
        
        logger.info("Performing context compaction...")
        
        # Split handoffs into old (to compact) and recent (to preserve)
        handoffs = state["handoff_history"]
        if len(handoffs) <= self.preserve_recent_steps:
            # Not enough history to compact
            return state["workflow_scratchpad"]
        
        old_handoffs = handoffs[:-self.preserve_recent_steps]
        recent_handoffs = handoffs[-self.preserve_recent_steps:]
        
        # Generate summary of old handoffs
        old_summary = await self._summarize_handoffs(old_handoffs, state)
        
        # Rebuild scratchpad with compacted history + recent details
        compacted_scratchpad = old_summary
        
        # Add recent handoffs in detail
        for i, handoff in enumerate(recent_handoffs, len(old_handoffs) + 1):
            entry = self._format_handoff_entry(handoff, i)
            compacted_scratchpad += f"\n\n{entry}"
        
        # Log compaction statistics
        original_tokens = self.estimate_tokens(state["workflow_scratchpad"])
        compacted_tokens = self.estimate_tokens(compacted_scratchpad)
        reduction = ((original_tokens - compacted_tokens) / original_tokens) * 100
        
        logger.info(f"Compaction complete: {original_tokens} -> {compacted_tokens} tokens ({reduction:.1f}% reduction)")
        
        return compacted_scratchpad
    
    async def _summarize_handoffs(self, handoffs: List[HandoffSummary], state: WorkflowState) -> str:
        """
        Use LLM to summarize a list of handoff summaries.
        
        Args:
            handoffs: List of handoff summaries to compact
            state: Current workflow state for context
            
        Returns:
            Compacted summary text
        """
        if not handoffs:
            return ""
        
        # Prepare the detailed history for summarization
        detailed_history = []
        for i, handoff in enumerate(handoffs, 1):
            entry = self._format_handoff_entry(handoff, i)
            detailed_history.append(entry)
        
        history_text = "\n\n".join(detailed_history)
        
        # Create summarization prompt
        system_prompt = """You are a technical workflow summarizer. Your task is to create a concise but comprehensive summary of development workflow steps.

CRITICAL REQUIREMENTS:
1. Preserve all technical decisions and their rationales
2. Maintain key error messages and resolution approaches
3. Keep important file names, commands, and configuration changes
4. Preserve context that future steps might reference
5. Remove redundant descriptions but keep essential facts

Output a clear, chronological summary that another agent could use to understand what has been accomplished and why."""

        user_prompt = f"""Summarize the following workflow history for task {state['task_id']}:

Original Directive: {state['original_directive']}

Workflow History:
{history_text}

Create a concise summary that preserves all critical information for continuing this workflow."""

        try:
            # Use the LLM to generate the summary
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            summary = response.content if hasattr(response, 'content') else str(response)
            
            # Add compaction metadata
            compacted_summary = f"=== COMPACTED HISTORY (Steps 1-{len(handoffs)}) ===\n{summary}\n\n=== RECENT DETAILED HISTORY ===\n"
            
            return compacted_summary
            
        except Exception as e:
            logger.error(f"Failed to generate LLM summary: {e}")
            # Fallback to simple truncation summary
            return self._fallback_summary(handoffs)
    
    def _format_handoff_entry(self, handoff: HandoffSummary, step_number: int) -> str:
        """Format a handoff summary as a readable entry."""
        actions = "\n  - ".join(handoff["actions_taken"])
        pending = "\n  - ".join(handoff["pending_items"]) if handoff["pending_items"] else "None"
        
        return f"""Step {step_number} ({handoff['status']}):
Actions Taken:
  - {actions}
Rationale: {handoff['rationale']}
Pending Items:
  - {pending}"""
    
    def _fallback_summary(self, handoffs: List[HandoffSummary]) -> str:
        """Generate a simple fallback summary without LLM."""
        summary_parts = [f"=== COMPACTED HISTORY (Steps 1-{len(handoffs)}) ==="]
        
        status_counts = {}
        key_actions = []
        
        for handoff in handoffs:
            status = handoff["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Extract key actions
            for action in handoff["actions_taken"][:2]:  # Top 2 actions per step
                if len(action) < 100:  # Avoid very long actions
                    key_actions.append(action)
        
        # Summarize status distribution
        status_summary = ", ".join([f"{count} {status}" for status, count in status_counts.items()])
        summary_parts.append(f"Completed {len(handoffs)} steps: {status_summary}")
        
        # Add key actions
        if key_actions:
            summary_parts.append("\nKey actions performed:")
            for action in key_actions[:10]:  # Limit to top 10 actions
                summary_parts.append(f"  - {action}")
        
        summary_parts.append("\n=== RECENT DETAILED HISTORY ===\n")
        
        return "\n".join(summary_parts)
    
    def _get_total_context(self, state: WorkflowState) -> str:
        """Get the total context that would be sent to an LLM."""
        return f"{state['static_context_package']}\n\n{state['workflow_scratchpad']}"


# Factory function for easy instantiation
def create_context_compactor(
    llm: BaseLLM,
    max_context_tokens: int = 8000
) -> ContextCompactor:
    """
    Create a context compactor with sensible defaults.
    
    Args:
        llm: Language model for summarization (recommend local-qwen3)
        max_context_tokens: Maximum context window size
        
    Returns:
        Configured ContextCompactor instance
    """
    return ContextCompactor(
        llm=llm,
        max_context_tokens=max_context_tokens,
        compaction_threshold=0.75,  # Compact at 75% of max tokens
        preserve_recent_steps=3     # Keep last 3 steps in full detail
    )