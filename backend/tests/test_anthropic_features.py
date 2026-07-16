# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Unit tests for Anthropic quick-win features wired into AgentFactory:

- Adaptive thinking (fable-5 always-on; sonnet-5 adaptive by default; opus-4-8 / sonnet-4-6 opt-in)
- Effort parameter mapping (low/medium/high; provider-neutral xhigh/max degrade to high; "none" omitted)
- Prompt caching (top-level cache_control via model_kwargs)
- Server-side web tools assembly + native-tool collision guard
"""

from types import SimpleNamespace

import pytest

from core.agents.factory import (
    AgentFactory,
    SERVER_TOOL_DEFS,
    resolve_anthropic_server_tools,
)
from core.models.registry import ModelCapability, model_registry
from config import settings


@pytest.fixture(autouse=True)
def _anthropic_api_key(monkeypatch):
    """Ensure ChatAnthropic construction never fails on a missing key.

    Settings.ANTHROPIC_API_KEY is a read-only property, so patch the class.
    """
    monkeypatch.setattr(
        type(settings), "ANTHROPIC_API_KEY", property(lambda self: "test-key")
    )


@pytest.mark.asyncio
async def test_fable_gets_adaptive_thinking_and_no_temperature():
    llm = await AgentFactory._create_llm("claude-fable-5", 0.7, 4096, {})
    # claude-fable-5 rejects sampling params -> temperature must not be set
    assert llm.temperature is None
    # Thinking is always on; display-only override (never type=disabled)
    assert llm.thinking == {"type": "adaptive", "display": "summarized"}


@pytest.mark.asyncio
async def test_opus_enable_thinking_sets_adaptive_and_pops_temperature():
    config = {"enable_thinking": True, "thinking_display": "omitted"}
    llm = await AgentFactory._create_llm("claude-opus-4-8", 0.7, 4096, config)
    assert llm.thinking == {"type": "adaptive", "display": "omitted"}
    assert llm.temperature is None


@pytest.mark.asyncio
async def test_opus_without_thinking_keeps_temperature_and_no_thinking():
    llm = await AgentFactory._create_llm("claude-opus-4-8", 0.3, 4096, {})
    assert llm.thinking is None
    assert llm.temperature == 0.3


@pytest.mark.asyncio
async def test_sonnet_5_enable_thinking_sets_adaptive_and_pops_temperature():
    config = {"enable_thinking": True, "thinking_display": "summarized"}
    llm = await AgentFactory._create_llm("claude-sonnet-5", 0.7, 4096, config)
    assert llm.thinking == {"type": "adaptive", "display": "summarized"}
    assert llm.temperature is None


@pytest.mark.asyncio
async def test_sonnet_5_default_omits_sampling_params_and_uses_adaptive_thinking():
    llm = await AgentFactory._create_llm("claude-sonnet-5", 0.7, 4096, {})

    assert llm.temperature is None
    assert llm.top_p is None
    assert llm.top_k is None
    assert llm.thinking == {"type": "adaptive", "display": "summarized"}


@pytest.mark.asyncio
async def test_sonnet_5_effort_only_omits_sampling_params():
    llm = await AgentFactory._create_llm(
        "claude-sonnet-5", 0.7, 4096, {"reasoning_effort": "medium"}
    )

    assert llm.temperature is None
    assert llm.top_p is None
    assert llm.top_k is None
    assert llm.effort == "medium"


@pytest.mark.asyncio
async def test_sonnet_5_explicitly_disabled_thinking_still_omits_sampling_params():
    llm = await AgentFactory._create_llm(
        "claude-sonnet-5", 0.7, 4096, {"enable_thinking": False}
    )

    assert llm.temperature is None
    assert llm.top_p is None
    assert llm.top_k is None
    assert llm.thinking == {"type": "disabled"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("effort", "expected"),
    [("low", "low"), ("medium", "medium"), ("high", "high"), ("xhigh", "high"), ("max", "high")],
)
@pytest.mark.parametrize("model_name", ["claude-sonnet-5", "claude-sonnet-4-6"])
async def test_effort_mapping_supported_levels(model_name, effort, expected):
    config = {"reasoning_effort": effort}
    llm = await AgentFactory._create_llm(model_name, 0.7, 4096, config)
    assert llm.effort == expected


@pytest.mark.asyncio
async def test_effort_none_is_omitted():
    llm = await AgentFactory._create_llm(
        "claude-sonnet-4-6", 0.7, 4096, {"reasoning_effort": "none"}
    )
    assert llm.effort is None


@pytest.mark.asyncio
async def test_effort_enum_value_is_unwrapped():
    from models.enums import ReasoningEffort

    llm = await AgentFactory._create_llm(
        "claude-fable-5", 0.7, 4096, {"reasoning_effort": ReasoningEffort.XHIGH}
    )
    assert llm.effort == "high"


@pytest.mark.asyncio
async def test_prompt_caching_sets_top_level_cache_control():
    llm = await AgentFactory._create_llm(
        "claude-opus-4-8", 0.7, 4096, {"enable_prompt_caching": True}
    )
    assert llm.model_kwargs.get("cache_control") == {"type": "ephemeral"}


def test_server_tool_assembly_and_collision_guard():
    native_web_search = SimpleNamespace(name="web_search")
    other_tool = SimpleNamespace(name="read_file")

    server_dicts, filtered = resolve_anthropic_server_tools(
        ["anthropic_web_search", "web_fetch", "bogus_tool"],
        [native_web_search, other_tool],
    )

    # Both known server tools resolved (UI-prefixed and bare names accepted)
    assert server_dicts == [
        SERVER_TOOL_DEFS["web_search"],
        SERVER_TOOL_DEFS["web_fetch"],
    ]
    assert server_dicts[0]["type"] == "web_search_20260209"
    assert server_dicts[1]["type"] == "web_fetch_20260209"

    # Collision guard: native web_search dropped, unrelated tool kept
    assert native_web_search not in filtered
    assert other_tool in filtered


def test_sonnet_5_registry_metadata():
    model = model_registry.get_model("claude-sonnet-5")

    assert model is not None
    assert model.display_name == "Claude Sonnet 5"
    assert model.cost_per_1m_input == 2.0
    assert model.cost_per_1m_output == 10.0
    assert model.max_context_tokens == 1_000_000
    assert model.max_output_tokens == 128_000
    assert ModelCapability.REASONING in model.capabilities
