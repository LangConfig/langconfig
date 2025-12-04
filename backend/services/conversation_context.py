# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Conversation Context Service

Handles retrieval and formatting of conversation history from deep agent chat sessions
for injection into workflow execution contexts.
"""

from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
import tiktoken

from models.deep_agent import ChatSession


class ConversationContextService:
    """Service for managing conversation context retrieval and formatting"""

    def __init__(self, db: Union[Session, AsyncSession]):
        self.db = db

    def calculate_session_tokens(self, session: ChatSession) -> int:
        """
        Calculate total token count for a chat session.
        Useful for monitoring context size.
        """
        if not session.messages:
            return 0

        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            total_tokens = 0

            for msg in session.messages:
                if isinstance(msg, dict):
                    content = msg.get('content', '')
                    total_tokens += len(encoding.encode(content)) + 4

            return total_tokens

        except Exception as e:
            print(f"Token calculation failed: {e}")
            # Fallback estimate
            total_chars = sum(len(msg.get('content', '')) for msg in session.messages if isinstance(msg, dict))
            return total_chars // 4

    async def get_context_for_agent(
        self,
        agent_template_id: int,
        current_query: str,
        context_mode: str = "smart",
        window_size: int = 20,
        banked_message_ids: List[str] = None,
        project_id: Optional[int] = None
    ) -> List[BaseMessage]:
        """
        Retrieve and format conversation context for workflow agent.

        Args:
            agent_template_id: ID of the deep agent template
            current_query: Current workflow query (used for semantic search)
            context_mode: "recent", "smart", or "full"
            window_size: Number of recent messages to include
            banked_message_ids: IDs of user-marked important messages

        Returns:
            List of LangChain BaseMessage objects ready for state injection
        """
        if banked_message_ids is None:
            banked_message_ids = []

        # Load chat sessions for this agent
        sessions = await self._load_chat_sessions(agent_template_id)

        if not sessions:
            return []

        # Collect messages based on context mode
        selected_messages: List[Dict] = []

        if context_mode == "recent":
            # Just get recent messages
            selected_messages = await self._get_recent_messages(sessions, window_size)

        elif context_mode == "full":
            # Get all messages from all sessions
            selected_messages = await self._get_all_messages(sessions)

        elif context_mode == "smart":
            # Hybrid: recent + banked + semantic (if history is long)
            recent = await self._get_recent_messages(sessions, window_size)
            banked = await self._get_banked_messages(sessions, banked_message_ids)

            # Count total messages to decide if we need semantic search
            total_message_count = sum(
                len(session.messages) if session.messages else 0
                for session in sessions
            )

            # Combine and deduplicate
            seen_indices = set()
            combined = []

            # Priority 1: Banked messages (user-marked important)
            for msg in banked:
                idx = msg.get('_index')
                if idx not in seen_indices:
                    seen_indices.add(idx)
                    combined.append(msg)

            # Priority 2: Recent messages (continuity)
            for msg in recent:
                idx = msg.get('_index')
                if idx not in seen_indices:
                    seen_indices.add(idx)
                    combined.append(msg)

            # Priority 3: Semantic matches (if history is long)
            if total_message_count > 50 and project_id:
                semantic_matches = await self._semantic_search_messages(
                    sessions=sessions,
                    query=current_query,
                    agent_template_id=agent_template_id,
                    project_id=project_id,
                    limit=10
                )
                # Add semantic matches that aren't already included
                for msg in semantic_matches:
                    idx = msg.get('_index')
                    if idx not in seen_indices:
                        seen_indices.add(idx)
                        combined.append(msg)

            # Sort by timestamp to maintain chronological order
            combined.sort(key=lambda m: m.get('timestamp', ''))
            selected_messages = combined

        # Convert to LangChain messages
        langchain_messages = self._format_as_langchain_messages(selected_messages)

        # Token counting and trimming
        total_tokens = self._count_tokens(langchain_messages)
        max_context_tokens = 32000  # Conservative limit for most models (50% of 128k context)

        # If context is too large, apply trimming
        if total_tokens > max_context_tokens:
            # Try summarization first for very long histories
            if len(selected_messages) > 200:
                summary = await self._generate_summary(selected_messages)
                if summary:
                    # Replace messages with summary + recent messages
                    summary_message = SystemMessage(content=f"## Previous Conversation Summary\n\n{summary}")
                    recent_messages = self._format_as_langchain_messages(selected_messages[-20:])
                    langchain_messages = [summary_message] + recent_messages
                    total_tokens = self._count_tokens(langchain_messages)

            # If still too large, trim to fit
            if total_tokens > max_context_tokens:
                langchain_messages = self._trim_messages(langchain_messages, max_context_tokens)

        return langchain_messages

    async def _load_chat_sessions(
        self,
        agent_template_id: int
    ) -> List[ChatSession]:
        """Load all active chat sessions for the agent template"""
        stmt = select(ChatSession).where(
            and_(
                ChatSession.agent_id == agent_template_id,
                ChatSession.is_active == True
            )
        ).order_by(ChatSession.created_at.desc())

        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        return list(sessions)

    async def _get_recent_messages(
        self,
        sessions: List[ChatSession],
        limit: int
    ) -> List[Dict]:
        """Get most recent N messages across all sessions"""
        all_messages = []

        for session in sessions:
            if not session.messages:
                continue

            messages = session.messages if isinstance(session.messages, list) else []

            for idx, msg in enumerate(messages):
                if isinstance(msg, dict):
                    # Add session and index info for deduplication
                    msg_copy = msg.copy()
                    msg_copy['_session_id'] = session.session_id
                    msg_copy['_index'] = f"{session.session_id}:{idx}"
                    all_messages.append(msg_copy)

        # Sort by timestamp (most recent first)
        all_messages.sort(
            key=lambda m: m.get('timestamp', ''),
            reverse=True
        )

        # Take most recent N
        recent = all_messages[:limit]

        # Reverse to get chronological order (oldest first)
        recent.reverse()

        return recent

    async def _get_all_messages(
        self,
        sessions: List[ChatSession]
    ) -> List[Dict]:
        """Get all messages from all sessions"""
        all_messages = []

        for session in sessions:
            if not session.messages:
                continue

            messages = session.messages if isinstance(session.messages, list) else []

            for idx, msg in enumerate(messages):
                if isinstance(msg, dict):
                    msg_copy = msg.copy()
                    msg_copy['_session_id'] = session.session_id
                    msg_copy['_index'] = f"{session.session_id}:{idx}"
                    all_messages.append(msg_copy)

        # Sort chronologically
        all_messages.sort(key=lambda m: m.get('timestamp', ''))

        return all_messages

    async def _get_banked_messages(
        self,
        sessions: List[ChatSession],
        banked_ids: List[str]
    ) -> List[Dict]:
        """Get user-marked important messages"""
        if not banked_ids:
            return []

        banked_messages = []

        for session in sessions:
            if not session.messages:
                continue

            messages = session.messages if isinstance(session.messages, list) else []

            for idx, msg in enumerate(messages):
                if isinstance(msg, dict):
                    msg_index = f"{session.session_id}:{idx}"

                    # Check if this message is banked
                    if msg.get('banked', False) or msg_index in banked_ids:
                        msg_copy = msg.copy()
                        msg_copy['_session_id'] = session.session_id
                        msg_copy['_index'] = msg_index
                        banked_messages.append(msg_copy)

        # Sort chronologically
        banked_messages.sort(key=lambda m: m.get('timestamp', ''))

        return banked_messages

    def _format_as_langchain_messages(
        self,
        messages: List[Dict]
    ) -> List[BaseMessage]:
        """Convert dict messages to LangChain BaseMessage objects"""
        langchain_messages = []

        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if not content:
                continue

            if role == 'user':
                langchain_messages.append(HumanMessage(content=content))
            elif role == 'assistant' or role == 'ai':
                langchain_messages.append(AIMessage(content=content))
            # Skip system messages or other types for now

        return langchain_messages

    async def _semantic_search_messages(
        self,
        sessions: List[ChatSession],
        query: str,
        agent_template_id: int,
        project_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Use RAG to find relevant historical messages.

        Searches through stored conversation embeddings to find messages
        semantically related to the current query.
        """
        if not project_id:
            # Can't do semantic search without project context
            return []

        try:
            from services.llama_config import get_vector_store

            vector_store = get_vector_store(project_id)

            # Build metadata filter for this agent's conversations
            metadata_filter = {
                "doc_type": "chat_message",
                "agent_id": str(agent_template_id)
            }

            # Perform similarity search
            results = await vector_store.asimilarity_search(
                query=query,
                k=limit,
                filter=metadata_filter
            )

            # Convert Document results back to message dict format
            relevant_messages = []
            for doc in results:
                metadata = doc.metadata
                msg = {
                    "role": metadata.get("role", "user"),
                    "content": doc.page_content,
                    "timestamp": metadata.get("timestamp", ""),
                    "_session_id": metadata.get("session_id", ""),
                    "_index": metadata.get("message_index", ""),
                    "_relevance_score": getattr(doc, "score", None)  # If available
                }
                relevant_messages.append(msg)

            return relevant_messages

        except Exception as e:
            # Log error but don't fail the whole context retrieval
            print(f"Semantic search failed: {e}")
            return []

    async def store_message_in_vector_store(
        self,
        session_id: str,
        agent_template_id: int,
        message_index: int,
        role: str,
        content: str,
        timestamp: str,
        project_id: int
    ) -> bool:
        """
        Store a chat message in the vector store for semantic search.

        Args:
            session_id: Chat session ID
            agent_template_id: Deep agent template ID
            message_index: Index of message in session
            role: "user" or "assistant"
            content: Message content
            timestamp: ISO timestamp
            project_id: Project ID for vector store scoping

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            from services.llama_config import get_vector_store
            from langchain_core.documents import Document
            import uuid

            vector_store = get_vector_store(project_id)

            # Create document with metadata
            doc = Document(
                page_content=content,
                metadata={
                    "doc_type": "chat_message",
                    "message_id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "agent_id": str(agent_template_id),
                    "message_index": f"{session_id}:{message_index}",
                    "role": role,
                    "timestamp": timestamp
                }
            )

            # Store in vector store
            await vector_store.aadd_documents([doc])
            return True

        except Exception as e:
            print(f"Failed to store message in vector store: {e}")
            return False

    def _count_tokens(self, messages: List[BaseMessage]) -> int:
        """
        Count tokens in messages using tiktoken.
        Uses cl100k_base encoding (same as GPT-4/Claude models).
        """
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            total_tokens = 0

            for message in messages:
                # Count tokens in message content
                content = message.content if hasattr(message, 'content') else str(message)
                total_tokens += len(encoding.encode(content))

                # Add overhead for message structure (role, formatting)
                total_tokens += 4  # Approximate overhead per message

            return total_tokens

        except Exception as e:
            print(f"Token counting failed: {e}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            total_chars = sum(len(str(m.content)) for m in messages if hasattr(m, 'content'))
            return total_chars // 4

    def _trim_messages(
        self,
        messages: List[BaseMessage],
        max_tokens: int
    ) -> List[BaseMessage]:
        """
        Trim messages to fit within token budget.
        Keeps most recent messages (FIFO eviction).
        """
        if not messages:
            return []

        # Always keep at least the last message
        if len(messages) == 1:
            return messages

        encoding = tiktoken.get_encoding("cl100k_base")
        trimmed = []
        current_tokens = 0

        # Process messages in reverse (most recent first)
        for message in reversed(messages):
            content = message.content if hasattr(message, 'content') else str(message)
            msg_tokens = len(encoding.encode(content)) + 4

            if current_tokens + msg_tokens <= max_tokens:
                trimmed.insert(0, message)  # Insert at beginning to maintain order
                current_tokens += msg_tokens
            else:
                # Budget exhausted
                break

        # If we trimmed significantly, add a notice
        if len(trimmed) < len(messages) // 2:
            notice = SystemMessage(
                content=f"[Context trimmed: showing {len(trimmed)} of {len(messages)} messages due to token limits]"
            )
            trimmed.insert(0, notice)

        return trimmed

    async def _generate_summary(
        self,
        messages: List[Dict]
    ) -> str:
        """
        Generate AI summary of conversation themes.
        Uses a lightweight model to summarize key points.
        """
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate

            # Use a cheap, fast model for summarization
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

            # Build conversation text
            conversation_text = "\n\n".join([
                f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')[:500]}"
                for msg in messages[:100]  # Only summarize first 100 messages
            ])

            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a conversation summarizer. Create a concise summary of the key themes,
                decisions, and important information from this conversation. Keep it under 200 words.
                Focus on facts, decisions made, and context that would be useful later."""),
                ("human", f"Summarize this conversation:\n\n{conversation_text}")
            ])

            chain = prompt | llm
            result = await chain.ainvoke({})

            summary = result.content if hasattr(result, 'content') else str(result)
            return summary

        except Exception as e:
            print(f"Summarization failed: {e}")
            # Fallback: simple truncation summary
            recent_messages = messages[-10:]
            summary = "Recent conversation topics:\n"
            for msg in recent_messages:
                content = msg.get('content', '')[:100]
                summary += f"- {content}...\n"
            return summary
