# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Regression tests for the chat SSE streaming contract.

The chat endpoint iterates `agent.astream_events(...)` directly with
`async for`. Pregel's `version="v3"` is an experimental API that returns an
awaitable AsyncGraphRunStream instead of an async iterator, so passing v3
breaks every chat prompt with:

    'async for' requires an object with __aiter__ method, got coroutine

(introduced in 071e51a, fixed by pinning the call to version="v2").
"""
from pathlib import Path
from typing import TypedDict

import pytest

from langgraph.graph import StateGraph, START, END

CHAT_ROUTES = Path(__file__).resolve().parents[1] / "api" / "chat" / "routes.py"


class _State(TypedDict, total=False):
    x: int


def _minimal_graph():
    def node(state: _State):
        return {"x": 1}

    g = StateGraph(_State)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    return g.compile()


@pytest.mark.asyncio
async def test_astream_events_v2_is_directly_async_iterable():
    """The contract the chat route depends on: v2 yields StreamEvent dicts."""
    graph = _minimal_graph()
    events = []
    async for event in graph.astream_events({}, version="v2"):
        events.append(event)
    assert events, "v2 must yield at least one event"
    assert all("event" in e for e in events), "v2 events carry an 'event' key"


@pytest.mark.asyncio
async def test_astream_events_v3_is_not_async_iterable():
    """Documents WHY the chat route must not pass version='v3' to async for."""
    graph = _minimal_graph()
    with pytest.raises(TypeError, match="__aiter__"):
        async for _ in graph.astream_events({}, version="v3"):
            pass  # pragma: no cover


def test_chat_route_does_not_use_stream_events_v3():
    """Guard: reintroducing version='v3' in the chat route breaks every chat
    prompt unless the consumption code is rewritten for AsyncGraphRunStream."""
    source = CHAT_ROUTES.read_text(encoding="utf-8")
    assert 'version="v3"' not in source and "version='v3'" not in source, (
        "api/chat/routes.py uses astream_events version='v3', which returns an "
        "awaitable AsyncGraphRunStream, not an async iterator - 'async for' "
        "over it raises TypeError on every chat prompt. Use version='v2' or "
        "rewrite the consumer for the v3 API."
    )
