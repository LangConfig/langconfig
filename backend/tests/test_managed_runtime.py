# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the Anthropic Managed Agents runtime
(core/runtimes/anthropic_managed_runtime.py).

The AsyncAnthropic client is replaced with a fake that replays REAL
anthropic.types.beta.sessions event models (constructed from the installed
anthropic 0.105.2 package), so the event mapping is exercised against the
actual Managed Agents schemas:

- agent.message                  -> text_delta
- agent.thinking                 -> thinking_delta (progress, no text)
- agent.tool_use / tool_result   -> tool_start / tool_end
- agent.thread_context_compacted -> custom
- span.model_request_end         -> usage (model_usage payload)
- session.error / terminated     -> error
- session.status_idle gate       -> end_turn completes; requires_action errors
- stream-first ordering          -> events.stream opened BEFORE events.send
- prepare_template               -> create-then-update with external_refs
- claude-only model gating       -> ValueError from create_session/prepare_template
- destroy_session                -> poll until not running, archive SESSION only
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from anthropic.types.beta.sessions import (
    BetaManagedAgentsAgentMessageEvent,
    BetaManagedAgentsAgentThinkingEvent,
    BetaManagedAgentsAgentThreadContextCompactedEvent,
    BetaManagedAgentsAgentToolResultEvent,
    BetaManagedAgentsAgentToolUseEvent,
    BetaManagedAgentsSessionEndTurn,
    BetaManagedAgentsSessionErrorEvent,
    BetaManagedAgentsSessionRequiresAction,
    BetaManagedAgentsSessionStatusIdleEvent,
    BetaManagedAgentsSessionStatusTerminatedEvent,
    BetaManagedAgentsSpanModelRequestEndEvent,
    BetaManagedAgentsSpanModelUsage,
    BetaManagedAgentsTextBlock,
    BetaManagedAgentsUnknownError,
)
from anthropic.types.beta.sessions.beta_managed_agents_retry_status_terminal import (
    BetaManagedAgentsRetryStatusTerminal,
)

from core.runtimes import get_runtime
from core.runtimes.anthropic_managed_runtime import (
    AGENT_TOOLSET,
    AnthropicManagedRuntime,
    _slug_agent_name,
)
from core.runtimes.base import RuntimeSessionRef

NOW = datetime.now(timezone.utc)


# =============================================================================
# Real-SDK event builders
# =============================================================================

def _msg(text, event_id="ev_msg"):
    return BetaManagedAgentsAgentMessageEvent(
        id=event_id,
        content=[BetaManagedAgentsTextBlock(text=text, type="text")],
        processed_at=NOW,
        type="agent.message",
    )


def _thinking(event_id="ev_think"):
    return BetaManagedAgentsAgentThinkingEvent(
        id=event_id, processed_at=NOW, type="agent.thinking"
    )


def _tool_use(name, input_, event_id="ev_tool"):
    return BetaManagedAgentsAgentToolUseEvent(
        id=event_id, input=input_, name=name, processed_at=NOW,
        type="agent.tool_use",
    )


def _tool_result(tool_use_id, text=None, is_error=None, event_id="ev_result"):
    content = None
    if text is not None:
        content = [BetaManagedAgentsTextBlock(text=text, type="text")]
    return BetaManagedAgentsAgentToolResultEvent(
        id=event_id, processed_at=NOW, tool_use_id=tool_use_id,
        type="agent.tool_result", content=content, is_error=is_error,
    )


def _compacted(event_id="ev_compact"):
    return BetaManagedAgentsAgentThreadContextCompactedEvent(
        id=event_id, processed_at=NOW, type="agent.thread_context_compacted"
    )


