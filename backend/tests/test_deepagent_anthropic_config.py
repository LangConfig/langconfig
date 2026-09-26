import sys
import types

import pytest

from core.agents.factory import AgentFactory
from core.middleware.deep import DeepAgentsMiddlewareFactory
from models.deep_agent import DeepAgentConfig
from services.deepagent_factory import DeepAgentFactory


def _sonnet_config(**overrides):
    return DeepAgentConfig(
        model="claude-sonnet-5",
        system_prompt="You are a focused test agent.",
        **overrides,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected_enable_thinking"),
    [({}, "missing"), ({"enable_thinking": False}, False)],
)
async def test_deepagent_sonnet_5_preserves_unset_vs_explicit_disable(
    monkeypatch,
    overrides,
    expected_enable_thinking,
):
    import core.workflows.checkpointing.manager as checkpoint_manager

    captured_llm_config = {}

    async def fake_create_llm(model, temperature, max_tokens, config):
        captured_llm_config.update(config)
        return "configured-sonnet"

    async def no_callbacks(*args, **kwargs):
        return []

    async def no_tools(*args, **kwargs):
        return []

    async def no_subagents(*args, **kwargs):
        return []

    fake_deepagents = types.ModuleType("deepagents")
    fake_deepagents.create_deep_agent = lambda **kwargs: object()

    monkeypatch.setitem(sys.modules, "deepagents", fake_deepagents)
    monkeypatch.setattr(AgentFactory, "_create_llm", fake_create_llm)
    monkeypatch.setattr(DeepAgentFactory, "_setup_callbacks", no_callbacks)
    monkeypatch.setattr(DeepAgentFactory, "_load_base_tools", no_tools)
    monkeypatch.setattr(DeepAgentFactory, "_prepare_subagents", no_subagents)
    monkeypatch.setattr(DeepAgentsMiddlewareFactory, "create_all_tools", no_tools)
    monkeypatch.setattr(checkpoint_manager, "get_checkpointer", lambda: None)
    monkeypatch.setattr(checkpoint_manager, "get_store", lambda: None)

    await DeepAgentFactory.create_deep_agent(
        config=_sonnet_config(**overrides),
        project_id=0,
        task_id=0,
        context="",
    )

    if expected_enable_thinking == "missing":
        assert "enable_thinking" not in captured_llm_config
    else:
        assert captured_llm_config["enable_thinking"] is expected_enable_thinking


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected_enable_thinking"),
    [({}, "missing"), ({"enable_thinking": False}, False)],
)
async def test_deepagent_fallback_preserves_unset_vs_explicit_disable(
    monkeypatch,
    overrides,
    expected_enable_thinking,
):
    captured_agent_config = {}

    async def fake_create_agent(*, agent_config, **kwargs):
        captured_agent_config.update(agent_config)
        return object(), [], []

    monkeypatch.setattr(AgentFactory, "create_agent", fake_create_agent)

    await DeepAgentFactory._fallback_to_regular_agent(
        config=_sonnet_config(**overrides),
        project_id=0,
        task_id=0,
        context="",
        mcp_manager=None,
        vector_store=None,
    )

    if expected_enable_thinking == "missing":
        assert "enable_thinking" not in captured_agent_config
    else:
        assert captured_agent_config["enable_thinking"] is expected_enable_thinking
