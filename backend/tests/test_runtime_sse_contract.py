# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SSE contract gate for the AgentRuntime refactor.

This test drives the chat streaming endpoint (POST /api/chat/message/stream)
with a fully mocked agent whose ``astream_events`` replays a recorded v2 event
sequence covering every frame type the UI consumes:

- text chunks with plain ``str`` content
- text chunks with list-of-content-blocks content (Anthropic style)
- a thinking block (thinking_delta)
- tool start / tool end
- a tool artifact (image) flushed after tool end
- a custom event
- the final ``complete`` frame

The SSE frames produced by the endpoint were recorded BEFORE the runtime
refactor into ``tests/fixtures/chat_sse_contract.json`` (golden file). After
the refactor the endpoint must emit byte-identical frames. If the golden file
is missing the test records it (recording mode) and fails, so a fresh checkout
can never silently regenerate the contract.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from api.chat.routes import SendMessageRequest, send_message_stream
from core.workflows.events.emitter import ExecutionEventCallbackHandler
from services.deepagent_factory import DeepAgentFactory

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "chat_sse_contract.json"

SESSION_ID = "sse-contract-test-session"

ARTIFACT = {
    "type": "image",
    "data": "aGVsbG8=",
    "mimeType": "image/png",
    "tool_name": "calculator",
    "agent_label": "main",
}


def _chunk(content: Any) -> Dict[str, Any]:
    """A v2 on_chat_model_stream event whose chunk carries ``content``."""
    return {"event": "on_chat_model_stream", "data": {"chunk": SimpleNamespace(content=content)}}


# Recorded astream_events(version="v2") sequence the fake agent replays.
RECORDED_EVENTS: List[Dict[str, Any]] = [
    _chunk("Hello "),  # plain str content
    _chunk([
        {"type": "text", "text": "from "},
        {"type": "text", "text": "blocks"},
    ]),  # list-of-blocks content (flattened to one token)
    _chunk([{"type": "thinking", "thinking": "Considering the question..."}]),  # thinking
    {"event": "on_tool_start", "name": "calculator", "data": {"input": {"expression": "6*7"}}},
    {"event": "on_tool_end", "name": "calculator", "data": {"output": "42"}},
    {"event": "on_custom_event", "data": {"progress": 0.5, "label": "halfway"}},
    _chunk("Final."),
]


