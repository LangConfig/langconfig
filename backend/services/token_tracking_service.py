"""In-memory token tracking service used by LangChain callbacks.

This keeps the callback path operational for local development and tests. A
database-backed implementation can replace the singleton without changing the
callback interface.
"""

from enum import Enum
from typing import Any, Dict, List


class TokenCategory(str, Enum):
    SYSTEM_PROMPT = "system_prompt"
    MODEL_OUTPUT = "model_output"
    TOOL_CALLS = "tool_calls"
    TOOL_RESPONSES = "tool_responses"
    CONTEXT = "context"
    RAG_CONTEXT = "rag_context"


class TokenTrackingService:
    def __init__(self) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.usage: Dict[str, List[Dict[str, Any]]] = {}

    async def start_session(
        self,
        session_id: str,
        agent_id: str,
        model: str,
        mcp_tools: List[str] | None = None,
    ) -> None:
        self.sessions[session_id] = {
            "agent_id": agent_id,
            "model": model,
            "mcp_tools": mcp_tools or [],
        }
        self.usage.setdefault(session_id, [])

    async def track_usage(
        self,
        session_id: str,
        category: TokenCategory,
        input_tokens: int,
        output_tokens: int,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        self.usage.setdefault(session_id, []).append({
            "category": category.value if isinstance(category, TokenCategory) else str(category),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "metadata": metadata or {},
        })

    async def end_session(self, session_id: str) -> Dict[str, Any]:
        entries = self.usage.get(session_id, [])
        total_input = sum(item.get("input_tokens", 0) for item in entries)
        total_output = sum(item.get("output_tokens", 0) for item in entries)
        total_tokens = total_input + total_output
        return {
            "session_id": session_id,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "total_cost": 0.0,
        }


_token_tracker = TokenTrackingService()


def get_token_tracker() -> TokenTrackingService:
    return _token_tracker
