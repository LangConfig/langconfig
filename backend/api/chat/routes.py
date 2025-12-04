# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Chat API - DeepAgent Testing Interface

This module provides a complete chat interface for testing DeepAgents before export.

## Architecture

The chat system uses **dual storage** for conversation history:

1. **PostgreSQL JSON Column** (`chat_sessions.messages`)
   - Used for: UI display, conversation context service, session list
   - Format: `[{role, content, timestamp, banked}, ...]`
   - Must use `flag_modified()` when updating

2. **LangGraph Checkpointer** (PostgreSQL checkpoint tables)
   - Used for: Agent runtime memory, automatic compaction
   - Format: Binary-encoded LangChain BaseMessage objects
   - Automatic persistence via thread_id

## Session Lifecycle

1. **Start Session** - User opens chat → Create session, assign thread_id
2. **Active Chat** - Messages flow through both storage systems
3. **Auto-Cleanup** - Session manager removes stale sessions (1 hour TTL)
4. **End Session** - User explicitly ends → Remove from cache, cleanup checkpoints

## Memory Management

- **Agent Caching**: Session manager caches agent instances for performance
- **TTL Cleanup**: Background task removes inactive sessions every 5 minutes
- **Checkpoint Cleanup**: Deletes LangGraph state when session ends
- **Token Limits**: Guardrails config controls automatic summarization/eviction

## Health Monitoring

GET /api/chat/health - Returns session manager stats and validates consistency

## Key Features

- Token-by-token streaming (astream_events)
- Message banking (mark important messages)
- Conversation context for workflows
- Human-in-the-loop (HITL) support
- Automatic resource cleanup
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json

from db.database import get_db
from models.deep_agent import DeepAgentTemplate, ChatSession, DeepAgentConfig, SessionDocument
from models.core import DocumentType, IndexingStatus
from services.deepagent_factory import DeepAgentFactory
from core.workflows.events.emitter import ExecutionEventCallbackHandler
from services.conversation_context import ConversationContextService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# =============================================================================
# Helper Functions
# =============================================================================

def make_json_safe(obj):
    """
    Recursively convert objects to JSON-safe format.
    Filters out non-serializable items like LangGraph Command objects.
    """
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items() if not k.startswith('_')}
    elif isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]
    else:
        # Skip non-serializable objects like Command
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return None


# =============================================================================
# Request/Response Models
# =============================================================================

class StartChatRequest(BaseModel):
    """Request to start a new chat session."""
    agent_id: int
    user_id: Optional[int] = None


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # 'user' or 'assistant'
    content: str


class SendMessageRequest(BaseModel):
    """Request to send a message in a chat session."""
    session_id: str
    message: str


class ChatResponse(BaseModel):
    """Response from the agent."""
    session_id: str
    message: str
    tool_calls: List[Dict[str, Any]] = []
    subagent_activity: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}


class ChatSessionResponse(BaseModel):
    """Response with chat session details."""
    session_id: str
    agent_id: int
    agent_name: str
    is_active: bool
    message_count: int
    created_at: str
    updated_at: str


class ChatHistoryResponse(BaseModel):
    """Response with chat history."""
    session_id: str
    messages: List[ChatMessage]
    metrics: Dict[str, Any]


# =============================================================================
# Session Management
# =============================================================================

from services.chat_session_manager import get_session_manager

# Legacy: Will be removed after migration to session manager
active_agents: Dict[str, Any] = {}


def get_cached_agent(session_id: str) -> Optional[Any]:
    """Get cached agent instance using session manager."""
    manager = get_session_manager()
    agent = manager.get_agent(session_id)
    if agent:
        return agent
    # Fallback to legacy cache
    return active_agents.get(session_id)


def cache_agent(session_id: str, agent_instance: Any):
    """Cache agent instance using session manager."""
    manager = get_session_manager()
    manager.cache_agent(session_id, agent_instance)
    # Also update legacy cache for compatibility
    active_agents[session_id] = agent_instance


# =============================================================================
# Session Lifecycle Endpoints
# =============================================================================


