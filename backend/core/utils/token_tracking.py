# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Token Tracking Callback Handler for LangChain

Integrates with TokenTrackingService to automatically track token usage
for all LangChain/LangGraph agent executions.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from uuid import UUID
from datetime import datetime

# IMPORTANT: LangChain v1.0 - callbacks moved to langchain_core
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from langchain_core.agents import AgentAction, AgentFinish

from services.token_tracking_service import (
    get_token_tracker, 
    TokenCategory
)

logger = logging.getLogger(__name__)


class TokenTrackingCallback(BaseCallbackHandler):
    """
    LangChain callback handler that tracks token usage.
    
    Integrates with TokenTrackingService to provide real-time
    token usage tracking across all agent executions.
    """
    
    def __init__(
        self,
        session_id: str,
        agent_id: str,
        project_id: int,
        task_id: str,
        mcp_tools: List[str] = None
    ):
        """
        Initialize callback handler.
        
        Args:
            session_id: Unique session identifier
            agent_id: Agent template ID
            project_id: Project ID for tracking
            task_id: Task ID for tracking
            mcp_tools: List of MCP tools available to agent
        """
        super().__init__()
        self.session_id = session_id
        self.agent_id = agent_id
        self.project_id = project_id
        self.task_id = task_id
        self.mcp_tools = mcp_tools or []
        self.tracker = get_token_tracker()
        self.model_name = None
        self._session_started = False
    
    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any
    ) -> None:
        """Called when LLM starts generating."""
        # Extract model name
        invocation_params = kwargs.get("invocation_params", {})
        self.model_name = (
            invocation_params.get("model_name") or
            invocation_params.get("model") or
            kwargs.get("name", "unknown")
        )
        
        # Start tracking session if not already started
        if not self._session_started:
            await self.tracker.start_session(
                session_id=self.session_id,
                agent_id=self.agent_id,
                model=self.model_name,
                mcp_tools=self.mcp_tools
            )
            self._session_started = True
        
        # Track system prompt tokens (estimate)
        if prompts:
            # Rough estimate: 4 chars = 1 token
            system_tokens = sum(len(p) // 4 for p in prompts)
            await self.tracker.track_usage(
                session_id=self.session_id,
                category=TokenCategory.SYSTEM_PROMPT,
                input_tokens=system_tokens,
                output_tokens=0,
                metadata={
                    "project_id": self.project_id,
                    "task_id": self.task_id
                }
            )
    
    async def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any
    ) -> None:
        """Called when LLM finishes generating."""
        if not self._session_started:
            return
            
        # Extract token usage from response
        if hasattr(response, "llm_output") and response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            
            if token_usage:
                input_tokens = token_usage.get("prompt_tokens", 0)
                output_tokens = token_usage.get("completion_tokens", 0)
                
                await self.tracker.track_usage(
                    session_id=self.session_id,
                    category=TokenCategory.MODEL_OUTPUT,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    metadata={
                        "project_id": self.project_id,
                        "task_id": self.task_id,
                        "model": self.model_name
                    }
                )
    
    async def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        **kwargs: Any
    ) -> None:
        """Called when chat model starts."""
        # Similar to on_llm_start but for chat models
        invocation_params = kwargs.get("invocation_params", {})
        self.model_name = (
            invocation_params.get("model_name") or
            invocation_params.get("model") or
            kwargs.get("name", "unknown")
        )
        
        if not self._session_started:
            await self.tracker.start_session(
                session_id=self.session_id,
                agent_id=self.agent_id,
                model=self.model_name,
                mcp_tools=self.mcp_tools
            )
            self._session_started = True
    
    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any
    ) -> None:
        """Called when tool execution starts."""
        # Track tool input tokens
        tool_name = serialized.get("name", "unknown")
        input_tokens = len(input_str) // 4  # Rough estimate
        
        await self.tracker.track_usage(
            session_id=self.session_id,
            category=TokenCategory.TOOL_CALLS,
            input_tokens=input_tokens,
            output_tokens=0,
            metadata={
                "project_id": self.project_id,
                "task_id": self.task_id,
                "tool": tool_name
            }
        )
    
    async def on_tool_end(
        self,
        output: str,
        **kwargs: Any
    ) -> None:
        """Called when tool execution ends."""
        # Track tool output tokens
        output_tokens = len(output) // 4  # Rough estimate
        
        await self.tracker.track_usage(
            session_id=self.session_id,
            category=TokenCategory.TOOL_RESPONSES,
            input_tokens=0,
            output_tokens=output_tokens,
            metadata={
                "project_id": self.project_id,
                "task_id": self.task_id
            }
        )
    
    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs: Any
    ) -> None:
        """Called when chain execution ends."""
        # End session and get summary
        if self._session_started:
            summary = await self.tracker.end_session(self.session_id)
            logger.info(
                f"Token usage summary for {self.agent_id}: "
                f"{summary.get('total_tokens', 0)} tokens, "
                f"${summary.get('total_cost', 0):.4f}"
            )
    
    async def on_agent_action(
        self,
        action: AgentAction,
        **kwargs: Any
    ) -> None:
        """Track agent reasoning steps."""
        # Track tokens used in agent reasoning
        thought_tokens = len(action.log) // 4 if action.log else 0
        
        await self.tracker.track_usage(
            session_id=self.session_id,
            category=TokenCategory.CONTEXT,
            input_tokens=thought_tokens,
            output_tokens=0,
            metadata={
                "project_id": self.project_id,
                "task_id": self.task_id,
                "action": "reasoning"
            }
        )
    
    async def on_retriever_start(
        self,
        serialized: Dict[str, Any],
        query: str,
        **kwargs: Any
    ) -> None:
        """Track RAG retrieval."""
        query_tokens = len(query) // 4
        
        await self.tracker.track_usage(
            session_id=self.session_id,
            category=TokenCategory.RAG_CONTEXT,
            input_tokens=query_tokens,
            output_tokens=0,
            metadata={
                "project_id": self.project_id,
                "task_id": self.task_id,
                "action": "rag_query"
            }
        )
    
    async def on_retriever_end(
        self,
        documents: List[Any],
        **kwargs: Any
    ) -> None:
        """Track RAG retrieval results."""
        # Estimate tokens in retrieved documents
        doc_tokens = 0
        for doc in documents:
            if hasattr(doc, "page_content"):
                doc_tokens += len(doc.page_content) // 4
        
        await self.tracker.track_usage(
            session_id=self.session_id,
            category=TokenCategory.RAG_CONTEXT,
            input_tokens=0,
            output_tokens=doc_tokens,
            metadata={
                "project_id": self.project_id,
                "task_id": self.task_id,
                "action": "rag_results",
                "doc_count": len(documents)
            }
        )


def create_token_tracking_callback(
    agent_id: str,
    project_id: int,
    task_id: str,
    session_id: Optional[str] = None,
    mcp_tools: List[str] = None
) -> TokenTrackingCallback:
    """
    Factory function to create token tracking callback.
    
    Args:
        agent_id: Agent template ID
        project_id: Project ID
        task_id: Task ID
        session_id: Optional session ID (generated if not provided)
        mcp_tools: List of MCP tools
        
    Returns:
        Configured TokenTrackingCallback instance
    """
    if not session_id:
        session_id = f"{task_id}_{datetime.utcnow().timestamp()}"
    
    return TokenTrackingCallback(
        session_id=session_id,
        agent_id=agent_id,
        project_id=project_id,
        task_id=task_id,
        mcp_tools=mcp_tools
    )