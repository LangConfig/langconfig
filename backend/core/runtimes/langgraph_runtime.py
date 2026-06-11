# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""LangGraph implementation of the AgentRuntime protocol.

This module RELOCATES (verbatim where possible) the chat streaming logic that
previously lived inline in ``api/chat/routes.py::send_message_stream``:

- agent acquisition (session-manager cache + DeepAgentFactory build)
- ExecutionEventCallbackHandler creation
- the ``astream_events(version="v2")`` loop and its
  ``normalize_stream_event`` handling, including token flattening of
  list/str chunk content and tool-artifact flushing

Each SSE payload the route used to yield is now an equivalent
:class:`RuntimeEvent`; the route performs a dumb RuntimeEvent -> SSE mapping
so the wire output is unchanged. Guarded by
``tests/test_runtime_sse_contract.py`` (golden SSE fixture recorded before
the refactor).
"""

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from models.deep_agent import DeepAgentConfig
from services.chat_session_manager import get_session_manager
from services.deepagent_factory import DeepAgentFactory
from core.runtimes.base import (
    AgentRuntime,
    RuntimeCapabilities,
    RuntimeEvent,
    RuntimeSessionRef,
    has_multimodal_blocks,
    make_json_safe,
)
from core.streaming.adapters import normalize_stream_event
from core.workflows.events.emitter import ExecutionEventCallbackHandler

logger = logging.getLogger(__name__)


# =============================================================================
# Agent instance cache (relocated from api/chat/routes.py)
# =============================================================================

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
# Runtime implementation
# =============================================================================

class LangGraphRuntime(AgentRuntime):
    """Executes chat agents via LangGraph/DeepAgents (the default runtime)."""

    name = "langgraph"
    capabilities = RuntimeCapabilities(
        streaming=True,
        hitl=True,
        custom_tools=True,
        checkpoint_resume=True,
    )

    async def prepare_template(self, template_row: Any, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the config against DeepAgentConfig and return it as a dict."""
        validated = DeepAgentConfig(**config)
        return validated.model_dump(exclude_none=True) if hasattr(validated, "model_dump") else dict(config)

    async def create_session(
        self,
        config: Dict[str, Any],
        session_id: str,
        context: str = "",
        project_id: Optional[int] = None,
    ) -> RuntimeSessionRef:
        """Get or build the agent instance for this session (cache-first).

        Relocated from the route: when no cached instance exists, build one
        via DeepAgentFactory with RAG context injected, then cache it.
        """
        agent_instance = get_cached_agent(session_id)

        if not agent_instance:
            agent_config = DeepAgentConfig(**config) if isinstance(config, dict) else config
            agent_instance, tools, callbacks = await DeepAgentFactory.create_deep_agent(
                config=agent_config,
                project_id=project_id or 0,
                task_id=0,
                context=context,  # Inject RAG context
                mcp_manager=None,
                vector_store=None
            )
            cache_agent(session_id, agent_instance)

        # For LangGraph the external ref IS the checkpoint thread id.
        return RuntimeSessionRef(runtime=self.name, session_id=session_id, external_ref=session_id)

    async def stream(
        self,
        ref: RuntimeSessionRef,
        message: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[RuntimeEvent]:
        """Stream RuntimeEvents for one user message."""
        # Create new user message (checkpointer loads previous messages)
        from langchain_core.messages import HumanMessage
        new_message = HumanMessage(content=message)

        async for event in self._run({"messages": [new_message]}, ref, options or {}):
            yield event

    async def resume(
        self,
        ref: RuntimeSessionRef,
        payload: Dict[str, Any],
    ) -> AsyncIterator[RuntimeEvent]:
        """Resume an interrupted HITL run via LangGraph Command(resume=...)."""
        from langgraph.types import Command

        async for event in self._run(Command(resume=payload), ref, {}):
            yield event

    async def destroy_session(self, ref: RuntimeSessionRef) -> Any:
        """Cleanup LangGraph checkpoints for this thread.

        Relocated verbatim from the routes' cleanup blocks (including the
        deferred import); exceptions propagate so callers keep their existing
        warn-and-continue handling.
        """
        from core.workflows.checkpointing.utils import delete_thread_checkpoints
        return await delete_thread_checkpoints(thread_id=ref.external_ref or ref.session_id)

    # -------------------------------------------------------------------------
    # Internal: the relocated astream_events(version="v2") loop
    # -------------------------------------------------------------------------

    async def _run(
        self,
        input_obj: Any,
        ref: RuntimeSessionRef,
        options: Dict[str, Any],
    ) -> AsyncIterator[RuntimeEvent]:
        session_id = ref.session_id
        thread_id = ref.external_ref or ref.session_id
        project_id = options.get("project_id") or 0
        enable_hitl = bool(options.get("enable_hitl", False))

        agent_instance = get_cached_agent(session_id)
        if agent_instance is None:
            raise RuntimeError(
                f"No agent instance available for session {session_id}; "
                "call create_session() before stream()/resume()"
            )

        # Create event handler for tracking tool calls and subagent activity
        event_handler = ExecutionEventCallbackHandler(
            project_id=project_id,
            task_id=0,
            workflow_id=None,  # No workflow for chat sessions
            enable_sanitization=True,
            save_to_db=False  # Don't persist to DB for chat sessions
        )

        full_response = ""
        assistant_artifacts: List[Dict[str, Any]] = []
        assistant_content_blocks: List[Dict[str, Any]] = []
        artifact_cursor = 0

        # Use astream_events for token-by-token streaming.
        # MUST be v2: Pregel's v3 stream API is experimental and returns
        # an awaitable AsyncGraphRunStream, not an async iterator -
        # `async for` over it raises "'async for' requires an object
        # with __aiter__ method, got coroutine" on every chat prompt.
        # v2 yields the StreamEvent dicts that normalize_stream_event
        # and the RuntimeEvent handlers below consume.
        # Guarded by tests/test_chat_stream_contract.py.
        async for event in agent_instance.astream_events(
            input_obj,
            config={
                "configurable": {"thread_id": thread_id, "enable_hitl": enable_hitl},
                "metadata": {"enable_hitl": enable_hitl},
                "callbacks": [event_handler],
                "recursion_limit": 500  # Increased from default 25 for complex tool chains
            },
            version="v2"
        ):
            kind = event.get("event")
            normalized_event = normalize_stream_event(event)

            # Stream tool call events
            if normalized_event and normalized_event.get("type") == "tool_started":
                yield {
                    "type": "tool_start",
                    "tool_name": normalized_event.get("tool_name") or "unknown",
                    "data": {
                        "input": normalized_event.get("input"),
                        "namespace": normalized_event.get("namespace"),
                    },
                }

            elif normalized_event and normalized_event.get("type") in {"tool_completed", "tool_error"}:
                tool_name = normalized_event.get("tool_name") or "unknown"
                yield {
                    "type": "tool_end",
                    "tool_name": tool_name,
                    "data": {
                        "output": normalized_event.get("output"),
                        "error": normalized_event.get("error"),
                        "namespace": normalized_event.get("namespace"),
                    },
                }

                collected_artifacts = event_handler.get_collected_artifacts()
                new_artifacts = collected_artifacts[artifact_cursor:]
                artifact_cursor = len(collected_artifacts)
                for artifact in new_artifacts:
                    artifact = make_json_safe(artifact)
                    if not isinstance(artifact, dict):
                        continue
                    assistant_artifacts.append(artifact)
                    if artifact.get("type") in {"image", "audio", "file", "resource"}:
                        assistant_content_blocks.append(artifact)
                    yield {
                        "type": "tool_artifact",
                        "tool_name": tool_name,
                        "data": {"artifact": artifact},
                    }

            # Stream custom events (LangGraph-style progress bars, status badges, etc.)
            elif kind == "on_custom_event" or (kind == "custom_event"):
                custom_data = event.get("data", {})
                safe_data = make_json_safe(custom_data)
                yield {"type": "custom", "data": safe_data}

            # Stream model thinking (Anthropic adaptive thinking summaries).
            # Kept separate from full_response so reasoning text is never
            # mixed into the assistant message content.
            elif normalized_event and normalized_event.get("type") == "thinking_delta":
                thinking_token = normalized_event.get("text")
                if isinstance(thinking_token, str) and thinking_token:
                    yield {"type": "thinking_delta", "text": thinking_token}

            # Stream LLM tokens as they're generated
            elif normalized_event and normalized_event.get("type") == "text_delta":
                token = normalized_event.get("text")

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
                    yield {"type": "text_delta", "text": token}

        # Completion event (mirrors the route's final SSE frame payload)
        yield {
            "type": "complete",
            "text": full_response,
            "data": {
                "artifacts": assistant_artifacts,
                "content_blocks": assistant_content_blocks,
                "has_multimodal": has_multimodal_blocks(assistant_content_blocks),
            },
        }
