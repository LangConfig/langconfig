# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Anthropic Managed Agents implementation of the AgentRuntime protocol.

Executes chat agents via Anthropic's hosted Managed Agents beta
(``managed-agents-2026-04-01``): the agent loop runs on Anthropic's
orchestration layer and tools execute in an Anthropic-hosted container.
LangConfig only drives the session event stream behind the same RuntimeEvent
contract as the LangGraph/ADK runtimes.

Design notes (verified against anthropic 0.105.2 source —
``resources/beta/{agents,sessions,environments}`` and
``types/beta/sessions/*``):

- **Agents are persistent, versioned objects.** ``prepare_template`` (called
  from the template save endpoints, never the chat path) creates/updates one
  Anthropic agent per LangConfig template and returns
  ``{"anthropic_agent_id", "anthropic_agent_version"}`` for persistence into
  ``deep_agent_templates.external_refs``. ``agents.update`` requires the
  current ``version`` as an optimistic lock, so we ``retrieve`` first.
- **Sessions** are created lazily per chat session
  (``sessions.create(agent=<id>, environment_id=..., title=...)``) and the
  Anthropic session id (``external_ref``) is persisted to
  ``chat_sessions.external_session_ref`` so conversations survive backend
  restarts (``capabilities.checkpoint_resume``).
- **Stream-first ordering:** ``stream()`` opens
  ``sessions.events.stream(...)`` BEFORE ``events.send(...)`` — the SSE
  stream has no replay, so sending first can drop the earliest events.
- **Event mapping** (SDK event ``type`` -> RuntimeEvent):
    agent.message                   -> text_delta (full text of the blocks)
    agent.thinking                  -> thinking_delta (progress signal; the
                                       SDK event carries no text content)
    agent.tool_use                  -> tool_start (id->name remembered so the
                                       result can be labeled)
    agent.tool_result               -> tool_end
    agent.thread_context_compacted  -> custom (info)
    span.model_request_end          -> usage (model_usage payload)
    session.error                   -> error + break
    session.status_terminated       -> error + break
    session.status_idle             -> break ONLY when stop_reason.type !=
                                       "requires_action" (the documented idle
                                       gate). requires_action should never
                                       happen in v1 (no custom tools, default
                                       always_allow permissions) -> error +
                                       break defensively.
- **RAG context** is held at session build time and prepended to the FIRST
  user message (``<context>...</context>``) because the system prompt lives
  on the shared Anthropic agent object, not the session.
- **Resumed sessions** (second+ message): same stream-first flow. Each turn
  opens its stream before sending, so there is no missed-event gap to
  consolidate; an ``events.list`` + dedupe pass is deliberately NOT done
  because replaying prior turns' ``agent.message`` events would duplicate
  text already persisted in chat history. (events.list consolidation only
  matters for mid-turn reconnects, which this runtime does not attempt.)
- **destroy_session** polls ``sessions.retrieve`` until the session is not
  ``running`` (post-idle status-write race), then archives the SESSION only.
  The agent object is never archived (archive is permanent).
"""

import asyncio
import logging
import re
from typing import Any, AsyncIterator, Dict, Optional, Tuple

from anthropic import APIStatusError, AsyncAnthropic

# Fail fast (ImportError) on SDKs that predate the Managed Agents beta
# surface so the registry can raise a clear install hint.
from anthropic.resources.beta.agents import AsyncAgents as _AsyncAgents  # noqa: F401
from anthropic.resources.beta.environments import (  # noqa: F401
    AsyncEnvironments as _AsyncEnvironments,
)
from anthropic.resources.beta.sessions import AsyncSessions as _AsyncSessions  # noqa: F401

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

# Default environment created when ANTHROPIC_MANAGED_ENVIRONMENT_ID is unset.
DEFAULT_ENVIRONMENT_NAME = "langconfig-default"

# Anthropic's prebuilt toolset (bash, read/write/edit, glob/grep,
# web_search/web_fetch) — the ONLY toolset in v1 (no custom tools).
AGENT_TOOLSET = [{"type": "agent_toolset_20260401"}]


def _slug_agent_name(name: Optional[str]) -> str:
    """Slug a template name into a 1-256 char Anthropic agent name."""
    candidate = re.sub(r"[^A-Za-z0-9._ -]+", "-", (name or "").strip())
    candidate = re.sub(r"-{2,}", "-", candidate).strip("- ")
    return (candidate or "langconfig-agent")[:256]


class AnthropicManagedRuntime(AgentRuntime):
    """Executes chat agents via Anthropic Managed Agents (Claude models only)."""

    name = "anthropic_managed"
    capabilities = RuntimeCapabilities(
        streaming=True,
        hitl=False,
        custom_tools=False,
        # Anthropic stores the session server-side; we persist its id in
        # chat_sessions.external_session_ref, so chats survive restarts.
        checkpoint_resume=True,
    )

    # Post-idle status-write race: poll before archive (Anthropic rejects
    # archive while the session still reads 'running'). Class attributes so
    # tests can shrink the interval.
    ARCHIVE_POLL_ATTEMPTS = 10
    ARCHIVE_POLL_INTERVAL_S = 0.2

    def __init__(self) -> None:
        self._client: Optional[AsyncAnthropic] = None
        self._environment_id: Optional[str] = None
        # chat session_id -> anthropic session id (sesn_...)
        self._sessions: Dict[str, str] = {}
        # chat session_id -> RAG context awaiting its first user message
        self._pending_context: Dict[str, str] = {}

    # -------------------------------------------------------------------------
    # AgentRuntime interface
    # -------------------------------------------------------------------------

    async def prepare_template(self, template_row: Any, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update the Anthropic agent backing this template.

        NOTE: unlike the other runtimes (which return the validated config),
        this returns the external refs to persist into the template's
        ``external_refs`` JSON column:
        ``{"anthropic_agent_id": ..., "anthropic_agent_version": ...}``.
        Agents are NEVER created from the chat path — only here, on save.
        """
        raw_config = dict(config) if isinstance(config, dict) else config.model_dump()
        validated = DeepAgentConfig(**raw_config)
        self._require_claude_model(validated.model)

        client = self._get_client()
        system_prompt = await self._build_system_prompt(validated, raw_config)
        agent_name = _slug_agent_name(
            getattr(template_row, "name", None) or raw_config.get("name")
        )

        existing_refs = dict(getattr(template_row, "external_refs", None) or {})
        agent_id = existing_refs.get("anthropic_agent_id")

        if agent_id:
            # Later saves: update in place (new immutable version). update()
            # takes the current version as an optimistic lock — retrieve it
            # fresh so a stale stored version never bricks the save.
            current = await client.beta.agents.retrieve(agent_id)
            agent = await client.beta.agents.update(
                agent_id,
                version=current.version,
                name=agent_name,
                model=validated.model,
                system=system_prompt,
                tools=AGENT_TOOLSET,
            )
            logger.info(
                "Updated Anthropic managed agent %s -> version %s (template=%r)",
                agent.id, agent.version, agent_name,
            )
        else:
            # First save: create the persistent agent object.
            agent = await client.beta.agents.create(
                name=agent_name,
                model=validated.model,
                system=system_prompt,
                tools=AGENT_TOOLSET,
            )
            logger.info(
                "Created Anthropic managed agent %s version %s (template=%r)",
                agent.id, agent.version, agent_name,
            )

        return {
            "anthropic_agent_id": agent.id,
            "anthropic_agent_version": agent.version,
        }

    async def create_session(
        self,
        config: Dict[str, Any],
        session_id: str,
        context: str = "",
        project_id: Optional[int] = None,
    ) -> RuntimeSessionRef:
        """Get or create the Anthropic session for this chat session.

        The config must carry the template's ``external_refs`` (threaded
        through by the chat route) so the pre-created agent id is available —
        agents are never created here.
        """
        raw_config = dict(config) if isinstance(config, dict) else config.model_dump()
        agent_config = (
            config if isinstance(config, DeepAgentConfig) else DeepAgentConfig(**raw_config)
        )
        self._require_claude_model(agent_config.model)

        # Cache-first, mirroring the other runtimes (the route calls
        # create_session before every message).
        cached = self._sessions.get(session_id)
        if cached:
            return RuntimeSessionRef(
                runtime=self.name, session_id=session_id, external_ref=cached
            )

        # Restart recovery: the anthropic session id persisted on the chat
        # session row (Anthropic holds the conversation server-side).
        persisted = await self._load_external_ref(session_id)
        if persisted:
            self._sessions[session_id] = persisted
            if context:
                self._pending_context[session_id] = context
            logger.info(
                "Resumed Anthropic managed session %s for chat session %s",
                persisted, session_id,
            )
            return RuntimeSessionRef(
                runtime=self.name, session_id=session_id, external_ref=persisted
            )

        refs = raw_config.get("external_refs") or {}
        agent_id = refs.get("anthropic_agent_id")
        if not agent_id:
            raise ValueError(
                "This agent template has no Anthropic managed agent yet "
                "(external_refs.anthropic_agent_id is missing). Re-save the "
                "template with runtime='anthropic_managed' to provision it."
            )

        client = self._get_client()
        environment_id = await self._ensure_environment(client)

        session = await client.beta.sessions.create(
            agent=agent_id,  # string shorthand -> latest agent version
            environment_id=environment_id,
            title=f"chat-{session_id}",
        )

        self._sessions[session_id] = session.id
        if context:
            # System prompt is shared across sessions on the agent object, so
            # RAG context rides on the first user message instead.
            self._pending_context[session_id] = context
        await self._store_external_ref(session_id, session.id)

        logger.info(
            "Created Anthropic managed session %s (chat session %s, agent %s)",
            session.id, session_id, agent_id,
        )
        return RuntimeSessionRef(
            runtime=self.name, session_id=session_id, external_ref=session.id
        )

    async def stream(
        self,
        ref: RuntimeSessionRef,
        message: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[RuntimeEvent]:
        """Stream RuntimeEvents for one user message.

        STREAM-FIRST: the SSE stream is opened BEFORE events.send so no early
        events are missed (the stream has no replay).
        """
        anthropic_session_id = ref.external_ref or self._sessions.get(ref.session_id)
        if not anthropic_session_id:
            raise RuntimeError(
                f"No Anthropic managed session for chat session {ref.session_id}; "
                "call create_session() before stream()"
            )

        pending_context = self._pending_context.pop(ref.session_id, "")
        if pending_context:
            message = f"<context>\n{pending_context}\n</context>\n\n{message}"

        client = self._get_client()

        full_response = ""
        saw_error = False
        # agent.tool_result carries only tool_use_id — remember names.
        tool_names: Dict[str, str] = {}

        # 1) Open the stream FIRST (it buffers server-side from this moment).
        event_stream = await client.beta.sessions.events.stream(anthropic_session_id)
        try:
            # 2) THEN send the user message.
            await client.beta.sessions.events.send(
                anthropic_session_id,
                events=[{
                    "type": "user.message",
                    "content": [{"type": "text", "text": message}],
                }],
            )

            # 3) Drain until the documented terminal gate.
            async for event in event_stream:
                etype = getattr(event, "type", None)

                if etype == "agent.message":
                    text = "".join(
                        getattr(block, "text", "") or ""
                        for block in (getattr(event, "content", None) or [])
                        if getattr(block, "type", None) == "text"
                    )
                    if text:
                        full_response += text
                        yield {"type": "text_delta", "text": text}

                elif etype == "agent.thinking":
                    # Progress signal only — the SDK event carries no text.
                    yield {"type": "thinking_delta", "text": ""}

                elif etype == "agent.tool_use":
                    tool_name = getattr(event, "name", None) or "unknown"
                    event_id = getattr(event, "id", None)
                    if event_id:
                        tool_names[event_id] = tool_name
                    yield {
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "data": {
                            "input": make_json_safe(dict(getattr(event, "input", None) or {})),
                            "namespace": None,
                        },
                    }

                elif etype == "agent.tool_result":
                    tool_use_id = getattr(event, "tool_use_id", None)
                    tool_name = tool_names.pop(tool_use_id, "unknown")
                    output, error = self._render_tool_result(event)
                    yield {
                        "type": "tool_end",
                        "tool_name": tool_name,
                        "data": {"output": output, "error": error, "namespace": None},
                    }

                elif etype == "agent.thread_context_compacted":
                    yield {
                        "type": "custom",
                        "data": {
                            "event": "context_compacted",
                            "message": "Conversation context was compacted by Anthropic",
                        },
                    }

                elif etype == "span.model_request_end":
                    usage = getattr(event, "model_usage", None)
                    if usage is not None:
                        usage_payload = (
                            usage.model_dump(exclude_none=True)
                            if hasattr(usage, "model_dump") else dict(usage)
                        )
                        yield {"type": "usage", "data": make_json_safe(usage_payload)}

                elif etype == "session.error":
                    saw_error = True
                    yield {"type": "error", "error": self._render_session_error(event)}
                    break

                elif etype == "session.status_terminated":
                    saw_error = True
                    yield {
                        "type": "error",
                        "error": "Anthropic managed session terminated unexpectedly",
                    }
                    break

                elif etype == "session.status_idle":
                    stop_reason = getattr(event, "stop_reason", None)
                    stop_type = getattr(stop_reason, "type", None)
                    if stop_type == "requires_action":
                        # Should never happen in v1 (no custom tools, default
                        # always_allow). Bail out defensively rather than
                        # deadlock waiting on a confirmation we can't send.
                        saw_error = True
                        yield {
                            "type": "error",
                            "error": (
                                "Anthropic managed session is waiting on a "
                                "client action (requires_action), which this "
                                "runtime does not support"
                            ),
                        }
                        break
                    if stop_type == "retries_exhausted":
                        saw_error = True
                        yield {
                            "type": "error",
                            "error": "Anthropic managed session exhausted its retries",
                        }
                    # end_turn / retries_exhausted are both terminal -> break.
                    break

                # user.* echoes, span starts, thread events, etc. -> ignored.
        finally:
            await event_stream.close()

        # Completion event — same envelope shape as the other runtimes so the
        # route's persistence + SSE 'complete' frame stay runtime-agnostic.
        if saw_error and not full_response:
            logger.warning(
                "Anthropic managed stream for session %s ended with an error "
                "and no text", ref.session_id,
            )
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
        """Archive the Anthropic SESSION (never the agent) after it settles.

        The SSE stream reports idle slightly before the queryable status
        flips, so archive-while-running 400s — poll first.
        """
        anthropic_session_id = ref.external_ref or self._sessions.get(ref.session_id)
        self._sessions.pop(ref.session_id, None)
        self._pending_context.pop(ref.session_id, None)

        if not anthropic_session_id or anthropic_session_id == ref.session_id:
            # Nothing was created remotely (or we only have the local id).
            return True

        client = self._get_client()

        status = None
        for _ in range(self.ARCHIVE_POLL_ATTEMPTS):
            session = await client.beta.sessions.retrieve(anthropic_session_id)
            status = getattr(session, "status", None)
            if status != "running":
                break
            await asyncio.sleep(self.ARCHIVE_POLL_INTERVAL_S)

        if status == "running":
            logger.warning(
                "Anthropic managed session %s still running after %.1fs; "
                "skipping archive",
                anthropic_session_id,
                self.ARCHIVE_POLL_ATTEMPTS * self.ARCHIVE_POLL_INTERVAL_S,
            )
            return False

        await client.beta.sessions.archive(anthropic_session_id)
        logger.info("Archived Anthropic managed session %s", anthropic_session_id)
        return True

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _require_claude_model(model: Optional[str]) -> None:
        if not (model or "").startswith("claude"):
            raise ValueError(
                f"The Anthropic Managed runtime only supports Claude models; "
                f"got '{model}'. Select a 'claude-*' model in the agent "
                f"builder, or switch the agent's runtime back to 'langgraph'."
            )

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is not configured; the "
                    "'anthropic_managed' runtime requires it (set it in "
                    "backend/.env or the settings page)."
                )
            self._client = AsyncAnthropic(api_key=api_key)
        return self._client

    async def _ensure_environment(self, client: AsyncAnthropic) -> str:
        """Resolve (or create) the reusable cloud environment for sessions."""
        if self._environment_id:
            return self._environment_id

        configured = getattr(settings, "ANTHROPIC_MANAGED_ENVIRONMENT_ID", None)
        if configured:
            self._environment_id = configured
            return configured

        try:
            environment = await client.beta.environments.create(
                name=DEFAULT_ENVIRONMENT_NAME,
                config={"type": "cloud", "networking": {"type": "unrestricted"}},
            )
            environment_id = environment.id
        except APIStatusError as e:
            if e.status_code != 409:
                raise
            # Environment names are unique — reuse the one a previous process
            # created (its id was never pinned in .env).
            environment_id = await self._find_environment_by_name(
                client, DEFAULT_ENVIRONMENT_NAME
            )
            if not environment_id:
                raise

        self._environment_id = environment_id
        logger.warning(
            "=" * 70 + "\n"
            "Created/resolved Anthropic Managed Agents environment '%s': %s\n"
            "Add this to backend/.env to reuse it across restarts:\n"
            "    ANTHROPIC_MANAGED_ENVIRONMENT_ID=%s\n" + "=" * 70,
            DEFAULT_ENVIRONMENT_NAME, environment_id, environment_id,
        )
        return environment_id

    @staticmethod
    async def _find_environment_by_name(
        client: AsyncAnthropic, name: str
    ) -> Optional[str]:
        async for environment in client.beta.environments.list():
            if getattr(environment, "name", None) == name:
                return environment.id
        return None

    @staticmethod
    async def _build_system_prompt(
        agent_config: DeepAgentConfig, raw_config: Dict[str, Any]
    ) -> str:
        """Assemble the system prompt with the SAME pipeline the LangGraph/ADK
        runtimes use (guardrails + role, then optional skills injection).

        Context is empty here: the prompt lives on the shared agent object and
        per-session RAG context rides on the first user message instead.
        """
        from core.agents.factory import AgentFactory

        long_term_memory = bool(
            agent_config.guardrails and agent_config.guardrails.long_term_memory
        )

        system_prompt = AgentFactory._construct_system_prompt_string(
            agent_config.system_prompt,
            "",  # no RAG context at template-save time
            enable_memory=False,
            long_term_memory=long_term_memory,
            tools=None,  # Anthropic's builtin toolset isn't LangChain tools
        )

        if raw_config.get("enable_skills"):
            system_prompt = await AgentFactory._inject_skills(
                system_prompt=system_prompt,
                context={
                    "query": "",
                    "project_type": raw_config.get("project_type"),
                    "tags": raw_config.get("skill_tags", []),
                },
                explicit_skills=raw_config.get("skills", []),
                enable_auto_detection=raw_config.get("enable_skill_auto_detection", True),
                max_skills=raw_config.get("max_skills", 3),
            )

        return system_prompt

    @staticmethod
    def _render_tool_result(event: Any) -> Tuple[Optional[str], Optional[str]]:
        """Flatten an agent.tool_result event's blocks to (output, error)."""
        parts = []
        for block in getattr(event, "content", None) or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                parts.append(getattr(block, "text", "") or "")
            elif block_type:
                parts.append(f"[{block_type}]")
        output = "\n".join(part for part in parts if part) or None
        if getattr(event, "is_error", False):
            return None, output or "Tool execution failed"
        return output, None

    @staticmethod
    def _render_session_error(event: Any) -> str:
        error = getattr(event, "error", None)
        message = getattr(error, "message", None) or str(error or "unknown error")
        error_type = getattr(error, "type", None)
        return f"{error_type}: {message}" if error_type else message

    # -------------------------------------------------------------------------
    # External-ref persistence (chat_sessions.external_session_ref)
    # -------------------------------------------------------------------------

    async def _load_external_ref(self, session_id: str) -> Optional[str]:
        """Read the persisted Anthropic session id for a chat session.

        Failures degrade to in-process caching only (a fresh Anthropic
        session would be created, losing server-side history but not the
        DB-persisted transcript).
        """
        def _read() -> Optional[str]:
            from db.database import SessionLocal
            from models.deep_agent import ChatSession

            with SessionLocal() as db:
                row = (
                    db.query(ChatSession.external_session_ref)
                    .filter(ChatSession.session_id == session_id)
                    .first()
                )
                return row[0] if row else None

        try:
            external_ref = await asyncio.to_thread(_read)
        except Exception as e:
            logger.warning(
                "Could not load external_session_ref for %s: %s", session_id, e
            )
            return None
        # Guard against rows stamped by other runtimes (they use the chat
        # session id itself as the external ref).
        if external_ref and external_ref != session_id:
            return external_ref
        return None

    async def _store_external_ref(self, session_id: str, external_ref: str) -> None:
        def _write() -> None:
            from db.database import SessionLocal
            from models.deep_agent import ChatSession

            with SessionLocal() as db:
                row = (
                    db.query(ChatSession)
                    .filter(ChatSession.session_id == session_id)
                    .first()
                )
                if row is not None:
                    row.external_session_ref = external_ref
                    db.commit()

        try:
            await asyncio.to_thread(_write)
        except Exception as e:
            logger.warning(
                "Could not persist external_session_ref for %s: %s "
                "(conversation will not survive a backend restart)",
                session_id, e,
            )
