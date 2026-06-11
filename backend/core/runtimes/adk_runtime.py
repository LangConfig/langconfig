# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Google ADK implementation of the AgentRuntime protocol.

Executes chat agents via google-adk (LlmAgent + Runner) behind the same
RuntimeEvent contract as the LangGraph runtime, so api/chat/routes.py needs
no runtime-specific branching.

Design notes (verified against google-adk 1.22.1 source):

- ``Runner.run_async(user_id=, session_id=, new_message=, run_config=)``
  yields ``google.adk.events.Event`` objects. With
  ``StreamingMode.SSE`` the runner emits *partial* text chunks
  (``event.partial is True``) AND a final aggregated event that repeats the
  full text (``event.partial`` falsy). We therefore emit ``text_delta`` for
  partials and dedupe the aggregated event against what was already
  streamed, so the SSE route never sees the same text twice.
- ``Part.thought`` marks Gemini thinking text -> ``thinking_delta`` (never
  mixed into the assistant content, mirroring LangGraphRuntime).
- ``Part.function_call`` / ``Part.function_response`` -> tool_start/tool_end.
- ``event.usage_metadata`` -> ``usage`` RuntimeEvent (no SSE frame yet).
- ``event.error_code`` / ``error_message`` -> ``error`` RuntimeEvent.

Sessions: ADK conversation memory lives in an ADK session service.
We use ``DatabaseSessionService`` against the app's Postgres (converted to an
asyncpg URL; it lazily creates its own ``sessions``/``events``/``app_states``/
``user_states``/``adk_internal_metadata`` tables, which do not collide with
LangConfig tables). If it cannot be constructed or fails at runtime we fall
back to a process-local ``InMemorySessionService`` (logged TODO; ADK
conversations then do not survive backend restarts and
``capabilities.checkpoint_resume`` is flipped off).

