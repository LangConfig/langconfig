# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for HITL pause/resume via LangGraph interrupt() + Command(resume=...).

Uses a minimal StateGraph with an InMemorySaver checkpointer (no DB required)
to verify the executor's pause-detection helper and the resume contract used
by APPROVAL_NODE.
"""
from typing import Optional, TypedDict

import pytest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

from core.workflows.executor import detect_pending_interrupt


class _ApprovalState(TypedDict, total=False):
    decision: Optional[str]
    workflow_status: Optional[str]
    done: bool


def _build_graph():
    """Minimal graph mirroring the APPROVAL_NODE pattern in the executor."""

    def approval_node(state: _ApprovalState):
        decision = interrupt({
            "type": "approval_required",
            "message": "Please review and approve before continuing.",
        })
        if decision == "reject":
            return {"decision": decision, "workflow_status": "REJECTED"}
        return {"decision": decision, "workflow_status": "APPROVED"}

    def finish_node(state: _ApprovalState):
        return {"done": True}

    graph = StateGraph(_ApprovalState)
    graph.add_node("approval", approval_node)
    graph.add_node("finish", finish_node)
    graph.add_edge(START, "approval")
    graph.add_edge("approval", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=InMemorySaver())


async def _drain_events(graph, stream_input, config):
    """Consume astream_events exactly like the executor's main loop does."""
    async for _ in graph.astream_events(stream_input, config=config, version="v2"):
        pass


@pytest.mark.asyncio
async def test_first_run_pauses_and_interrupt_is_detected():
    graph = _build_graph()
    config = {"configurable": {"thread_id": "hitl-test-pause"}}

    await _drain_events(graph, {}, config)

    snapshot = await graph.aget_state(config)
    assert snapshot.next, "Graph should have a pending node after interrupt()"

    payload = detect_pending_interrupt(snapshot)
    assert payload is not None
    assert payload["type"] == "approval_required"
    assert "message" in payload


@pytest.mark.asyncio
async def test_resume_with_approve_completes_workflow():
    graph = _build_graph()
    config = {"configurable": {"thread_id": "hitl-test-approve"}}

    # First run pauses at the approval node
    await _drain_events(graph, {}, config)
    assert detect_pending_interrupt(await graph.aget_state(config)) is not None

    # Resume with approval - graph should run to completion
    await _drain_events(graph, Command(resume="approve"), config)

    snapshot = await graph.aget_state(config)
    assert not snapshot.next, "Graph should have no pending nodes after resume"
    assert detect_pending_interrupt(snapshot) is None
    assert snapshot.values["decision"] == "approve"
    assert snapshot.values["workflow_status"] == "APPROVED"
    assert snapshot.values["done"] is True


@pytest.mark.asyncio
async def test_resume_with_reject_runs_reject_branch():
    graph = _build_graph()
    config = {"configurable": {"thread_id": "hitl-test-reject"}}

    await _drain_events(graph, {}, config)
    assert detect_pending_interrupt(await graph.aget_state(config)) is not None

    # Resume with rejection - graph terminates cleanly through the reject branch
    await _drain_events(graph, Command(resume="reject"), config)

    snapshot = await graph.aget_state(config)
    assert not snapshot.next
    assert detect_pending_interrupt(snapshot) is None
    assert snapshot.values["decision"] == "reject"
    assert snapshot.values["workflow_status"] == "REJECTED"


def test_detect_pending_interrupt_handles_none_and_completed_snapshots():
    assert detect_pending_interrupt(None) is None

    class _FakeSnapshot:
        next = ()
        tasks = ()

    assert detect_pending_interrupt(_FakeSnapshot()) is None


def test_detect_pending_interrupt_wraps_non_dict_payloads():
    class _FakeInterrupt:
        value = "plain-string-payload"

    class _FakeTask:
        interrupts = (_FakeInterrupt(),)

    class _FakeSnapshot:
        next = ("approval",)
        tasks = (_FakeTask(),)

    payload = detect_pending_interrupt(_FakeSnapshot())
    assert payload == {"value": "plain-string-payload"}