@router.post("/start", response_model=ChatSessionResponse)
async def start_chat_session(
    request: StartChatRequest,
    db: Session = Depends(get_db)
):
    """
    Start a new chat session with a DeepAgent.

    Creates a session record in PostgreSQL and assigns a unique thread_id
    for LangGraph checkpoint persistence.

    Returns:
        ChatSessionResponse with session details
    """
    try:
        # Get agent
        agent = db.query(DeepAgentTemplate).filter(
            DeepAgentTemplate.id == request.agent_id
        ).first()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Create session ID
        session_id = str(uuid.uuid4())

        # Create session record
        session = ChatSession(
            session_id=session_id,
            agent_id=agent.id,
            user_id=request.user_id,
            messages=[],
            metrics={
                "total_tokens": 0,
                "tool_calls": 0,
                "subagent_spawns": 0
            },
            tool_calls=[],
            subagent_spawns=[],
            context_operations=[],
            is_active=True
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        logger.info(f"Started chat session {session_id} for agent {agent.name}")

        return ChatSessionResponse(
            session_id=session.session_id,
            agent_id=agent.id,
            agent_name=agent.name,
            is_active=session.is_active,
            message_count=len(session.messages),
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat()
        )

    except Exception as e:
        logger.error(f"Error starting chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Message Endpoints (Synchronous & Streaming)
# =============================================================================


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: SendMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message and receive a complete response (non-streaming).

    Storage Flow:
    1. Append user message to session.messages (PostgreSQL JSON)
    2. Invoke agent with thread_id (LangGraph loads previous messages from checkpointer)
    3. Append assistant response to session.messages
    4. Both storages are updated atomically

    Returns:
        ChatResponse with full message content
    """
    try:
        # Get session
        session = db.query(ChatSession).filter(
            ChatSession.session_id == request.session_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not session.is_active:
            raise HTTPException(status_code=400, detail="Session is not active")

        # Get agent
        agent = db.query(DeepAgentTemplate).filter(
            DeepAgentTemplate.id == session.agent_id
        ).first()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Add user message to history
        from datetime import datetime
        from sqlalchemy.orm.attributes import flag_modified
        user_message_timestamp = datetime.utcnow().isoformat()
        user_message_index = len(session.messages)
        session.messages.append({
            "role": "user",
            "content": request.message,
            "timestamp": user_message_timestamp,
            "banked": False
        })
        flag_modified(session, "messages")

        # Get or create agent instance
        agent_instance = get_cached_agent(request.session_id)

        if not agent_instance:
            # Create agent instance
            config = DeepAgentConfig(**agent.config)
            agent_instance, tools, callbacks = await DeepAgentFactory.create_deep_agent(
                config=config,
                project_id=0,  # Not tied to a project
                task_id=0,  # Not tied to a task
                context="",
                mcp_manager=None,  # Would be injected in production
                vector_store=None
            )
            cache_agent(request.session_id, agent_instance)

        # Create new user message (checkpointer will load previous messages automatically)
        from langchain_core.messages import HumanMessage
        new_message = HumanMessage(content=request.message)

        # Invoke agent with thread_id for conversation persistence
        # The checkpointer automatically loads and saves conversation history
        result = agent_instance.invoke(
            {"messages": [new_message]},
            config={"configurable": {"thread_id": session.session_id}}
        )

        # Extract response
        if hasattr(result, "messages") and result.messages:
            response_text = result.messages[-1].content
        elif isinstance(result, dict) and "messages" in result:
            response_text = result["messages"][-1].content
        else:
            response_text = str(result)

        # Ensure response_text is a string (handle cases where content might be a list of blocks)
        if isinstance(response_text, list):
            # Extract text from content blocks: [{'text': '...', 'type': 'text'}, ...]
            response_text = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in response_text
            )
        elif not isinstance(response_text, str):
            response_text = str(response_text)

        # Add assistant message to history
        assistant_message_timestamp = datetime.utcnow().isoformat()
        assistant_message_index = len(session.messages)
        session.messages.append({
            "role": "assistant",
            "content": response_text,
            "timestamp": assistant_message_timestamp,
            "banked": False
        })
        flag_modified(session, "messages")

        # Update metrics
        session.metrics["total_tokens"] = session.metrics.get("total_tokens", 0) + len(request.message) + len(response_text)
        flag_modified(session, "metrics")

        # Extract tool calls and subagent activity from result
        tool_calls = []
        subagent_activity = []

        # This would be populated from actual agent execution
        # For now, return empty lists

        # Save session
        db.commit()
        db.refresh(session)

        # Store messages in vector store for semantic search (if project_id available)
        # Note: Chat sessions currently don't have project association, but we'll add it later
        project_id_for_vectorstore = getattr(session, 'project_id', None) or agent.project_id if hasattr(agent, 'project_id') else None
        if project_id_for_vectorstore:
            try:
                from backend.services.conversation_context import ConversationContextService
                from sqlalchemy.ext.asyncio import AsyncSession
                async_db = AsyncSession(bind=db.get_bind())
                context_service = ConversationContextService(async_db)

                # Store user message
                await context_service.store_message_in_vector_store(
                    session_id=session.session_id,
                    agent_template_id=session.agent_id,
                    message_index=user_message_index,
                    role="user",
                    content=request.message,
                    timestamp=user_message_timestamp,
                    project_id=project_id_for_vectorstore
                )

                # Store assistant message
                await context_service.store_message_in_vector_store(
                    session_id=session.session_id,
                    agent_template_id=session.agent_id,
                    message_index=assistant_message_index,
                    role="assistant",
                    content=response_text,
                    timestamp=assistant_message_timestamp,
                    project_id=project_id_for_vectorstore
                )
            except Exception as e:
                # Don't fail the whole request if vector storage fails
                print(f"Failed to store messages in vector store: {e}")

        logger.info(f"Processed message in session {request.session_id}")

        return ChatResponse(
            session_id=session.session_id,
            message=response_text,
            tool_calls=tool_calls,
            subagent_activity=subagent_activity,
            metrics=session.metrics
        )

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/stream")
async def send_message_stream(
    request: SendMessageRequest,
    db: Session = Depends(get_db)
):
    """Send a message and stream the response."""
    try:
        # Get session
        session = db.query(ChatSession).filter(
            ChatSession.session_id == request.session_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not session.is_active:
            raise HTTPException(status_code=400, detail="Session is not active")

        # Get agent
        agent = db.query(DeepAgentTemplate).filter(
            DeepAgentTemplate.id == session.agent_id
        ).first()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Store session_id and agent config before entering generator
        # to avoid detached session issues
        session_id = session.session_id
        agent_config = agent.config.copy() if agent.config else {}
        agent_project_id = getattr(agent, 'project_id', None)

        async def generate_stream():
            """Generate streaming response."""
            full_response = ""
            all_context = ""
            rag_tokens_used = 0

            try:
                # Re-query session inside generator to avoid detached object issues
                from sqlalchemy.orm.attributes import flag_modified
                fresh_session = db.query(ChatSession).filter(
                    ChatSession.session_id == session_id
                ).first()

                if not fresh_session:
                    logger.error(f"Session {session_id} not found in generator")
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Session not found'})}\n\n"
                    return

                logger.info(f"Before adding user message: total_messages={len(fresh_session.messages)}")
                fresh_session.messages.append({
                    "role": "user",
                    "content": request.message
                })
                flag_modified(fresh_session, "messages")
                db.commit()  # Commit user message immediately
                db.refresh(fresh_session)  # Refresh to confirm save
                logger.info(f"✓ User message saved to DB: session={session_id}, total_messages={len(fresh_session.messages)}")

                project_id = agent_project_id

                if project_id:
                    from services.context_retrieval import context_retriever
                    from services.token_counter import get_token_counter
                    token_counter = get_token_counter()

                    try:
                        project_context_package = await context_retriever.retrieve_context(
                            project_id=project_id,
                            task_description=request.message,
                            similarity_top_k=3,
                            use_hyde=False
                        )
                        project_chunks = project_context_package.get('components', {}).get('code_chunks', [])
                        project_context = "\n\n".join([chunk.get('content', '') for chunk in project_chunks])
                    except Exception as e:
                        logger.warning(f"Failed to retrieve project context: {e}")
                        project_context = ""

                    session_context = ""
                    session_docs = db.query(SessionDocument).filter(
                        SessionDocument.session_id == request.session_id,
                        SessionDocument.indexing_status == IndexingStatus.READY
                    ).all()

                    if session_docs:
                        try:
                            logger.info(f"Found {len(session_docs)} indexed session documents")
                            session_context_package = await context_retriever.retrieve_context(
                                project_id=project_id,
                                task_description=request.message,
                                similarity_top_k=2,
                                session_id=request.session_id,
                                use_hyde=False
                            )
                            session_chunks = session_context_package.get('components', {}).get('code_chunks', [])
                            session_context = "\n\n".join([chunk.get('content', '') for chunk in session_chunks])
                        except Exception as e:
                            logger.warning(f"Failed to retrieve session context: {e}")
                            session_context = ""

                    if project_context and session_context:
                        all_context = f"# Project Documents:\n{project_context}\n\n# Session Documents:\n{session_context}"
                    elif project_context:
                        all_context = f"# Project Documents:\n{project_context}"
                    elif session_context:
                        all_context = f"# Session Documents:\n{session_context}"

                    if all_context:
                        rag_tokens_used = token_counter.count_tokens(all_context)
                        logger.info(f"Retrieved RAG context: {rag_tokens_used} tokens")

                # Get or create agent instance
                agent_instance = get_cached_agent(request.session_id)

                if not agent_instance:
                    config = DeepAgentConfig(**agent_config)
                    agent_instance, tools, callbacks = await DeepAgentFactory.create_deep_agent(
                        config=config,
                        project_id=project_id or 0,
                        task_id=0,
                        context=all_context,  # Inject RAG context
                        mcp_manager=None,
                        vector_store=None
                    )
                    cache_agent(request.session_id, agent_instance)

                # Create event handler for tracking tool calls and subagent activity
                event_handler = ExecutionEventCallbackHandler(
                    project_id=project_id or 0,
                    task_id=0,
                    workflow_id=None,  # No workflow for chat sessions
                    enable_sanitization=True,
                    save_to_db=False  # Don't persist to DB for chat sessions
                )

                # Create new user message (checkpointer loads previous messages)
                from langchain_core.messages import HumanMessage
                new_message = HumanMessage(content=request.message)

                # Use astream_events for token-by-token streaming
                async for event in agent_instance.astream_events(
                    {"messages": [new_message]},
                    config={
                        "configurable": {"thread_id": session_id},
                        "callbacks": [event_handler]
                    },
                    version="v2"
                ):
                    kind = event.get("event")

                    # Stream tool call events
                    if kind == "on_tool_start":
                        tool_data = event.get("data", {})
                        tool_name = tool_data.get("input", {}).get("name") if isinstance(tool_data.get("input"), dict) else event.get("name", "unknown")
                        # Filter out non-serializable objects
                        safe_data = make_json_safe(tool_data)
                        yield f"data: {json.dumps({'type': 'tool_start', 'tool_name': tool_name, 'data': safe_data})}\n\n"

                    elif kind == "on_tool_end":
                        tool_data = event.get("data", {})
                        tool_name = event.get("name", "unknown")
                        # Filter out non-serializable objects
                        safe_data = make_json_safe(tool_data)
                        yield f"data: {json.dumps({'type': 'tool_end', 'tool_name': tool_name, 'data': safe_data})}\n\n"

                    # Stream LLM tokens as they're generated
                    elif kind == "on_chat_model_stream":
                        chunk_content = event.get("data", {}).get("chunk")
                        if chunk_content and hasattr(chunk_content, "content"):
                            token = chunk_content.content

                            # Ensure token is a string (handle cases where content might be a list of blocks)
                            if isinstance(token, list):
                                # Skip empty lists
                                if not token:
                                    continue
                                # Extract text from content blocks: [{'text': '...', 'type': 'text'}, ...]
                                parts = [
                                    block.get("text", "") if isinstance(block, dict) else str(block)
                                    for block in token
                                ]
                                # Join parts directly - streaming sends complete tokens
                                token = "".join(parts)
                            elif token is None:
                                continue
                            elif not isinstance(token, str):
                                token = str(token)

                            if token:
                                full_response += token
                                yield f"data: {json.dumps({'type': 'chunk', 'content': token})}\n\n"

                # Send completion event
                yield f"data: {json.dumps({'type': 'complete', 'content': full_response})}\n\n"

            except Exception as e:
                logger.error(f"Error in stream: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            finally:
                # Always save assistant message, even if there was an error
                if full_response:
                    try:
                        # Re-query session to ensure we have a fresh, attached object
                        final_session = db.query(ChatSession).filter(
                            ChatSession.session_id == session_id
                        ).first()

                        if final_session:
                            logger.info(f"Before adding assistant message: total_messages={len(final_session.messages)}")

                            final_session.messages.append({
                                "role": "assistant",
                                "content": full_response
                            })
                            flag_modified(final_session, "messages")

                            # Update metrics with RAG token tracking
                            rough_tokens = len(request.message) + len(full_response)
                            final_session.metrics["total_tokens"] = final_session.metrics.get("total_tokens", 0) + rough_tokens + rag_tokens_used
                            final_session.metrics["rag_context_tokens"] = final_session.metrics.get("rag_context_tokens", 0) + rag_tokens_used
                            flag_modified(final_session, "metrics")

                            # Update cost tracking columns (if they exist)
                            try:
                                final_session.rag_context_tokens = final_session.metrics.get("rag_context_tokens", 0)
                            except AttributeError:
                                pass  # Column doesn't exist yet

                            db.commit()
                            db.refresh(final_session)  # Refresh to confirm save
                            logger.info(f"✓ Assistant message saved to DB: session={session_id}, total_messages={len(final_session.messages)}, rag_tokens={rag_tokens_used}")
                        else:
                            logger.error(f"❌ Session {session_id} not found when saving assistant message")
                    except Exception as save_error:
                        logger.error(f"❌ Failed to save assistant message to DB: {save_error}", exc_info=True)
                        db.rollback()
                else:
                    logger.warning(f"⚠ No response generated for session={session_id}")

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Session Data & Metrics Endpoints
# =============================================================================


@router.get("/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the full chat history for a session.

    Loads from PostgreSQL session.messages (not from checkpointer).
    """
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return ChatHistoryResponse(
        session_id=session.session_id,
        messages=[ChatMessage(**msg) for msg in session.messages],
        metrics=session.metrics
    )


@router.get("/{session_id}/metrics")
async def get_session_metrics(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed metrics for a chat session with cost calculations."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    total_tokens = session.metrics.get("total_tokens", 0)
    rag_tokens = session.metrics.get("rag_context_tokens", 0)

    agent = db.query(DeepAgentTemplate).filter_by(id=session.agent_id).first()
    model = "claude-sonnet-4-5-20250929"
    if agent and agent.config:
        model = agent.config.get("model", "claude-sonnet-4-5-20250929")

    MODEL_PRICING = {
        "claude-sonnet-4-5-20250929": 9.0,
        "claude-sonnet-4": 9.0,
        "claude-opus-4-20250514": 45.0,
        "claude-opus-4": 45.0,
        "claude-3-5-sonnet-20241022": 6.0,
        "claude-3-5-sonnet-20240620": 6.0,
        "claude-3-5-haiku-20241022": 1.5,
        "claude-3-opus-20240229": 37.5,
        "claude-3-sonnet-20240229": 6.0,
        "claude-3-haiku-20240307": 0.75,
        "gpt-4o-2024-11-20": 5.0,
        "gpt-4o-2024-08-06": 5.0,
        "gpt-4o-2024-05-13": 10.0,
        "gpt-4o": 7.5,
        "gpt-4o-mini-2024-07-18": 0.3,
        "gpt-4o-mini": 0.3,
        "gpt-4-turbo-2024-04-09": 15.0,
        "gpt-4-turbo": 15.0,
        "gpt-4-0125-preview": 30.0,
        "gpt-4": 30.0,
        "gpt-3.5-turbo": 1.5,
        "gemini-2.0-flash-exp": 0.0,
        "gemini-exp-1206": 0.0,
        "gemini-2.0-flash-thinking-exp-1219": 0.0,
        "gemini-2.0-flash-thinking-exp": 0.0,
        "gemini-1.5-pro-002": 2.5,
        "gemini-1.5-pro": 2.5,
        "gemini-1.5-flash-002": 0.15,
        "gemini-1.5-flash": 0.15,
        "deepseek-chat": 0.55,
        "deepseek-reasoner": 2.19,
    }

    cost_per_1m = MODEL_PRICING.get(model, 9.0)
    estimated_cost = (total_tokens / 1_000_000) * cost_per_1m

    # Calculate current context size
    context_service = ConversationContextService(db)
    context_tokens = context_service.calculate_session_tokens(session)

    # Update cost tracking if column exists (handle missing column gracefully)
    try:
        current_cost = getattr(session, 'total_cost_usd', 0.0)
        if abs(current_cost - estimated_cost) > 0.0001:
            session.total_cost_usd = estimated_cost
            db.commit()
    except AttributeError:
        # Column doesn't exist yet - migration not run
        pass

    return {
        "session_id": session.session_id,
        "metrics": {
            **session.metrics,
            "total_cost_usd": round(estimated_cost, 4),
            "rag_context_tokens": rag_tokens,
            "context_tokens": context_tokens,
            "cost_per_token": round(estimated_cost / max(total_tokens, 1), 8) if total_tokens > 0 else 0,
            "model_used": model
        },
        "tool_calls": session.tool_calls,
        "subagent_spawns": session.subagent_spawns,
        "context_operations": session.context_operations,
        "message_count": len(session.messages),
        "is_active": session.is_active,
        "duration_seconds": (session.updated_at - session.created_at).total_seconds()
    }


@router.post("/{session_id}/end")
async def end_chat_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """End a chat session and cleanup resources."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Mark as inactive
    session.is_active = False
    import datetime
    session.ended_at = datetime.datetime.utcnow()
    db.commit()

    # Cleanup agent instance from cache
    manager = get_session_manager()
    removed = manager.remove_session(session_id)

    # Also remove from legacy cache
    if session_id in active_agents:
        del active_agents[session_id]

    # Cleanup LangGraph checkpoints for this thread
    cleanup_success = False
    try:
        from core.workflows.checkpointing.utils import delete_thread_checkpoints
        await delete_thread_checkpoints(thread_id=session_id)
        cleanup_success = True
        logger.info(f"Cleaned up checkpoints for session {session_id}")
    except Exception as e:
        logger.warning(f"Failed to cleanup checkpoints for session {session_id}: {e}")

    logger.info(
        f"Ended chat session {session_id} "
        f"(agent_removed={removed}, checkpoints_cleaned={cleanup_success})"
    )

    return {
        "status": "success",
        "message": "Session ended",
        "agent_removed": removed,
        "checkpoints_cleaned": cleanup_success
    }


@router.get("/sessions")
async def list_chat_sessions(
    agent_id: Optional[int] = None,
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """List all chat sessions."""
    query = db.query(ChatSession).join(
        DeepAgentTemplate,
        ChatSession.agent_id == DeepAgentTemplate.id
    )

    if agent_id:
        query = query.filter(ChatSession.agent_id == agent_id)

    if active_only:
        query = query.filter(ChatSession.is_active == True)

    sessions = query.order_by(ChatSession.created_at.desc()).all()

    result = []
    for session in sessions:
        # Get agent safely (might have been deleted)
        agent = db.query(DeepAgentTemplate).filter(
            DeepAgentTemplate.id == session.agent_id
        ).first()

        # Get last message preview
        last_message_preview = None
        if session.messages and len(session.messages) > 0:
            last_msg = session.messages[-1]
            content = last_msg.get("content", "")
            # Truncate to 60 chars for preview
            last_message_preview = content[:60] + "..." if len(content) > 60 else content

        result.append({
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "agent_name": agent.name if agent else "Unknown Agent",
            "is_active": session.is_active,
            "message_count": len(session.messages),
            "last_message_preview": last_message_preview,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat()
        })

    return result


@router.get("/health")
async def get_chat_health(db: Session = Depends(get_db)):
    """
    Get health status of the chat system.

    Returns session manager statistics and validates message consistency.
    """
    manager = get_session_manager()
    stats = manager.get_stats()

    # Validate message consistency
    active_sessions = db.query(ChatSession).filter(
        ChatSession.is_active == True
    ).all()

    inconsistencies = []
    for session in active_sessions:
        db_message_count = len(session.messages) if session.messages else 0

        # Check if session is cached
        cached_agent = manager.get_agent(session.session_id)
        is_cached = cached_agent is not None

        # Basic validation
        if db_message_count == 0 and is_cached:
            inconsistencies.append({
                "session_id": session.session_id,
                "issue": "Session has cached agent but no messages in database",
                "db_messages": db_message_count,
                "is_cached": is_cached
            })

    return {
        "status": "healthy" if len(inconsistencies) == 0 else "warning",
        "session_manager": stats,
        "active_db_sessions": len(active_sessions),
        "inconsistencies": inconsistencies,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/{session_id}/recover")
async def recover_messages_from_checkpoint(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Recover messages from LangGraph checkpointer.

    If messages were lost from the database but still exist in the
    LangGraph checkpoint storage, this endpoint can retrieve and restore them.
    """
    try:
        # Check if session exists
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Query checkpoint table for this thread_id
        from sqlalchemy import text
        checkpoint_query = text("""
            SELECT checkpoint_id, checkpoint, metadata, created_at
            FROM checkpoints
            WHERE thread_id = :thread_id
            ORDER BY created_at DESC
            LIMIT 1
        """)

        result = db.execute(checkpoint_query, {"thread_id": session_id})
        checkpoint_row = result.fetchone()

        if not checkpoint_row:
            return {
                "session_id": session_id,
                "recovered": False,
                "message": "No checkpoint data found for this session",
                "db_messages": len(session.messages) if session.messages else 0
            }

        # Decode checkpoint data (it's stored as binary/pickle)
        import pickle
        try:
            checkpoint_data = pickle.loads(checkpoint_row.checkpoint)

            # Extract messages from checkpoint
            recovered_messages = []
            if 'channel_values' in checkpoint_data and 'messages' in checkpoint_data['channel_values']:
                from langchain_core.messages import BaseMessage
                for msg in checkpoint_data['channel_values']['messages']:
                    if isinstance(msg, BaseMessage):
                        recovered_messages.append({
                            "role": "assistant" if msg.type == "ai" else "user" if msg.type == "human" else msg.type,
                            "content": msg.content,
                            "timestamp": getattr(msg, 'id', None) or datetime.utcnow().isoformat()
                        })

            # Compare with DB messages
            db_message_count = len(session.messages) if session.messages else 0
            checkpoint_message_count = len(recovered_messages)

            return {
                "session_id": session_id,
                "recovered": True,
                "db_messages": db_message_count,
                "checkpoint_messages": checkpoint_message_count,
                "missing_messages": checkpoint_message_count - db_message_count,
                "recovered_data": recovered_messages,
                "checkpoint_id": checkpoint_row.checkpoint_id,
                "created_at": checkpoint_row.created_at.isoformat() if checkpoint_row.created_at else None
            }

        except Exception as decode_error:
            logger.error(f"Failed to decode checkpoint data: {decode_error}")
            return {
                "session_id": session_id,
                "recovered": False,
                "message": f"Found checkpoint but failed to decode: {str(decode_error)}",
                "db_messages": len(session.messages) if session.messages else 0
            }

    except Exception as e:
        logger.error(f"Error recovering messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/recover/restore")
async def restore_messages_from_checkpoint(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Restore messages from LangGraph checkpointer to database.

    This will overwrite the current messages in the database with
    the messages from the checkpoint.
    """
    try:
        # First recover the messages
        recovery_data = await recover_messages_from_checkpoint(session_id, db)

        if not recovery_data.get("recovered"):
            raise HTTPException(status_code=404, detail=recovery_data.get("message", "No checkpoint data found"))

        # Get session
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Restore messages
        from sqlalchemy.orm.attributes import flag_modified
        session.messages = recovery_data["recovered_data"]
        flag_modified(session, "messages")
        db.commit()

        logger.info(f"✓ Restored {len(recovery_data['recovered_data'])} messages for session {session_id}")

        return {
            "session_id": session_id,
            "restored": True,
            "message_count": len(recovery_data["recovered_data"]),
            "messages": recovery_data["recovered_data"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/approve")
async def approve_hitl(
    session_id: str,
    approval_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Handle HITL (Human-in-the-Loop) approval for sensitive operations."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # This would integrate with LangGraph's interrupt/resume mechanism
    # For now, just log the approval

    logger.info(f"HITL approval for session {session_id}: {approval_data}")

    return {
        "status": "approved",
        "session_id": session_id,
        "approval_data": approval_data
    }


# =============================================================================
# Message Banking Endpoints (for Context Management)
# =============================================================================


@router.post("/{session_id}/messages/{message_index}/bank")
async def bank_message(
    session_id: str,
    message_index: int,
    db: Session = Depends(get_db)
):
    """
    Mark a message as 'banked' (important for future context).

    Banked messages are prioritized for inclusion when loading conversation
    context into workflows, even if they're old.
    """
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.messages or message_index >= len(session.messages):
        raise HTTPException(status_code=404, detail="Message not found")

    # Mark message as banked
    from sqlalchemy.orm.attributes import flag_modified
    session.messages[message_index]["banked"] = True
    flag_modified(session, "messages")
    db.commit()

    logger.info(f"Banked message {message_index} in session {session_id}")

    return {
        "status": "success",
        "message": "Message banked successfully",
        "session_id": session_id,
        "message_index": message_index
    }


@router.delete("/{session_id}/messages/{message_index}/bank")
async def unbank_message(
    session_id: str,
    message_index: int,
    db: Session = Depends(get_db)
):
    """Unmark a banked message."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.messages or message_index >= len(session.messages):
        raise HTTPException(status_code=404, detail="Message not found")

    # Unmark message
    from sqlalchemy.orm.attributes import flag_modified
    session.messages[message_index]["banked"] = False
    flag_modified(session, "messages")
    db.commit()

    logger.info(f"Unbanked message {message_index} in session {session_id}")

    return {
        "status": "success",
        "message": "Message unbanked successfully",
        "session_id": session_id,
        "message_index": message_index
    }


# =============================================================================
# Context Preview Endpoint
# =============================================================================

class ContextPreviewResponse(BaseModel):
    messages: List[Dict[str, Any]]
    total_count: int
    token_count: int
    strategy_used: str
    breakdown: Dict[str, int]  # banked, recent, semantic counts


@router.get("/agents/{agent_template_id}/context-preview")
async def preview_context(
    agent_template_id: int,
    query: str,
    context_mode: str = "smart",
    window_size: int = 20,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Preview what context would be injected for a given query.

    This helps users understand what conversation history will be loaded
    when they run a workflow with this agent.
    """
    try:
        from backend.services.conversation_context import ConversationContextService
        from sqlalchemy.ext.asyncio import AsyncSession

        # Convert to async session
        async_db = AsyncSession(bind=db.get_bind())
        context_service = ConversationContextService(async_db)

        # Get context
        messages = await context_service.get_context_for_agent(
            agent_template_id=agent_template_id,
            current_query=query,
            context_mode=context_mode,
            window_size=window_size,
            banked_message_ids=[],
            project_id=project_id
        )

        # Convert messages to dict format for response
        message_dicts = []
        for msg in messages:
            message_dicts.append({
                "role": "user" if msg.__class__.__name__ == "HumanMessage" else "assistant",
                "content": msg.content,
                "type": msg.__class__.__name__
            })

        # Estimate token count (rough estimate: ~4 chars per token)
        total_text = "".join(msg["content"] for msg in message_dicts)
        estimated_tokens = len(total_text) // 4

        # Breakdown by source (simplified for now)
        breakdown = {
            "total": len(message_dicts),
            "banked": 0,  # Would be counted if we tracked sources
            "recent": min(len(message_dicts), window_size),
            "semantic": max(0, len(message_dicts) - window_size)
        }

        return ContextPreviewResponse(
            messages=message_dicts,
            total_count=len(message_dicts),
            token_count=estimated_tokens,
            strategy_used=context_mode,
            breakdown=breakdown
        )

    except Exception as e:
        logger.error(f"Failed to preview context: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to preview context: {str(e)}")


# =============================================================================
# Session Document Management
# =============================================================================

class SessionDocumentResponse(BaseModel):
    """Response model for session document"""
    id: int
    session_id: str
    filename: str
    original_filename: str
    file_size: int
    mime_type: Optional[str]
    document_type: str
    indexing_status: str
    uploaded_at: datetime
    message_index: Optional[int]
    indexed_chunks_count: Optional[int]

    class Config:
        from_attributes = True


async def index_session_document_background(document_id: int, agent_id: int):
    """
    Background task to index a session document with embeddings.
    Similar to index_document_background but session-scoped.
    """
    from db.database import SessionLocal
    from services.context_document_indexer import context_document_indexer

    db = SessionLocal()
    try:
        doc = db.query(SessionDocument).filter(SessionDocument.id == document_id).first()
        if not doc:
            logger.error(f"Session document {document_id} not found for indexing")
            return

        if not doc.file_path:
            logger.error(f"Session document {document_id} has no file_path")
            doc.indexing_status = IndexingStatus.FAILED
            db.commit()
            return

        # Update status to indexing
        doc.indexing_status = IndexingStatus.INDEXING
        file_path = doc.file_path
        session_id = doc.session_id
        db.commit()
        db.close()

        # Get agent and project info for metadata
        db = SessionLocal()
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not session:
            logger.error(f"Chat session {session_id} not found")
            return

        agent = db.query(DeepAgentTemplate).filter(DeepAgentTemplate.id == agent_id).first()
        if not agent:
            logger.error(f"Agent {agent_id} not found")
            return

        project_id = agent.project_id if hasattr(agent, 'project_id') else None
        db.close()

        # Index the document with session-specific metadata
        result = await context_document_indexer.index_document(
            document_id=document_id,
            file_path=file_path,
            metadata={
                "session_id": session_id,
                "agent_id": str(agent_id),
                "doc_type": "session_document"
            }
        )

        # Update status to ready
        db = SessionLocal()
        doc = db.query(SessionDocument).filter(SessionDocument.id == document_id).first()
        if doc:
            doc.indexing_status = IndexingStatus.READY
            doc.indexed_at = datetime.utcnow()
            doc.indexed_chunks_count = result.get("embeddings_stored", 0)
            db.commit()
        db.close()

        logger.info(f"Session document {document_id} indexed successfully")

    except Exception as e:
        logger.error(f"Failed to index session document {document_id}: {e}", exc_info=True)
        # Create fresh session for error handling
        try:
            db.close()
        except:
            pass

        db = SessionLocal()
        try:
            doc = db.query(SessionDocument).filter(SessionDocument.id == document_id).first()
            if doc:
                doc.indexing_status = IndexingStatus.FAILED
                db.commit()
        finally:
            db.close()


@router.post("/{session_id}/upload", response_model=SessionDocumentResponse)
async def upload_file_to_session(
    session_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Upload a file to a chat session for agent context.

    Files are indexed for semantic search and available to the agent
    in this session only (session-scoped RAG).
    """
    from services.file_storage import file_storage

    # Verify session exists
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Read file
    content = await file.read()
    file_size = len(content)

    # Save file to disk (session-scoped storage)
    file_path = file_storage.save_file(f"chat_sessions/{session_id}", file.filename, content)

    # Detect document type from file extension
    file_ext = file.filename.split('.')[-1].lower()
    doc_type_map = {
        'txt': DocumentType.TEXT,
        'md': DocumentType.MARKDOWN,
        'pdf': DocumentType.PDF,
        'json': DocumentType.JSON,
        'py': DocumentType.CODE,
        'js': DocumentType.CODE,
        'ts': DocumentType.CODE,
        'tsx': DocumentType.CODE,
        'jsx': DocumentType.CODE,
    }
    document_type = doc_type_map.get(file_ext, DocumentType.TEXT)

    # Create SessionDocument record
    doc = SessionDocument(
        session_id=session_id,
        filename=file.filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        document_type=document_type,
        indexing_status=IndexingStatus.NOT_INDEXED,
        message_index=len(session.messages) if session.messages else 0
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Queue background indexing
    background_tasks.add_task(index_session_document_background, doc.id, session.agent_id)

    return SessionDocumentResponse(
        id=doc.id,
        session_id=doc.session_id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        document_type=doc.document_type.value,
        indexing_status=doc.indexing_status.value,
        uploaded_at=doc.uploaded_at,
        message_index=doc.message_index,
        indexed_chunks_count=doc.indexed_chunks_count
    )


@router.get("/{session_id}/documents", response_model=List[SessionDocumentResponse])
async def list_session_documents(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get all documents uploaded to this chat session."""
    # Verify session exists
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    docs = db.query(SessionDocument).filter(
        SessionDocument.session_id == session_id
    ).order_by(SessionDocument.uploaded_at.desc()).all()

    return [
        SessionDocumentResponse(
            id=doc.id,
            session_id=doc.session_id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_size=doc.file_size,
            mime_type=doc.mime_type,
            document_type=doc.document_type.value,
            indexing_status=doc.indexing_status.value,
            uploaded_at=doc.uploaded_at,
            message_index=doc.message_index,
            indexed_chunks_count=doc.indexed_chunks_count
        )
        for doc in docs
    ]


@router.delete("/{session_id}/documents/{document_id}", status_code=204)
async def delete_session_document(
    session_id: str,
    document_id: int,
    db: Session = Depends(get_db)
):
    """Delete a document from the session."""
    from services.file_storage import file_storage

    doc = db.query(SessionDocument).filter(
        SessionDocument.id == document_id,
        SessionDocument.session_id == session_id
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete file from disk
    if doc.file_path:
        try:
            file_storage.delete_file(doc.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file {doc.file_path}: {e}")

    # TODO: Delete vector embeddings from vector store
    # This would require querying the vector store with session_id and document_id metadata

    db.delete(doc)
    db.commit()

    return None
