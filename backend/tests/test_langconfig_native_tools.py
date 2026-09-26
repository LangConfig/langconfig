import json
from types import SimpleNamespace

import db.database as db_database
import services.codex_harness as codex_harness_service
import services.hermes_service as hermes_service
from services.platform_brain_service import platform_brain_service
from tools.native_tools import (
    codex_get_status,
    codex_run_task,
    langconfig_apply_draft,
    langconfig_create_draft,
    langconfig_export_workflow,
    langconfig_search,
    langconfig_validate_workflow,
    load_native_tools,
)


class FakeQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.value


class FakeSession:
    def __init__(self, query_value=None):
        self.query_value = query_value
        self.rollback_calls = 0
        self.closed = False

    def query(self, model):
        return FakeQuery(self.query_value)

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.closed = True


def _use_session(monkeypatch, *, query_value=None):
    session = FakeSession(query_value=query_value)
    monkeypatch.setattr(db_database, "SessionLocal", lambda: session)
    return session


def _invoke(tool, **arguments):
    return json.loads(tool.invoke(arguments))


def test_privileged_native_tools_require_protected_loader_opt_in():
    requested = ["langconfig_apply_draft", "codex_run_task"]

    assert load_native_tools(requested) == []
    assert {tool.name for tool in load_native_tools(requested, allow_privileged=True)} == set(requested)


def test_langconfig_search_delegates_and_closes_session(monkeypatch):
    session = _use_session(monkeypatch)
    captured = {}

    def fake_query(query, db, *, top_k, project_id):
        captured.update(query=query, db=db, top_k=top_k, project_id=project_id)
        return {"results": [{"source_id": "doc:setup"}]}

    monkeypatch.setattr(platform_brain_service, "query", fake_query)

    result = _invoke(langconfig_search, query="setup", top_k=3, project_id=12)

    assert result == {"results": [{"source_id": "doc:setup"}]}
    assert captured == {"query": "setup", "db": session, "top_k": 3, "project_id": 12}
    assert session.closed is True


def test_langconfig_search_serializes_service_error_and_closes_session(monkeypatch):
    session = _use_session(monkeypatch)

    def fail_query(*args, **kwargs):
        raise RuntimeError("brain unavailable")

    monkeypatch.setattr(platform_brain_service, "query", fail_query)

    result = _invoke(langconfig_search, query="setup")

    assert result == {"error": "brain unavailable"}
    assert session.closed is True


def test_langconfig_validate_workflow_rejects_malformed_json_and_closes_session(monkeypatch):
    session = _use_session(monkeypatch)

    result = _invoke(langconfig_validate_workflow, payload_json="{not-json")

    assert result["valid"] is False
    assert result["issues"][0]["path"] == "$"
    assert "valid JSON" in result["issues"][0]["message"]
    assert session.closed is True


def test_langconfig_create_draft_delegates_success_and_closes_session(monkeypatch):
    session = _use_session(monkeypatch)
    draft = SimpleNamespace(id=41)
    captured = {}

    def fake_create(db, **kwargs):
        captured.update(db=db, **kwargs)
        return draft

    monkeypatch.setattr(hermes_service, "create_draft", fake_create)
    monkeypatch.setattr(hermes_service, "serialize_draft", lambda value: {"id": value.id, "status": "validated"})

    result = _invoke(
        langconfig_create_draft,
        artifact_type="workflow",
        title="Draft me",
        payload_json='{"name":"Draft me"}',
        project_id=7,
        source_session_id="session-1",
        codex_run_id="run-1",
    )

    assert result == {"id": 41, "status": "validated"}
    assert captured == {
        "db": session,
        "artifact_type": "workflow",
        "title": "Draft me",
        "payload_json": {"name": "Draft me"},
        "project_id": 7,
        "source_session_id": "session-1",
        "codex_run_id": "run-1",
        "validate_on_create": True,
    }
    assert session.rollback_calls == 0
    assert session.closed is True


def test_langconfig_create_draft_rolls_back_bad_input_and_closes_session(monkeypatch):
    session = _use_session(monkeypatch)

    result = _invoke(
        langconfig_create_draft,
        artifact_type="workflow",
        title="Bad payload",
        payload_json="[]",
    )

    assert result == {"error": "payload_json must be a JSON object"}
    assert session.rollback_calls == 1
    assert session.closed is True


