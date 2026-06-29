from pydantic import ValidationError
import pytest

from langchain_core.tools import tool

from api.chat.routes import runtime_event_to_sse_payload
from core.templates.deep_agent import DeepAgentTemplateRegistry, create_dynamic_workflow_agent
from core.runtimes.base import normalize_dynamic_subagent_event
from models.deep_agent import DeepAgentConfig, SubAgentConfig
from services.deepagent_factory import DeepAgentFactory


@tool
def search_notes(query: str) -> str:
    """Search notes."""
    return query


def test_deep_agent_interpreter_config_defaults_off():
    config = DeepAgentConfig(system_prompt="Use subagents carefully.")

    assert config.interpreter.enabled is False
    assert config.interpreter.mode == "thread"
    assert config.interpreter.dynamic_subagents is True
    assert config.interpreter.ptc_tool_allowlist == []
    assert config.interpreter.require_eval_approval is True
    assert config.interrupt_on == {}


def test_interpreter_config_rejects_invalid_ptc_budget():
    try:
        DeepAgentConfig(
            system_prompt="Use subagents carefully.",
            interpreter={"enabled": True, "max_ptc_calls": 0},
        )
    except ValidationError as exc:
        assert "max_ptc_calls" in str(exc)
    else:
        raise AssertionError("max_ptc_calls=0 should be rejected")


def test_resolve_ptc_allowlist_matches_loaded_tools():
    config = DeepAgentConfig(
        system_prompt="Use subagents carefully.",
        interpreter={"enabled": True, "ptc_tool_allowlist": ["search_notes"]},
    )

    assert DeepAgentFactory._resolve_ptc_allowlist(config, [search_notes]) == [search_notes]


def test_resolve_ptc_allowlist_rejects_task_and_unknown_tools():
    task_config = DeepAgentConfig(
        system_prompt="Use subagents carefully.",
        interpreter={"enabled": True, "ptc_tool_allowlist": ["task"]},
    )
    try:
        DeepAgentFactory._resolve_ptc_allowlist(task_config, [search_notes])
    except ValueError as exc:
        assert "cannot include 'task'" in str(exc)
    else:
        raise AssertionError("task should be rejected from the PTC allowlist")

    missing_config = DeepAgentConfig(
        system_prompt="Use subagents carefully.",
        interpreter={"enabled": True, "ptc_tool_allowlist": ["missing_tool"]},
    )
    try:
        DeepAgentFactory._resolve_ptc_allowlist(missing_config, [search_notes])
    except ValueError as exc:
        assert "unknown tools" in str(exc)
    else:
        raise AssertionError("unknown PTC tools should be rejected")


def test_build_code_interpreter_middleware_uses_real_quickjs_package():
    pytest.importorskip("langchain_quickjs")
    config = DeepAgentConfig(
        system_prompt="Use subagents carefully.",
        interpreter={"enabled": True, "ptc_tool_allowlist": ["search_notes"]},
    )

    middleware = DeepAgentFactory._build_code_interpreter_middleware(config, [search_notes])

    assert middleware is not None
    assert getattr(middleware, "_subagents") is True
    assert getattr(middleware, "_ptc") == [search_notes]
    assert getattr(middleware, "_mode") == "thread"


def test_dynamic_workflow_template_keeps_safe_interpreter_defaults():
    config = create_dynamic_workflow_agent()

    assert config.interpreter.enabled is True
    assert config.interpreter.dynamic_subagents is True
    assert config.interpreter.ptc_tool_allowlist == []
    assert config.interpreter.require_eval_approval is True
    assert config.interrupt_on["eval"] is True
    assert {subagent.name for subagent in config.subagents} == {
        "analyzer",
        "verifier",
        "synthesizer",
    }

    registry_config = DeepAgentTemplateRegistry.get_template("DYNAMIC_WORKFLOW_AGENT")
    assert registry_config.interpreter.enabled is True


def test_inline_subagent_response_schema_resolves_to_pydantic_model():
    subagent = SubAgentConfig(
        name="reviewer",
        description="Review work",
        response_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "score": {"type": "integer"},
            },
            "required": ["summary"],
        },
    )

    response_format = DeepAgentFactory._resolve_subagent_response_format(subagent)

    assert response_format.__name__ == "ReviewerResult"
    assert "summary" in response_format.model_fields
    assert "score" in response_format.model_fields


def test_quickjs_subagent_custom_event_normalizes_to_runtime_event():
    normalized = normalize_dynamic_subagent_event({
        "type": "subagent",
        "phase": "start",
        "id": "ptc_task_1234",
        "eval_id": "eval_1",
        "subagent_type": "reviewer",
        "label": "Review diff",
        "description": "Inspect changed files",
    })

    assert normalized == {
        "type": "subagent_start",
        "data": {
            "subagent_name": "Review diff",
            "subagent_run_id": "ptc_task_1234",
            "parent_agent_label": None,
            "parent_run_id": "eval_1",
            "input_preview": "Inspect changed files",
            "output_preview": None,
            "is_dynamic": True,
            "eval_id": "eval_1",
            "phase": "start",
            "subagent_type": "reviewer",
            "label": "Review diff",
            "description": "Inspect changed files",
            "duration_ms": None,
        },
    }


def test_dynamic_subagent_runtime_event_maps_to_public_sse_frame():
    event = {
        "type": "subagent_end",
        "data": {
            "subagent_name": "Review diff",
            "subagent_run_id": "ptc_task_1234",
            "success": True,
            "is_dynamic": True,
            "eval_id": "eval_1",
            "duration_ms": 120,
        },
    }

    assert runtime_event_to_sse_payload(event) == {
        "type": "subagent_end",
        "data": event["data"],
    }
