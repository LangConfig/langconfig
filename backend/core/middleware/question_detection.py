# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Question Detection Middleware for HITL (Human-in-the-Loop)

Automatically detects when an agent asks a question and pauses workflow
execution to wait for user input via the HITL system.

Example patterns detected:
- "Would you prefer to test another workflow capability?"
- "Should I proceed with option A or B?"
- "What database should I use?"
- "Which approach do you want?"
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.messages import AIMessage
from core.middleware.core import AgentMiddleware

logger = logging.getLogger(__name__)


class QuestionDetectionMiddleware(AgentMiddleware):
    """
    Detects when an agent asks a question and triggers HITL pause.

    This middleware analyzes the agent's output after each model call.
    If the output contains question patterns, it sets an interrupt flag
    that causes the workflow to pause and wait for user input.

    Question patterns detected:
    - Ends with "?"
    - Contains interrogative phrases: "Would you", "Should I", "Which option"
    - Uses question words: "what", "when", "where", "who", "why", "how"

    Example:
        >>> middleware = [QuestionDetectionMiddleware()]
        >>> # Agent asks: "Would you prefer...?"
        >>> # Workflow pauses, HITL UI shown to user
    """

    # Interrogative patterns that indicate a question
    QUESTION_PATTERNS = [
        "would you prefer",
        "should i",
        "which option",
        "do you want",
        "what would you like",
        "can you clarify",
        "could you specify",
        "would you like me to",
        "shall i",
        "do you prefer",
        "which approach",
        "what database",
        "what framework",
        "which model",
        "which strategy"
    ]

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """
        Analyze agent output for question patterns.

        Called after the model generates a response.
        Checks if the response contains a question and sets interrupt flag.

        Args:
            state: Current workflow state with messages
            runtime: Runtime context

        Returns:
            State update with interrupt flag if question detected, None otherwise
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        # Get the last AI message
        last_msg = messages[-1]
        if not isinstance(last_msg, AIMessage):
            return None

        content = last_msg.content
        if not isinstance(content, str):
            return None

        content_lower = content.lower().strip()

        # Check for question mark (most obvious indicator)
        has_question_mark = content_lower.endswith("?")

        # Check for interrogative patterns
        has_interrogative = any(pattern in content_lower for pattern in self.QUESTION_PATTERNS)

        # Detect if this is a question
        is_question = has_question_mark or has_interrogative

        if is_question:
            logger.warning(f"🤔 Question detected - triggering HITL: {content[:100]}...")

            # Set interrupt flag in state to pause workflow
            return {
                "interrupt_requested": True,
                "interrupt_reason": "agent_question",
                "pending_question": content,
                "awaiting_user_input": True
            }

        return None


class AlwaysAskMiddleware(AgentMiddleware):
    """
    Development/testing middleware that always triggers HITL.

    Useful for testing the HITL system without needing actual questions.
    DO NOT enable in production - will pause after every agent response!

    Example:
        >>> middleware = [AlwaysAskMiddleware()]  # For testing only!
    """

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Always trigger HITL for testing."""
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage):
            logger.info("🛑 AlwaysAskMiddleware - forcing HITL pause for testing")
            return {
                "interrupt_requested": True,
                "interrupt_reason": "testing_always_ask",
                "awaiting_user_input": True
            }

        return None