def test_langconfig_create_draft_rolls_back_service_error_and_closes_session(monkeypatch):
    session = _use_session(monkeypatch)

    def fail_create(*args, **kwargs):
        raise RuntimeError("draft write failed")

    monkeypatch.setattr(hermes_service, "create_draft", fail_create)

    result = _invoke(
        langconfig_create_draft,
        artifact_type="workflow",
        title="Draft me",
        payload_json="{}",
    )

    assert result == {"error": "draft write failed"}
    assert session.rollback_calls == 1
    assert session.closed is True


def test_langconfig_apply_draft_handles_missing_draft_and_closes_session(monkeypatch):
    session = _use_session(monkeypatch, query_value=None)

    result = _invoke(langconfig_apply_draft, draft_id=404)

    assert result == {"error": "Hermes draft not found"}
    assert session.rollback_calls == 0
    assert session.closed is True


def test_langconfig_apply_draft_delegates_success_and_closes_session(monkeypatch):
    draft = SimpleNamespace(id=8)
    session = _use_session(monkeypatch, query_value=draft)
    captured = {}

    def fake_apply(db, value, **kwargs):
        captured.update(db=db, draft=value, **kwargs)
        return {"workflow_id": 23}

    monkeypatch.setattr(hermes_service, "apply_draft", fake_apply)
    monkeypatch.setattr(hermes_service, "serialize_draft", lambda value: {"id": value.id})

    result = _invoke(
        langconfig_apply_draft,
        draft_id=8,
        target_id=23,
        lock_version=4,
        approval_note="approved",
    )

    assert result == {"draft": {"id": 8}, "apply_result": {"workflow_id": 23}}
    assert captured == {
        "db": session,
        "draft": draft,
        "target_id": 23,
        "lock_version": 4,
        "approval_note": "approved",
    }
    assert session.rollback_calls == 0
    assert session.closed is True


def test_langconfig_apply_draft_rolls_back_service_error_and_closes_session(monkeypatch):
    session = _use_session(monkeypatch, query_value=SimpleNamespace(id=8))

    def fail_apply(*args, **kwargs):
        raise RuntimeError("apply failed")

    monkeypatch.setattr(hermes_service, "apply_draft", fail_apply)

    result = _invoke(langconfig_apply_draft, draft_id=8)

    assert result == {"error": "apply failed"}
    assert session.rollback_calls == 1
    assert session.closed is True


def test_langconfig_export_workflow_handles_missing_and_success(monkeypatch):
    missing_session = _use_session(monkeypatch, query_value=None)

    missing = _invoke(langconfig_export_workflow, workflow_id=404)

    assert missing == {"error": "Workflow not found"}
    assert missing_session.closed is True

    workflow = SimpleNamespace(id=9, name="Export Me")
    success_session = _use_session(monkeypatch, query_value=workflow)

    success = _invoke(langconfig_export_workflow, workflow_id=9, export_mode="portable")

    assert success["workflow_id"] == 9
    assert success["name"] == "Export Me"
    assert success["package_endpoint"].endswith("export_mode=portable")
    assert success_session.closed is True


def test_codex_native_tools_delegate_success(monkeypatch):
    run = SimpleNamespace(id="run-7")
    captured = {}

    class FakeHarness:
        def start_exec_run(self, prompt, model=None):
            captured.update(prompt=prompt, model=model)
            return run

        def serialize_run(self, value):
            assert value is run
            return {"id": value.id, "status": "queued"}

        def status(self):
            return {"installed": True, "logged_in": True}

    monkeypatch.setattr(codex_harness_service, "codex_harness", FakeHarness())

    run_result = _invoke(codex_run_task, prompt="inspect code", model="gpt-5.4")
    status_result = _invoke(codex_get_status)

    assert run_result == {"id": "run-7", "status": "queued"}
    assert status_result == {"installed": True, "logged_in": True}
    assert captured == {"prompt": "inspect code", "model": "gpt-5.4"}


def test_codex_native_tools_serialize_service_errors(monkeypatch):
    class FailingHarness:
        def start_exec_run(self, prompt, model=None):
            raise RuntimeError("run unavailable")

        def status(self):
            raise RuntimeError("status unavailable")

    monkeypatch.setattr(codex_harness_service, "codex_harness", FailingHarness())

    run_result = _invoke(codex_run_task, prompt="inspect code")
    status_result = _invoke(codex_get_status)

    assert run_result == {"error": "run unavailable"}
    assert status_result == {"error": "status unavailable"}