class FakeAgent:
    """Stands in for the CompiledStateGraph returned by DeepAgentFactory."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def astream_events(self, input: Any, config: Any = None, version: str = None, **kwargs):
        self.calls.append({"input": input, "config": config, "version": version})

        async def _gen():
            for event in RECORDED_EVENTS:
                yield event

        return _gen()


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result

    def all(self):
        return []


class FakeDB:
    """Minimal stand-in for a SQLAlchemy Session used by the chat routes."""

    def __init__(self, session_obj, agent_obj):
        self._session_obj = session_obj
        self._agent_obj = agent_obj

    def query(self, model):
        name = getattr(model, "__name__", str(model))
        if name == "ChatSession":
            return FakeQuery(self._session_obj)
        if name == "DeepAgentTemplate":
            return FakeQuery(self._agent_obj)
        return FakeQuery(None)

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def rollback(self):
        pass


def _fake_session():
    return SimpleNamespace(
        session_id=SESSION_ID,
        agent_id=1,
        project_id=None,  # keeps the RAG retrieval path disabled (hermetic test)
        is_active=True,
        messages=[],
        metrics={},
        runtime="langgraph",
    )


def _fake_agent_row():
    return SimpleNamespace(
        id=1,
        name="Contract Test Agent",
        project_id=None,
        config={"system_prompt": "You are a test agent."},
        runtime="langgraph",
    )


@pytest.fixture
def fake_agent(monkeypatch):
    agent = FakeAgent()

    async def fake_create_deep_agent(config, project_id, task_id, context,
                                     mcp_manager=None, vector_store=None, **kwargs):
        return agent, [], []

    monkeypatch.setattr(DeepAgentFactory, "create_deep_agent", fake_create_deep_agent)

    # The artifact flush after tool_end reads the (real) callback handler's
    # collected artifacts. Tool callbacks never fire with a fake agent, so
    # inject a canned artifact at the class level.
    monkeypatch.setattr(
        ExecutionEventCallbackHandler,
        "get_collected_artifacts",
        lambda self: [dict(ARTIFACT)],
    )

    # flag_modified needs SQLAlchemy-instrumented instances; the fakes aren't.
    import sqlalchemy.orm.attributes as sa_attributes
    monkeypatch.setattr(sa_attributes, "flag_modified", lambda instance, key: None)

    # Force a fresh agent build (no cross-test cache hits) and a no-op cache.
    from services.chat_session_manager import get_session_manager
    manager = get_session_manager()
    manager.remove_session(SESSION_ID)

    import api.chat.routes as chat_routes
    chat_routes.active_agents.pop(SESSION_ID, None)

    return agent


async def _collect_frames(db) -> List[str]:
    """Invoke the streaming endpoint directly and drain the SSE body."""
    request = SendMessageRequest(session_id=SESSION_ID, message="run the contract", enable_hitl=False)
    response = await send_message_stream(request, db=db)
    frames: List[str] = []
    async for raw in response.body_iterator:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        frames.append(raw)
    return frames


def _parse_frames(frames: List[str]) -> List[Dict[str, Any]]:
    parsed = []
    for frame in frames:
        assert frame.startswith("data: ") and frame.endswith("\n\n"), f"malformed SSE frame: {frame!r}"
        parsed.append(json.loads(frame[len("data: "):-2]))
    return parsed


@pytest.mark.asyncio
async def test_chat_sse_frames_match_pre_refactor_golden_fixture(fake_agent):
    session_obj = _fake_session()
    db = FakeDB(session_obj, _fake_agent_row())

    frames = await _collect_frames(db)

    if not FIXTURE_PATH.exists():
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(json.dumps(frames, indent=2), encoding="utf-8")
        pytest.fail(
            f"Golden fixture was missing; recorded {len(frames)} frames to {FIXTURE_PATH}. "
            "Re-run the test to verify against the recorded contract."
        )

    golden: List[str] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    # Byte-identical SSE output (frames carry no timestamps).
    assert frames == golden, (
        "SSE stream diverged from the pre-refactor recording.\n"
        f"got:    {json.dumps(frames, indent=2)}\n"
        f"golden: {json.dumps(golden, indent=2)}"
    )


@pytest.mark.asyncio
async def test_chat_sse_frame_semantics_and_agent_invocation(fake_agent):
    """Structural assertions independent of the golden file."""
    session_obj = _fake_session()
    db = FakeDB(session_obj, _fake_agent_row())

    parsed = _parse_frames(await _collect_frames(db))
    types = [frame["type"] for frame in parsed]

    assert types == [
        "chunk",          # "Hello "
        "chunk",          # "from blocks" (list content flattened)
        "thinking",       # thinking block
        "tool_start",
        "tool_end",
        "tool_artifact",  # flushed after tool_end
        "custom_event",
        "chunk",          # "Final."
        "complete",
    ]

    assert parsed[0]["content"] == "Hello "
    assert parsed[1]["content"] == "from blocks"
    assert parsed[2]["content"] == "Considering the question..."

    assert parsed[3]["tool_name"] == "calculator"
    assert parsed[3]["data"]["input"] == {"expression": "6*7"}
    assert parsed[4]["tool_name"] == "calculator"
    assert parsed[4]["data"]["output"] == "42"

    assert parsed[5]["tool_name"] == "calculator"
    assert parsed[5]["artifact"] == ARTIFACT

    assert parsed[6]["data"] == {"progress": 0.5, "label": "halfway"}

    complete = parsed[-1]
    assert complete["content"] == "Hello from blocksFinal."
    assert complete["artifacts"] == [ARTIFACT]
    assert complete["content_blocks"] == [ARTIFACT]
    assert complete["has_multimodal"] is True

    # The LangGraph invocation contract must survive the refactor.
    assert len(fake_agent.calls) == 1
    call = fake_agent.calls[0]
    assert call["version"] == "v2"
    assert call["config"]["recursion_limit"] == 500
    assert call["config"]["configurable"]["thread_id"] == SESSION_ID
    assert call["config"]["configurable"]["enable_hitl"] is False
    assert call["input"]["messages"][0].content == "run the contract"

    # DB persistence stays in the route: user + assistant message appended.
    assert len(session_obj.messages) == 2
    user_msg, assistant_msg = session_obj.messages
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "run the contract"
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["content"] == "Hello from blocksFinal."
    assert assistant_msg["thinking"] == "Considering the question..."
    assert assistant_msg["artifacts"] == [ARTIFACT]
    assert assistant_msg["has_multimodal"] is True
