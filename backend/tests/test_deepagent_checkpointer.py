# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Regression tests for DeepAgent checkpointer attachment (chat memory).

deepagents 0.6.x adds TodoListMiddleware/FilesystemMiddleware to every deep
agent by default. When DeepAgentFactory also appended its own instances,
create_agent raised "Please remove duplicate middleware instances" and the
factory silently fell back to AgentFactory - whose agents have NO checkpointer.
Result: every chat session lost conversation memory and zero rows were ever
written to the checkpoints tables.

These tests pin the contract: the deepagents path must succeed (no fallback)
and the compiled agent must carry the checkpointer returned by
get_checkpointer().
"""
import pytest

import core.workflows.checkpointing.manager as checkpoint_manager
from langgraph.checkpoint.memory import InMemorySaver

from models.deep_agent import DeepAgentConfig
from services.deepagent_factory import DeepAgentFactory


@pytest.fixture
def fake_checkpointer(monkeypatch):
    """Install an InMemorySaver as the global checkpointer (no DB needed)."""
    saver = InMemorySaver()
    monkeypatch.setattr(checkpoint_manager, "_checkpointer", saver)
    # Model construction must not require a real key (no API call is made)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    return saver


@pytest.mark.asyncio
async def test_deep_agent_carries_checkpointer(fake_checkpointer):
    """The compiled chat agent must have the checkpointer attached - this is
    what makes thread_id-scoped conversation memory work."""
    cfg = DeepAgentConfig(
        agent_name="checkpointer-probe",
        model="claude-haiku-4-5-20251001",
        system_prompt="You are a test agent.",
        tools=[],
    )
    agent, _tools, _callbacks = await DeepAgentFactory.create_deep_agent(
        config=cfg,
        project_id=0,
        task_id=0,
        context="",
        mcp_manager=None,
        vector_store=None,
    )

    attached = getattr(agent, "checkpointer", None)
    assert attached is not None, (
        "Deep agent compiled WITHOUT a checkpointer - chat sessions will have "
        "no conversation memory. Most likely create_deep_agent raised (e.g. "
        "duplicate middleware) and the factory silently fell back to "
        "AgentFactory. Check the 'Error creating DeepAgent' log."
    )


@pytest.mark.asyncio
async def test_deep_agent_does_not_duplicate_harness_middleware(fake_checkpointer):
    """deepagents supplies TodoList/Filesystem middleware itself; the factory
    must not append its own instances (create_agent asserts uniqueness)."""
    from models.deep_agent import MiddlewareConfig
    from models.enums import MiddlewareType

    cfg = DeepAgentConfig(
        agent_name="middleware-probe",
        model="claude-haiku-4-5-20251001",
        system_prompt="You are a test agent.",
        tools=[],
        middleware=[
            MiddlewareConfig(type=MiddlewareType.TODO_LIST, enabled=True),
        ],
    )
    # Must not raise and must not fall back (fallback has no checkpointer)
    agent, _tools, _callbacks = await DeepAgentFactory.create_deep_agent(
        config=cfg,
        project_id=0,
        task_id=0,
        context="",
        mcp_manager=None,
        vector_store=None,
    )
    assert getattr(agent, "checkpointer", None) is not None