RAG context: injected into the agent ``instruction`` via the same
``AgentFactory._construct_system_prompt_string`` <context> block the
LangGraph path uses (context is fixed at session build time there too).
"""

import logging
import os
import re
from typing import Any, AsyncIterator, Dict, List, Optional

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, InMemorySessionService
from google.adk.tools.langchain_tool import LangchainTool
from google.genai import types as genai_types

from config import settings
from core.runtimes.base import (
    AgentRuntime,
    RuntimeCapabilities,
    RuntimeEvent,
    RuntimeSessionRef,
    make_json_safe,
)
from models.deep_agent import DeepAgentConfig

logger = logging.getLogger(__name__)

# ADK scopes sessions by (app_name, user_id, session_id). LangConfig chat
# sessions are single-tenant today, so static app/user identifiers keep the
# chat session_id the only meaningful key.
ADK_APP_NAME = "langconfig"
ADK_USER_ID = "langconfig"


def _to_async_db_url(db_url: str) -> str:
    """Convert the app DATABASE_URL to the async URL ADK's engine needs.

    DatabaseSessionService calls ``create_async_engine`` internally, so a
    sync ``postgresql://`` URL must be rewritten to the asyncpg dialect.
    """
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url
    if db_url.startswith("postgresql+psycopg2://"):
        return db_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return db_url


def _sanitize_agent_name(name: Optional[str]) -> str:
    """ADK agent names must be valid identifiers."""
    candidate = re.sub(r"\W+", "_", (name or "").strip()).strip("_")
    if not candidate or not candidate[0].isalpha():
        return "langconfig_agent"
    return candidate


class GoogleADKRuntime(AgentRuntime):
    """Executes chat agents via Google ADK (Gemini models only)."""

    name = "google_adk"
    capabilities = RuntimeCapabilities(
        streaming=True,
        hitl=False,
        custom_tools=True,
        # DatabaseSessionService persists ADK events in Postgres, so
        # conversations survive backend restarts. Flipped to False at runtime
        # if we have to fall back to the in-memory session service.
        checkpoint_resume=True,
    )

    def __init__(self) -> None:
        # session_id -> Runner (mirrors the LangGraph agent-instance cache)
        self._runners: Dict[str, Runner] = {}
        self._session_service: Optional[Any] = None

    # -------------------------------------------------------------------------
    # AgentRuntime interface
    # -------------------------------------------------------------------------

    async def prepare_template(self, template_row: Any, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the config and enforce the Gemini-only model gate."""
        validated = DeepAgentConfig(**config)
        self._require_gemini_model(validated.model)
        return validated.model_dump(exclude_none=True)

    async def create_session(
        self,
        config: Dict[str, Any],
        session_id: str,
        context: str = "",
        project_id: Optional[int] = None,
    ) -> RuntimeSessionRef:
        """Build (or reuse) the ADK Runner + session for ``session_id``."""
        if session_id in self._runners:
            # Cache-first, mirroring LangGraphRuntime.create_session.
            return RuntimeSessionRef(
                runtime=self.name, session_id=session_id, external_ref=session_id
            )

        raw_config: Dict[str, Any] = dict(config) if isinstance(config, dict) else config.model_dump()
        agent_config = config if isinstance(config, DeepAgentConfig) else DeepAgentConfig(**raw_config)

        self._require_gemini_model(agent_config.model)
        self._ensure_google_api_key()

        # Load our LangChain BaseTools via the exact loaders the chat
        # (LangGraph) path uses, then adapt them for ADK.
        base_tools = await self._load_base_tools(agent_config, project_id)
        adk_tools = self._wrap_tools(base_tools)

        instruction = await self._build_instruction(
            agent_config, raw_config, context, base_tools
        )

        generate_config = genai_types.GenerateContentConfig(
            temperature=agent_config.temperature,
            max_output_tokens=agent_config.max_tokens,
        )

        agent = LlmAgent(
            name=_sanitize_agent_name(raw_config.get("name")),
            model=agent_config.model,
            description=raw_config.get("description") or "LangConfig chat agent",
            instruction=instruction,
            tools=adk_tools,
            generate_content_config=generate_config,
        )

        external_ref = await self._ensure_adk_session(session_id)

        self._runners[session_id] = Runner(
            app_name=ADK_APP_NAME,
            agent=agent,
            session_service=self._get_session_service(),
        )

        logger.info(
            "Created Google ADK session %s (model=%s, tools=%d/%d wrapped)",
            session_id, agent_config.model, len(adk_tools), len(base_tools),
        )
        return RuntimeSessionRef(
            runtime=self.name, session_id=session_id, external_ref=external_ref
        )

    async def stream(
        self,
        ref: RuntimeSessionRef,
        message: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[RuntimeEvent]:
        """Stream RuntimeEvents for one user message via Runner.run_async."""
        runner = self._runners.get(ref.session_id)
        if runner is None:
            raise RuntimeError(
                f"No ADK runner available for session {ref.session_id}; "
                "call create_session() before stream()"
            )

        new_message = genai_types.Content(
            role="user", parts=[genai_types.Part(text=message)]
        )

        full_response = ""       # everything emitted as text_delta so far
        pending_text = ""        # partial text streamed since last aggregated event
        pending_thought = ""     # partial thinking streamed since last aggregated event

        async for event in runner.run_async(
            user_id=ADK_USER_ID,
            session_id=ref.external_ref or ref.session_id,
            new_message=new_message,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            if event.error_code or event.error_message:
                error_msg = event.error_message or str(event.error_code)
                if event.error_code and event.error_message:
                    error_msg = f"{event.error_code}: {event.error_message}"
                yield {"type": "error", "error": error_msg}
                continue

            parts = list(event.content.parts) if event.content and event.content.parts else []

            if event.partial:
                # Streaming chunks (typewriter path). Partial function_call
                # parts are internal argument-building chunks - skip them.
                for part in parts:
                    if not part.text:
                        continue
                    if part.thought:
                        pending_thought += part.text
                        yield {"type": "thinking_delta", "text": part.text}
                    else:
                        pending_text += part.text
                        full_response += part.text
                        yield {"type": "text_delta", "text": part.text}
                continue

            # Aggregated (non-partial) event. With progressive SSE streaming
            # ADK repeats the full text of the segment here - emit only what
            # was NOT already streamed as partial chunks.
            segment_text = "".join(
                part.text or "" for part in parts if part.text and not part.thought
            )
            if segment_text and segment_text != pending_text:
                remainder = (
                    segment_text[len(pending_text):]
                    if segment_text.startswith(pending_text)
                    else segment_text
                )
                if remainder:
                    full_response += remainder
                    yield {"type": "text_delta", "text": remainder}
            # Aggregated thought text already streamed -> never re-emitted.
            pending_text = ""
            pending_thought = ""

            for part in parts:
                if part.function_call:
                    yield {
                        "type": "tool_start",
                        "tool_name": part.function_call.name or "unknown",
                        "data": {
                            "input": make_json_safe(dict(part.function_call.args or {})),
                            "namespace": None,
                        },
                    }
                elif part.function_response:
                    yield {
                        "type": "tool_end",
                        "tool_name": part.function_response.name or "unknown",
                        "data": {
                            "output": make_json_safe(part.function_response.response),
                            "error": None,
                            "namespace": None,
                        },
                    }

            if event.usage_metadata is not None:
                yield {
                    "type": "usage",
                    "data": make_json_safe(
                        event.usage_metadata.model_dump(exclude_none=True)
                    ),
                }

        # Completion event - same envelope shape as LangGraphRuntime so the
        # route's persistence + SSE 'complete' frame are runtime-agnostic.
        # ADK has no tool-artifact concept, so those collections stay empty.
        yield {
            "type": "complete",
            "text": full_response,
            "data": {
                "artifacts": [],
                "content_blocks": [],
                "has_multimodal": False,
            },
        }

    async def destroy_session(self, ref: RuntimeSessionRef) -> Any:
        """Drop the cached runner and delete the ADK session server-side."""
        self._runners.pop(ref.session_id, None)

        service = self._session_service
        if service is None:
            return True

        session_id = ref.external_ref or ref.session_id
        await service.delete_session(
            app_name=ADK_APP_NAME, user_id=ADK_USER_ID, session_id=session_id
        )
        return True

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _require_gemini_model(model: Optional[str]) -> None:
        if not (model or "").startswith("gemini"):
            raise ValueError(
                f"The Google ADK runtime only supports Gemini models; got "
                f"'{model}'. Select a 'gemini-*' model in the agent builder, "
                f"or switch the agent's runtime back to 'langgraph'."
            )

    @staticmethod
    def _ensure_google_api_key() -> None:
        """Expose the configured Google key to ADK's google-genai client."""
        if os.getenv("GOOGLE_API_KEY"):
            return
        key = getattr(settings, "GOOGLE_API_KEY", None)
        if key:
            os.environ["GOOGLE_API_KEY"] = key
        else:
            logger.warning(
                "GOOGLE_API_KEY is not configured; Google ADK requests will fail"
            )

    @staticmethod
    async def _load_base_tools(
        agent_config: DeepAgentConfig, project_id: Optional[int]
    ) -> List[Any]:
        """Load native/CLI/custom BaseTools via the shared chat loaders."""
        from services.deepagent_factory import DeepAgentFactory

        return await DeepAgentFactory._load_base_tools(
            config=agent_config,
            mcp_manager=None,
            vector_store=None,
            project_id=project_id or 0,
            task_id=0,
        )

    @staticmethod
    def _wrap_tools(tools: List[Any]) -> List[Any]:
        """Adapt LangChain BaseTools to ADK via LangchainTool.

        Individual wrap failures (unsupported schemas, async-only quirks)
        are logged and skipped so one bad tool never bricks the agent.
        """
        wrapped: List[Any] = []
        for tool in tools:
            tool_name = getattr(tool, "name", repr(tool))
            try:
                wrapped.append(LangchainTool(tool))
            except Exception as e:
                logger.warning(
                    "Skipping tool '%s' for Google ADK runtime "
                    "(LangchainTool wrap failed: %s)",
                    tool_name, e,
                )
        return wrapped

    @staticmethod
    async def _build_instruction(
        agent_config: DeepAgentConfig,
        raw_config: Dict[str, Any],
        context: str,
        tools: List[Any],
    ) -> str:
        """Assemble the instruction with the SAME prompt pipeline LangGraph
        uses: guardrails + tool enforcement + role + <context> (RAG), then
        optional skills injection. No behavior change to the LangGraph path -
        both call the existing AgentFactory static helpers.
        """
        from core.agents.factory import AgentFactory

        long_term_memory = bool(
            agent_config.guardrails and agent_config.guardrails.long_term_memory
        )

        instruction = AgentFactory._construct_system_prompt_string(
            agent_config.system_prompt,
            context or "",
            enable_memory=False,
            long_term_memory=long_term_memory,
            tools=tools,
        )

        if raw_config.get("enable_skills"):
            instruction = await AgentFactory._inject_skills(
                system_prompt=instruction,
                context={
                    "query": context or "",
                    "project_type": raw_config.get("project_type"),
                    "tags": raw_config.get("skill_tags", []),
                },
                explicit_skills=raw_config.get("skills", []),
                enable_auto_detection=raw_config.get("enable_skill_auto_detection", True),
                max_skills=raw_config.get("max_skills", 3),
            )

        return instruction

    def _get_session_service(self) -> Any:
        """Lazily build the ADK session service (Postgres-backed, with an
        in-memory fallback)."""
        if self._session_service is None:
            try:
                db_url = _to_async_db_url(settings.database_url)
                self._session_service = DatabaseSessionService(db_url=db_url)
                logger.info("Google ADK DatabaseSessionService initialized")
            except Exception as e:
                self._fallback_to_memory_sessions(e)
        return self._session_service

    def _fallback_to_memory_sessions(self, reason: Exception) -> None:
        # TODO(google_adk): DatabaseSessionService could not be used against
        # the app Postgres. Investigate and remove this fallback - in-memory
        # ADK sessions do not survive backend restarts.
        logger.warning(
            "Google ADK DatabaseSessionService unavailable (%s); falling back "
            "to InMemorySessionService. ADK conversations will NOT survive "
            "backend restarts.",
            reason,
        )
        self._session_service = InMemorySessionService()
        self.capabilities.checkpoint_resume = False

    async def _ensure_adk_session(self, session_id: str) -> str:
        """Get-or-create the ADK session keyed by our chat session_id.

        If the database-backed service fails at first use (e.g. async driver
        or table-creation issues only surface on the first query), retry once
        on the in-memory fallback.
        """
        for attempt in (0, 1):
            service = self._get_session_service()
            try:
                existing = await service.get_session(
                    app_name=ADK_APP_NAME, user_id=ADK_USER_ID, session_id=session_id
                )
                if existing is not None:
                    return existing.id
                created = await service.create_session(
                    app_name=ADK_APP_NAME, user_id=ADK_USER_ID, session_id=session_id
                )
                return created.id
            except Exception as e:
                if attempt == 0 and not isinstance(service, InMemorySessionService):
                    self._fallback_to_memory_sessions(e)
                    continue
                raise
        raise RuntimeError("unreachable")  # pragma: no cover
