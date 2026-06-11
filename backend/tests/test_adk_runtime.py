# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the Google ADK runtime (core/runtimes/adk_runtime.py).

The ADK Runner is replaced with a fake that replays REAL google.adk Event
objects (constructed via the installed google-adk package), so the event
mapping is exercised against the actual Event/Part schemas:

- partial text chunks       -> text_delta
- thought parts             -> thinking_delta
- function_call parts       -> tool_start
- function_response parts   -> tool_end
- final aggregated text     -> deduped (no double emission)
- usage_metadata            -> usage
- error_code/error_message  -> error
- gemini-only model gating  -> ValueError from create_session/prepare_template
- LangchainTool wrap errors -> tool skipped, others kept
"""

import pytest

from google.adk.events import Event
from google.genai import types as genai_types
from langchain_core.tools import tool as lc_tool

import core.runtimes.adk_runtime as adk_runtime_module
from core.runtimes import get_runtime
from core.runtimes.adk_runtime import GoogleADKRuntime
from core.runtimes.base import RuntimeSessionRef


# =============================================================================
# Helpers
# =============================================================================

class FakeRunner:
    """Stands in for google.adk.runners.Runner; replays canned Events."""

    def __init__(self, events):
        self._events = events
        self.calls = []

    def run_async(self, **kwargs):
        self.calls.append(kwargs)

        async def _gen():
            for event in self._events:
                yield event

        return _gen()


def _event(parts=None, partial=None, usage=None, error_code=None,
           error_message=None, author="model"):
    content = None
    if parts is not None:
        content = genai_types.Content(role="model", parts=parts)
    return Event(
        author=author,
        content=content,
        partial=partial,
        usage_metadata=usage,
        error_code=error_code,
        error_message=error_message,
    )


def _text(text, thought=None):
    return genai_types.Part(text=text, thought=thought)


async def _collect(runtime, ref, message="hi"):
    return [event async for event in runtime.stream(ref, message)]


def _make_runtime_with_events(events, session_id="sid-1"):
    runtime = GoogleADKRuntime()
    runner = FakeRunner(events)
    runtime._runners[session_id] = runner
    ref = RuntimeSessionRef(
        runtime="google_adk", session_id=session_id, external_ref=session_id
    )
    return runtime, runner, ref


# =============================================================================
# Event mapping
# =============================================================================

@pytest.mark.asyncio
async def test_stream_maps_partial_text_and_dedupes_final_aggregate():
    """Partial chunks stream as text_delta; the aggregated final event that
    repeats the same text must NOT be re-emitted (the documented ADK SSE
    duplicate-text behavior)."""
    usage = genai_types.GenerateContentResponseUsageMetadata(
        prompt_token_count=10, candidates_token_count=5, total_token_count=15
    )
    events = [
        _event([_text("Hel")], partial=True),
        _event([_text("lo!")], partial=True),
        _event([_text("Hello!")], partial=None, usage=usage),  # aggregated
    ]
    runtime, _, ref = _make_runtime_with_events(events)

    out = await _collect(runtime, ref)

    text_deltas = [e["text"] for e in out if e["type"] == "text_delta"]
    assert text_deltas == ["Hel", "lo!"], "final aggregate must be deduped"

    complete = out[-1]
    assert complete["type"] == "complete"
    assert complete["text"] == "Hello!"
    assert complete["data"] == {
        "artifacts": [], "content_blocks": [], "has_multimodal": False,
    }

    usage_events = [e for e in out if e["type"] == "usage"]
    assert len(usage_events) == 1
    assert usage_events[0]["data"]["total_token_count"] == 15


@pytest.mark.asyncio
async def test_stream_emits_remainder_when_final_extends_partials():
    """If the aggregated event contains MORE text than was streamed, only the
    missing tail is emitted (complete.text == sum of text_deltas)."""
    events = [
        _event([_text("Hello")], partial=True),
        _event([_text("Hello world")], partial=None),
    ]
    runtime, _, ref = _make_runtime_with_events(events)

    out = await _collect(runtime, ref)

    text_deltas = [e["text"] for e in out if e["type"] == "text_delta"]
    assert text_deltas == ["Hello", " world"]
    assert out[-1]["text"] == "Hello world"


@pytest.mark.asyncio
async def test_stream_final_only_text_emitted_once():
    """With no partial chunks (e.g. progressive streaming off), the final
    text is emitted as a single text_delta."""
    events = [_event([_text("Just the final.")], partial=None)]
    runtime, _, ref = _make_runtime_with_events(events)

    out = await _collect(runtime, ref)

    text_deltas = [e["text"] for e in out if e["type"] == "text_delta"]
    assert text_deltas == ["Just the final."]
    assert out[-1]["text"] == "Just the final."


@pytest.mark.asyncio
async def test_stream_maps_thought_parts_to_thinking_delta():
    """Thought parts stream as thinking_delta and never leak into the
    assistant content (complete.text)."""
    events = [
        _event([_text("pondering...", thought=True)], partial=True),
        _event([_text("Answer")], partial=True),
        _event(
            [_text("pondering...", thought=True), _text("Answer")],
            partial=None,
        ),
    ]
    runtime, _, ref = _make_runtime_with_events(events)

    out = await _collect(runtime, ref)

    thinking = [e["text"] for e in out if e["type"] == "thinking_delta"]
    assert thinking == ["pondering..."]
    text_deltas = [e["text"] for e in out if e["type"] == "text_delta"]
    assert text_deltas == ["Answer"]
    assert out[-1]["text"] == "Answer"


@pytest.mark.asyncio
async def test_stream_maps_function_call_and_response_to_tool_events():
    events = [
        _event([genai_types.Part(
            function_call=genai_types.FunctionCall(
                name="web_search", args={"query": "adk"}
            )
        )]),
        _event([genai_types.Part(
            function_response=genai_types.FunctionResponse(
                name="web_search", response={"result": "found it"}
            )
        )]),
        _event([_text("Done")], partial=None),
    ]
    runtime, _, ref = _make_runtime_with_events(events)

    out = await _collect(runtime, ref)

    tool_starts = [e for e in out if e["type"] == "tool_start"]
    assert len(tool_starts) == 1
    assert tool_starts[0]["tool_name"] == "web_search"
    assert tool_starts[0]["data"]["input"] == {"query": "adk"}

    tool_ends = [e for e in out if e["type"] == "tool_end"]
    assert len(tool_ends) == 1
    assert tool_ends[0]["tool_name"] == "web_search"
    assert tool_ends[0]["data"]["output"] == {"result": "found it"}
    assert tool_ends[0]["data"]["error"] is None

    assert out[-1]["type"] == "complete"
    assert out[-1]["text"] == "Done"


@pytest.mark.asyncio
async def test_stream_maps_error_events():
    events = [
        _event(error_code="RESOURCE_EXHAUSTED", error_message="quota exceeded"),
    ]
    runtime, _, ref = _make_runtime_with_events(events)

    out = await _collect(runtime, ref)

    errors = [e for e in out if e["type"] == "error"]
    assert errors == [
        {"type": "error", "error": "RESOURCE_EXHAUSTED: quota exceeded"}
    ]
    # Still terminates with a (empty) complete event for the route.
    assert out[-1]["type"] == "complete"
    assert out[-1]["text"] == ""


@pytest.mark.asyncio
async def test_stream_passes_session_ref_and_sse_mode_to_runner():
    from google.adk.agents.run_config import StreamingMode

    events = [_event([_text("ok")], partial=None)]
    runtime, runner, ref = _make_runtime_with_events(events, session_id="sess-42")

    await _collect(runtime, ref, message="ping")

    assert len(runner.calls) == 1
    call = runner.calls[0]
    assert call["session_id"] == "sess-42"
    assert call["user_id"] == adk_runtime_module.ADK_USER_ID
    assert call["run_config"].streaming_mode == StreamingMode.SSE
    assert call["new_message"].parts[0].text == "ping"


@pytest.mark.asyncio
async def test_stream_without_create_session_raises():
    runtime = GoogleADKRuntime()
    ref = RuntimeSessionRef(runtime="google_adk", session_id="missing")
    with pytest.raises(RuntimeError, match="create_session"):
        async for _ in runtime.stream(ref, "hi"):
            pass


# =============================================================================
# Gemini-only gating
# =============================================================================

@pytest.mark.asyncio
async def test_create_session_rejects_non_gemini_models():
    runtime = GoogleADKRuntime()
    with pytest.raises(ValueError, match="only supports Gemini"):
        await runtime.create_session(
            config={"system_prompt": "You are helpful", "model": "claude-sonnet-4-6"},
            session_id="sid-gate",
        )
    # Nothing was cached for the rejected session.
    assert "sid-gate" not in runtime._runners


@pytest.mark.asyncio
async def test_prepare_template_rejects_non_gemini_models():
    runtime = GoogleADKRuntime()
    with pytest.raises(ValueError, match="only supports Gemini"):
        await runtime.prepare_template(
            template_row=None,
            config={"system_prompt": "You are helpful", "model": "gpt-5.2"},
        )


@pytest.mark.asyncio
async def test_prepare_template_accepts_gemini_models():
    runtime = GoogleADKRuntime()
    result = await runtime.prepare_template(
        template_row=None,
        config={"system_prompt": "You are helpful", "model": "gemini-2.5-flash"},
    )
    assert result["model"] == "gemini-2.5-flash"
    assert result["system_prompt"] == "You are helpful"


# =============================================================================
# LangchainTool wrap resilience
# =============================================================================

def test_wrap_tools_skips_failures_and_keeps_good_tools(monkeypatch):
    @lc_tool
    def good_tool(query: str) -> str:
        """A perfectly fine tool."""
        return query

    @lc_tool
    def bad_tool(query: str) -> str:
        """A tool whose ADK adaptation explodes."""
        return query

    real_langchain_tool = adk_runtime_module.LangchainTool

    def flaky_wrapper(tool, *args, **kwargs):
        if getattr(tool, "name", "") == "bad_tool":
            raise ValueError("unsupported schema")
        return real_langchain_tool(tool, *args, **kwargs)

    monkeypatch.setattr(adk_runtime_module, "LangchainTool", flaky_wrapper)

    wrapped = GoogleADKRuntime._wrap_tools([good_tool, bad_tool])

    assert len(wrapped) == 1
    assert wrapped[0].name == "good_tool"


def test_wrap_tools_real_langchain_tool_roundtrip():
    """LangchainTool from google-adk 1.22.1 actually accepts our BaseTools."""
    @lc_tool
    def echo(text: str) -> str:
        """Echo the input text."""
        return text

    wrapped = GoogleADKRuntime._wrap_tools([echo])
    assert len(wrapped) == 1
    assert wrapped[0].name == "echo"
    assert wrapped[0].description == "Echo the input text."


# =============================================================================
# Registry integration
# =============================================================================

def test_registry_resolves_google_adk_runtime():
    runtime = get_runtime("google_adk")
    assert isinstance(runtime, GoogleADKRuntime)
    assert runtime.name == "google_adk"
    assert runtime.capabilities.streaming is True
    assert runtime.capabilities.hitl is False
    # Same instance on repeat lookups (registry caches singletons).
    assert get_runtime("google_adk") is runtime