def _usage_end(input_tokens=10, output_tokens=5, event_id="ev_span"):
    return BetaManagedAgentsSpanModelRequestEndEvent(
        id=event_id,
        model_request_start_id="ev_span_start",
        model_usage=BetaManagedAgentsSpanModelUsage(
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        processed_at=NOW,
        type="span.model_request_end",
    )


def _session_error(message="boom", event_id="ev_err"):
    return BetaManagedAgentsSessionErrorEvent(
        id=event_id,
        error=BetaManagedAgentsUnknownError(
            message=message,
            retry_status=BetaManagedAgentsRetryStatusTerminal(type="terminal"),
            type="unknown_error",
        ),
        processed_at=NOW,
        type="session.error",
    )


def _terminated(event_id="ev_term"):
    return BetaManagedAgentsSessionStatusTerminatedEvent(
        id=event_id, processed_at=NOW, type="session.status_terminated"
    )


def _idle(stop_reason="end_turn", event_id="ev_idle"):
    if stop_reason == "end_turn":
        reason = BetaManagedAgentsSessionEndTurn(type="end_turn")
    elif stop_reason == "requires_action":
        reason = BetaManagedAgentsSessionRequiresAction(
            event_ids=["ev_blocking"], type="requires_action"
        )
    else:
        raise ValueError(stop_reason)
    return BetaManagedAgentsSessionStatusIdleEvent(
        id=event_id, processed_at=NOW, stop_reason=reason,
        type="session.status_idle",
    )


# =============================================================================
# Fake AsyncAnthropic client (records ordered calls in a shared log)
# =============================================================================

class FakeEventStream:
    """Stands in for the SDK's AsyncStream of session events."""

    def __init__(self, events, log):
        self._events = events
        self._log = log
        self.closed = False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for event in self._events:
            self._log.append(("stream.yield", getattr(event, "type", None)))
            yield event

    async def close(self):
        self.closed = True


class FakeEvents:
    def __init__(self, log, events):
        self._log = log
        self._events = events
        self.streams = []

    async def stream(self, session_id, **kwargs):
        self._log.append(("events.stream", session_id))
        stream = FakeEventStream(self._events, self._log)
        self.streams.append(stream)
        return stream

    async def send(self, session_id, *, events, **kwargs):
        self._log.append(("events.send", session_id, events))
        return SimpleNamespace(event_ids=[f"ev_user_{len(self._log)}"])


class FakeSessions:
    def __init__(self, log, events=None, statuses=None):
        self._log = log
        self.events = FakeEvents(log, events or [])
        # destroy_session polling: statuses returned by successive retrieves
        # (the last one repeats forever).
        self._statuses = list(statuses or ["idle"])

    async def create(self, *, agent, environment_id, title=None, **kwargs):
        self._log.append(("sessions.create", {
            "agent": agent, "environment_id": environment_id, "title": title,
        }))
        return SimpleNamespace(id="sesn_test123", status="running")

    async def retrieve(self, session_id, **kwargs):
        status = self._statuses[0]
        if len(self._statuses) > 1:
            self._statuses.pop(0)
        self._log.append(("sessions.retrieve", session_id, status))
        return SimpleNamespace(id=session_id, status=status)

    async def archive(self, session_id, **kwargs):
        self._log.append(("sessions.archive", session_id))
        return SimpleNamespace(id=session_id, status="archived")


class FakeAgents:
    def __init__(self, log, current_version=1):
        self._log = log
        self._current_version = current_version

    async def create(self, *, name, model, system=None, tools=None, **kwargs):
        self._log.append(("agents.create", {
            "name": name, "model": model, "system": system, "tools": tools,
        }))
        return SimpleNamespace(id="agent_abc", version=1)

    async def retrieve(self, agent_id, **kwargs):
        self._log.append(("agents.retrieve", agent_id))
        return SimpleNamespace(id=agent_id, version=self._current_version)

    async def update(self, agent_id, *, version, **kwargs):
        self._log.append(("agents.update", {
            "agent_id": agent_id, "version": version, **kwargs,
        }))
        return SimpleNamespace(id=agent_id, version=version + 1)

    async def archive(self, agent_id, **kwargs):  # must NEVER be called
        self._log.append(("agents.archive", agent_id))
        return SimpleNamespace(id=agent_id)


class FakeClient:
    def __init__(self, events=None, statuses=None, agent_version=1):
        self.log = []
        self.beta = SimpleNamespace(
            agents=FakeAgents(self.log, current_version=agent_version),
            sessions=FakeSessions(self.log, events=events, statuses=statuses),
        )


# =============================================================================
# Helpers
# =============================================================================

def _make_runtime(events=None, statuses=None, agent_version=1,
                  session_id="sid-1", anthropic_id="sesn_test123"):
    runtime = AnthropicManagedRuntime()
    client = FakeClient(events=events, statuses=statuses,
                        agent_version=agent_version)
    runtime._client = client  # bypasses the API-key check in _get_client
    runtime._environment_id = "env_test"
    runtime.ARCHIVE_POLL_INTERVAL_S = 0  # no real sleeping in tests
    ref = RuntimeSessionRef(
        runtime="anthropic_managed", session_id=session_id,
        external_ref=anthropic_id,
    )
    return runtime, client, ref


async def _collect(runtime, ref, message="hi"):
    return [event async for event in runtime.stream(ref, message)]


VALID_CONFIG = {
    "system_prompt": "You are helpful",
    "model": "claude-sonnet-4-6",
}


@pytest.fixture
def stub_system_prompt(monkeypatch):
    """Bypass the AgentFactory prompt pipeline in prepare_template tests."""
    async def _fake_prompt(agent_config, raw_config):
        return "STUBBED PROMPT"

    monkeypatch.setattr(
        AnthropicManagedRuntime, "_build_system_prompt",
        staticmethod(_fake_prompt),
    )


# =============================================================================
# Event mapping (real SDK event objects)
# =============================================================================

@pytest.mark.asyncio
async def test_stream_maps_agent_message_to_text_delta():
    events = [_msg("Hello "), _msg("world"), _idle("end_turn")]
    runtime, _, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    text_deltas = [e["text"] for e in out if e["type"] == "text_delta"]
    assert text_deltas == ["Hello ", "world"]

    complete = out[-1]
    assert complete["type"] == "complete"
    assert complete["text"] == "Hello world"
    assert complete["data"] == {
        "artifacts": [], "content_blocks": [], "has_multimodal": False,
    }
    assert not [e for e in out if e["type"] == "error"]


@pytest.mark.asyncio
async def test_stream_maps_thinking_to_thinking_delta():
    """agent.thinking is a progress signal with no content — it maps to an
    empty thinking_delta and never leaks into the assistant text."""
    events = [_thinking(), _msg("Answer"), _idle("end_turn")]
    runtime, _, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    thinking = [e for e in out if e["type"] == "thinking_delta"]
    assert len(thinking) == 1
    assert thinking[0]["text"] == ""
    assert out[-1]["text"] == "Answer"


@pytest.mark.asyncio
async def test_stream_maps_tool_use_and_result_to_tool_events():
    events = [
        _tool_use("bash", {"command": "ls"}, event_id="ev_tool_1"),
        _tool_result("ev_tool_1", text="file.txt"),
        _msg("Done"),
        _idle("end_turn"),
    ]
    runtime, _, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    tool_starts = [e for e in out if e["type"] == "tool_start"]
    assert len(tool_starts) == 1
    assert tool_starts[0]["tool_name"] == "bash"
    assert tool_starts[0]["data"]["input"] == {"command": "ls"}

    tool_ends = [e for e in out if e["type"] == "tool_end"]
    assert len(tool_ends) == 1
    # The result event only carries tool_use_id; the name is remembered
    # from the corresponding agent.tool_use event.
    assert tool_ends[0]["tool_name"] == "bash"
    assert tool_ends[0]["data"]["output"] == "file.txt"
    assert tool_ends[0]["data"]["error"] is None

    assert out[-1]["text"] == "Done"


@pytest.mark.asyncio
async def test_stream_maps_failed_tool_result_to_error_field():
    events = [
        _tool_use("bash", {"command": "rm /"}, event_id="ev_tool_2"),
        _tool_result("ev_tool_2", text="permission denied", is_error=True),
        _idle("end_turn"),
    ]
    runtime, _, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    tool_ends = [e for e in out if e["type"] == "tool_end"]
    assert tool_ends[0]["data"]["output"] is None
    assert tool_ends[0]["data"]["error"] == "permission denied"


@pytest.mark.asyncio
async def test_stream_maps_model_request_end_to_usage():
    events = [_msg("hi"), _usage_end(input_tokens=42, output_tokens=7),
              _idle("end_turn")]
    runtime, _, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    usage = [e for e in out if e["type"] == "usage"]
    assert len(usage) == 1
    assert usage[0]["data"]["input_tokens"] == 42
    assert usage[0]["data"]["output_tokens"] == 7


@pytest.mark.asyncio
async def test_stream_maps_context_compaction_to_custom_event():
    events = [_compacted(), _msg("ok"), _idle("end_turn")]
    runtime, _, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    custom = [e for e in out if e["type"] == "custom"]
    assert len(custom) == 1
    assert custom[0]["data"]["event"] == "context_compacted"


@pytest.mark.asyncio
async def test_stream_maps_session_error_and_stops():
    events = [_session_error("model exploded"),
              _msg("never reached"), _idle("end_turn")]
    runtime, client, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    errors = [e for e in out if e["type"] == "error"]
    assert errors == [{"type": "error", "error": "unknown_error: model exploded"}]
    # The stream breaks on session.error: the trailing message is not consumed.
    assert not [e for e in out if e["type"] == "text_delta"]
    assert out[-1]["type"] == "complete"
    assert out[-1]["text"] == ""
    # The stream is always closed, even on the error path.
    assert client.beta.sessions.events.streams[0].closed


@pytest.mark.asyncio
async def test_stream_maps_session_terminated_to_error():
    events = [_terminated()]
    runtime, _, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    errors = [e for e in out if e["type"] == "error"]
    assert len(errors) == 1
    assert "terminated" in errors[0]["error"]


# =============================================================================
# The idle-break gate
# =============================================================================

@pytest.mark.asyncio
async def test_idle_with_end_turn_completes_cleanly():
    """status_idle(end_turn) is THE terminal signal: the loop breaks (the
    trailing event is never consumed) and the turn completes without error."""
    events = [_msg("All done"), _idle("end_turn"),
              _msg("after idle — must not be consumed")]
    runtime, client, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    assert not [e for e in out if e["type"] == "error"]
    assert out[-1]["type"] == "complete"
    assert out[-1]["text"] == "All done"
    # Loop broke at the idle event — the post-idle message never streamed.
    yielded = [c[1] for c in client.log if c[0] == "stream.yield"]
    assert yielded == ["agent.message", "session.status_idle"]


@pytest.mark.asyncio
async def test_idle_with_requires_action_does_not_complete_cleanly():
    """status_idle(requires_action) means the session is blocked waiting on a
    client event this runtime cannot send (no custom tools / confirmations in
    v1) — it must surface an error, NOT a clean completion."""
    events = [_msg("partial"), _idle("requires_action")]
    runtime, _, ref = _make_runtime(events)

    out = await _collect(runtime, ref)

    errors = [e for e in out if e["type"] == "error"]
    assert len(errors) == 1
    assert "requires_action" in errors[0]["error"]


# =============================================================================
# Stream-first ordering + message composition
# =============================================================================

@pytest.mark.asyncio
async def test_stream_opens_event_stream_before_sending_message():
    """The SSE stream has no replay: events.stream MUST be opened before
    events.send, or the earliest events of the turn can be dropped."""
    events = [_msg("hi"), _idle("end_turn")]
    runtime, client, ref = _make_runtime(events)

    await _collect(runtime, ref, message="ping")

    ops = [c[0] for c in client.log]
    assert "events.stream" in ops and "events.send" in ops
    assert ops.index("events.stream") < ops.index("events.send")


@pytest.mark.asyncio
async def test_stream_sends_user_message_event_shape():
    events = [_idle("end_turn")]
    runtime, client, ref = _make_runtime(events)

    await _collect(runtime, ref, message="what time is it?")

    send = next(c for c in client.log if c[0] == "events.send")
    assert send[1] == "sesn_test123"
    sent_events = send[2]
    assert sent_events == [{
        "type": "user.message",
        "content": [{"type": "text", "text": "what time is it?"}],
    }]


@pytest.mark.asyncio
async def test_stream_prepends_rag_context_to_first_message_only():
    events = [_idle("end_turn")]
    runtime, client, ref = _make_runtime(events)
    runtime._pending_context[ref.session_id] = "RAG facts here"

    await _collect(runtime, ref, message="question one")

    first = next(c for c in client.log if c[0] == "events.send")
    first_text = first[2][0]["content"][0]["text"]
    assert first_text == "<context>\nRAG facts here\n</context>\n\nquestion one"

    # Second turn: the pending context was consumed — sent verbatim.
    client.beta.sessions.events._events = [_idle("end_turn")]
    await _collect(runtime, ref, message="question two")
    second = [c for c in client.log if c[0] == "events.send"][1]
    assert second[2][0]["content"][0]["text"] == "question two"


@pytest.mark.asyncio
async def test_stream_without_create_session_raises():
    runtime = AnthropicManagedRuntime()
    ref = RuntimeSessionRef(runtime="anthropic_managed", session_id="missing")
    with pytest.raises(RuntimeError, match="create_session"):
        async for _ in runtime.stream(ref, "hi"):
            pass


# =============================================================================
# prepare_template: create-then-update with external_refs
# =============================================================================

@pytest.mark.asyncio
async def test_prepare_template_first_save_creates_agent(stub_system_prompt):
    runtime, client, _ = _make_runtime()
    template = SimpleNamespace(name="My Research Agent!", external_refs=None)

    refs = await runtime.prepare_template(template, dict(VALID_CONFIG))

    assert refs == {
        "anthropic_agent_id": "agent_abc",
        "anthropic_agent_version": 1,
    }
    creates = [c for c in client.log if c[0] == "agents.create"]
    assert len(creates) == 1
    assert creates[0][1]["model"] == "claude-sonnet-4-6"
    assert creates[0][1]["system"] == "STUBBED PROMPT"
    assert creates[0][1]["tools"] == AGENT_TOOLSET
    # Name is slugged to Anthropic's allowed charset.
    assert creates[0][1]["name"] == "My Research Agent"
    # No update on first save.
    assert not [c for c in client.log if c[0] == "agents.update"]


@pytest.mark.asyncio
async def test_prepare_template_resave_updates_with_fresh_version(stub_system_prompt):
    """Later saves update in place using the CURRENT version retrieved from
    the API as the optimistic lock — never the (possibly stale) stored one."""
    runtime, client, _ = _make_runtime(agent_version=3)
    template = SimpleNamespace(
        name="My Agent",
        external_refs={
            "anthropic_agent_id": "agent_abc",
            "anthropic_agent_version": 1,  # stale on purpose
        },
    )

    refs = await runtime.prepare_template(template, dict(VALID_CONFIG))

    # retrieve happened before update, and update used the fresh version.
    ops = [c[0] for c in client.log]
    assert ops.index("agents.retrieve") < ops.index("agents.update")
    update = next(c for c in client.log if c[0] == "agents.update")
    assert update[1]["agent_id"] == "agent_abc"
    assert update[1]["version"] == 3
    assert update[1]["tools"] == AGENT_TOOLSET

    assert refs == {
        "anthropic_agent_id": "agent_abc",
        "anthropic_agent_version": 4,  # new immutable version
    }
    assert not [c for c in client.log if c[0] == "agents.create"]


# =============================================================================
# Claude-only gating
# =============================================================================

@pytest.mark.asyncio
async def test_prepare_template_rejects_non_claude_models(stub_system_prompt):
    runtime, client, _ = _make_runtime()
    template = SimpleNamespace(name="X", external_refs=None)
    with pytest.raises(ValueError, match="only supports Claude"):
        await runtime.prepare_template(
            template, {"system_prompt": "hi", "model": "gemini-2.5-flash"}
        )
    assert client.log == []  # gate fires before any API call


@pytest.mark.asyncio
async def test_create_session_rejects_non_claude_models():
    runtime, client, _ = _make_runtime()
    with pytest.raises(ValueError, match="only supports Claude"):
        await runtime.create_session(
            config={"system_prompt": "hi", "model": "gpt-5.2"},
            session_id="sid-gate",
        )
    assert "sid-gate" not in runtime._sessions
    assert client.log == []


# =============================================================================
# create_session
# =============================================================================

@pytest.mark.asyncio
async def test_create_session_requires_provisioned_agent_refs(monkeypatch):
    """The chat path never creates agents: a template that was not saved with
    runtime='anthropic_managed' (no external_refs) is rejected."""
    runtime, client, _ = _make_runtime()
    monkeypatch.setattr(runtime, "_load_external_ref", _none_async())

    with pytest.raises(ValueError, match="anthropic_agent_id"):
        await runtime.create_session(config=dict(VALID_CONFIG), session_id="sid-2")
    assert not [c for c in client.log if c[0] == "sessions.create"]


@pytest.mark.asyncio
async def test_create_session_creates_session_from_template_refs(monkeypatch):
    runtime, client, _ = _make_runtime()
    monkeypatch.setattr(runtime, "_load_external_ref", _none_async())
    stored = {}

    async def _store(session_id, external_ref):
        stored[session_id] = external_ref

    monkeypatch.setattr(runtime, "_store_external_ref", _store)

    config = dict(VALID_CONFIG)
    config["external_refs"] = {"anthropic_agent_id": "agent_abc"}

    ref = await runtime.create_session(
        config=config, session_id="sid-3", context="RAG context"
    )

    assert ref.runtime == "anthropic_managed"
    assert ref.session_id == "sid-3"
    assert ref.external_ref == "sesn_test123"

    create = next(c for c in client.log if c[0] == "sessions.create")
    assert create[1]["agent"] == "agent_abc"
    assert create[1]["environment_id"] == "env_test"

    # Anthropic session id persisted for restart recovery; context parked
    # for the first user message.
    assert stored == {"sid-3": "sesn_test123"}
    assert runtime._pending_context["sid-3"] == "RAG context"

    # Repeat call is cache-first: no second remote session.
    ref2 = await runtime.create_session(config=config, session_id="sid-3")
    assert ref2.external_ref == "sesn_test123"
    assert len([c for c in client.log if c[0] == "sessions.create"]) == 1


def _none_async():
    async def _load(session_id):
        return None
    return _load


# =============================================================================
# destroy_session: poll-until-settled, then archive the SESSION only
# =============================================================================

@pytest.mark.asyncio
async def test_destroy_session_polls_until_not_running_then_archives():
    runtime, client, ref = _make_runtime(
        statuses=["running", "running", "idle"]
    )
    runtime._sessions[ref.session_id] = "sesn_test123"
    runtime._pending_context[ref.session_id] = "stale"

    result = await runtime.destroy_session(ref)

    assert result is True
    retrieves = [c for c in client.log if c[0] == "sessions.retrieve"]
    assert len(retrieves) == 3  # kept polling through the 'running' reads
    archives = [c for c in client.log if c[0] == "sessions.archive"]
    assert archives == [("sessions.archive", "sesn_test123")]
    # Archive happened only after the status settled.
    ops = [c[0] for c in client.log]
    assert ops.index("sessions.archive") > ops.index("sessions.retrieve")
    # The AGENT is never archived (that operation is permanent).
    assert not [c for c in client.log if c[0] == "agents.archive"]
    # Local state cleaned up.
    assert ref.session_id not in runtime._sessions
    assert ref.session_id not in runtime._pending_context


@pytest.mark.asyncio
async def test_destroy_session_skips_archive_while_still_running():
    runtime, client, ref = _make_runtime(statuses=["running"])

    result = await runtime.destroy_session(ref)

    assert result is False
    retrieves = [c for c in client.log if c[0] == "sessions.retrieve"]
    assert len(retrieves) == AnthropicManagedRuntime.ARCHIVE_POLL_ATTEMPTS
    assert not [c for c in client.log if c[0] == "sessions.archive"]


@pytest.mark.asyncio
async def test_destroy_session_without_remote_session_is_noop():
    runtime, client, _ = _make_runtime()
    ref = RuntimeSessionRef(
        runtime="anthropic_managed", session_id="sid-local", external_ref=None
    )
    assert await runtime.destroy_session(ref) is True
    assert client.log == []


# =============================================================================
# Misc unit coverage
# =============================================================================

def test_slug_agent_name_strips_disallowed_characters():
    assert _slug_agent_name("My Agent! (v2) ##") == "My Agent- -v2"
    assert _slug_agent_name(None) == "langconfig-agent"
    assert _slug_agent_name("   ") == "langconfig-agent"
    assert len(_slug_agent_name("x" * 500)) == 256


def test_capabilities_advertise_hosted_constraints():
    runtime = AnthropicManagedRuntime()
    assert runtime.capabilities.streaming is True
    assert runtime.capabilities.hitl is False
    assert runtime.capabilities.custom_tools is False
    assert runtime.capabilities.checkpoint_resume is True


def test_registry_resolves_anthropic_managed_runtime():
    runtime = get_runtime("anthropic_managed")
    assert isinstance(runtime, AnthropicManagedRuntime)
    assert runtime.name == "anthropic_managed"
    # Same instance on repeat lookups (registry caches singletons).
    assert get_runtime("anthropic_managed") is runtime
