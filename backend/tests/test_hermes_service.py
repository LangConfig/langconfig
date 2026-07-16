import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

import models  # noqa: F401 - registers SQLAlchemy models
import services.hermes_service as hermes_service
from core.templates.deep_agent import DeepAgentTemplateRegistry, create_hermes_platform_builder
from services.deepagent_factory import DeepAgentFactory
from db.database import Base
from models.custom_tool import CustomTool
from models.deep_agent import DeepAgentTemplate
from models.hermes import HermesDraft
from models.workflow import WorkflowProfile
from models.workflow_schedule import WorkflowSchedule
from models.workflow_trigger import WorkflowTrigger
from services.hermes_service import (
    HermesApplyError,
    apply_draft,
    create_draft,
    reject_draft,
    validate_draft_payload,
    validate_existing_draft,
)
from api.hermes.routes import validate_draft as validate_draft_route


def _db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    return engine, session


def _workflow_payload(name="Hermes Test Workflow"):
    return {
        "name": name,
        "configuration": {
            "nodes": [
                {"id": "start", "type": "START", "config": {}, "data": {"agentType": "START"}},
                {"id": "end", "type": "END", "config": {}, "data": {"agentType": "END"}},
            ],
            "edges": [{"id": "e1", "source": "start", "target": "end"}],
        },
        "blueprint": {
            "nodes": [
                {"id": "start", "type": "custom", "config": {}, "data": {"agentType": "START"}},
                {"id": "end", "type": "custom", "config": {}, "data": {"agentType": "END"}},
            ],
            "edges": [{"id": "e1", "source": "start", "target": "end"}],
        },
    }


def _deep_agent_payload(name="Hermes Test Agent"):
    return {
        "name": name,
        "description": "Created by a Hermes service test",
        "config": {
            "system_prompt": "You are a focused test agent.",
            "native_tools": ["get_current_time"],
        },
    }


def _custom_tool_payload(name="Hermes Test Tool"):
    return {
        "name": name,
        "description": "A deterministic test tool",
        "tool_type": "api",
        "implementation_config": {"url": "https://example.invalid/test"},
        "input_schema": {"type": "object", "properties": {}},
    }


def test_hermes_validates_workflow_payload():
    valid = validate_draft_payload("workflow", _workflow_payload())
    invalid = validate_draft_payload("workflow", {"configuration": {"nodes": [], "edges": []}})

    assert valid["valid"] is True
    assert invalid["valid"] is False
    assert invalid["issues"][0]["path"] == "$.configuration.nodes"


def test_hermes_standalone_validation_still_persists_status():
    engine, session = _db_session()
    try:
        draft = create_draft(
            session,
            artifact_type="workflow",
            title="Validate Separately",
            payload_json=_workflow_payload("Validate Separately"),
            validate_on_create=False,
        )

        validation = validate_existing_draft(session, draft)

        session.expire_all()
        assert validation["valid"] is True
        assert session.get(HermesDraft, draft.id).status == "validated"
    finally:
        session.close()
        engine.dispose()


def test_hermes_validation_does_not_reopen_applied_draft():
    engine, session = _db_session()
    try:
        draft = create_draft(
            session,
            artifact_type="workflow",
            title="Applied Terminal Draft",
            payload_json=_workflow_payload("Applied Terminal Draft"),
        )
        apply_draft(session, draft)

        with pytest.raises(HermesApplyError, match="Applied drafts cannot be revalidated"):
            validate_existing_draft(session, draft)

        session.expire_all()
        assert session.get(HermesDraft, draft.id).status == "applied"
    finally:
        session.close()
        engine.dispose()


def test_hermes_validate_route_reports_terminal_state_as_bad_request():
    engine, session = _db_session()
    try:
        draft = create_draft(
            session,
            artifact_type="workflow",
            title="Applied Route Draft",
            payload_json=_workflow_payload("Applied Route Draft"),
        )
        apply_draft(session, draft)

        with pytest.raises(HTTPException) as exc_info:
            validate_draft_route(draft.id, db=session)

        assert exc_info.value.status_code == 400
        assert "cannot be revalidated" in exc_info.value.detail
    finally:
        session.close()
        engine.dispose()


def test_hermes_validation_does_not_reopen_rejected_draft():
    engine, session = _db_session()
    try:
        draft = create_draft(
            session,
            artifact_type="workflow",
            title="Rejected Terminal Draft",
            payload_json=_workflow_payload("Rejected Terminal Draft"),
        )
        reject_draft(session, draft, "not approved")

        with pytest.raises(HermesApplyError, match="Rejected drafts cannot be revalidated"):
            validate_existing_draft(session, draft)

        session.expire_all()
        assert session.get(HermesDraft, draft.id).status == "rejected"
    finally:
        session.close()
        engine.dispose()


def test_hermes_create_apply_and_reject_workflow_drafts():
    engine, session = _db_session()
    try:
        draft = create_draft(
            session,
            artifact_type="workflow",
            title="Apply Me",
            payload_json=_workflow_payload("Apply Me"),
        )
        result = apply_draft(session, draft, approval_note="approved")

        workflow = session.query(WorkflowProfile).filter(WorkflowProfile.id == result["workflow_id"]).first()
        assert draft.status == "applied"
        assert workflow is not None
        assert workflow.name == "Apply Me"

        rejected = HermesDraft(
            artifact_type="workflow",
            title="Reject Me",
            payload_json=_workflow_payload("Reject Me"),
            status="validated",
            validation_result={"valid": True},
        )
        session.add(rejected)
        session.commit()
        reject_draft(session, rejected, "not needed")
        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "not needed"
    finally:
        session.close()
        engine.dispose()


def test_hermes_creates_and_applies_every_supported_artifact_type():
    engine, session = _db_session()
    try:
        workflow_draft = create_draft(
            session,
            artifact_type="workflow",
            title="Artifact Parent Workflow",
            payload_json=_workflow_payload("Artifact Parent Workflow"),
        )
        workflow_result = apply_draft(session, workflow_draft)
        workflow_id = workflow_result["workflow_id"]

        artifact_cases = [
            (
                "deep_agent",
                _deep_agent_payload(),
                DeepAgentTemplate,
                "agent_id",
            ),
            (
                "custom_tool",
                _custom_tool_payload(),
                CustomTool,
                "tool_id",
            ),
            (
                "schedule",
                {
                    "workflow_id": workflow_id,
                    "name": "Hermes Test Schedule",
                    "cron_expression": "0 9 * * *",
                },
                WorkflowSchedule,
                "schedule_id",
            ),
            (
                "trigger",
                {
                    "workflow_id": workflow_id,
                    "name": "Hermes Test Trigger",
                    "trigger_type": "webhook",
                    "config": {"require_signature": True},
                },
                WorkflowTrigger,
                "trigger_id",
            ),
        ]

        for artifact_type, payload, model, result_id_key in artifact_cases:
            draft = create_draft(
                session,
                artifact_type=artifact_type,
                title=f"Apply {artifact_type}",
                payload_json=payload,
            )

            result = apply_draft(session, draft, approval_note="approved in test")

            assert result["artifact_type"] == artifact_type
            assert result["action"] == "created"
            assert session.get(model, result[result_id_key]) is not None
            assert draft.status == "applied"
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("artifact_type", "initial_payload", "updated_payload", "result_id_key"),
    [
        (
            "workflow",
            _workflow_payload("Workflow Before Update"),
            _workflow_payload("Workflow After Update"),
            "workflow_id",
        ),
        (
            "deep_agent",
            _deep_agent_payload("Agent Before Update"),
            _deep_agent_payload("Agent After Update"),
            "agent_id",
        ),
    ],
)
def test_hermes_update_guards_and_successful_update(
    artifact_type,
    initial_payload,
    updated_payload,
    result_id_key,
):
    engine, session = _db_session()
    try:
        initial_draft = create_draft(
            session,
            artifact_type=artifact_type,
            title=f"Create {artifact_type}",
            payload_json=initial_payload,
        )
        initial_result = apply_draft(session, initial_draft)
        target_id = initial_result[result_id_key]
        target_model = WorkflowProfile if artifact_type == "workflow" else DeepAgentTemplate
        current_lock_version = session.get(target_model, target_id).lock_version

        update_draft = create_draft(
            session,
            artifact_type=artifact_type,
            title=f"Update {artifact_type}",
            payload_json=updated_payload,
        )

        with pytest.raises(HermesApplyError, match="not found"):
            apply_draft(
                session,
                update_draft,
                target_id=target_id + 100_000,
                lock_version=current_lock_version,
            )

        with pytest.raises(HermesApplyError, match="lock_version is required"):
            apply_draft(session, update_draft, target_id=target_id)

        with pytest.raises(HermesApplyError, match="modified since the draft was created"):
            apply_draft(
                session,
                update_draft,
                target_id=target_id,
                lock_version=current_lock_version + 1,
            )

        result = apply_draft(
            session,
            update_draft,
            target_id=target_id,
            lock_version=current_lock_version,
        )

        assert result["action"] == "updated"
        assert session.get(target_model, target_id).name.endswith("After Update")
    finally:
        session.close()
        engine.dispose()


@pytest.mark.slow
def test_concurrent_postgres_apply_vs_reject_has_one_terminal_winner():
    test_database_url = os.getenv("TEST_DATABASE_URL")
    if not test_database_url:
        pytest.skip("Set TEST_DATABASE_URL to run the PostgreSQL concurrency regression")
    test_database_url = test_database_url.replace("postgresql+asyncpg://", "postgresql://")
    if make_url(test_database_url).get_backend_name() != "postgresql":
        pytest.skip("Concurrency regression requires PostgreSQL row locks")
    if "test" not in (make_url(test_database_url).database or "").lower():
        pytest.skip("Concurrency test requires a disposable PostgreSQL test database")

    engine = create_engine(test_database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(engine)
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL test database is unavailable: {exc}")

    SessionLocal = sessionmaker(bind=engine)
    suffix = uuid.uuid4().hex[:10]
    workflow_name = f"Hermes Concurrent {suffix}"
    setup_session = SessionLocal()
    try:
        draft = create_draft(
            setup_session,
            artifact_type="workflow",
            title=workflow_name,
            payload_json=_workflow_payload(workflow_name),
        )
        draft_id = draft.id
    finally:
        setup_session.close()

    start_barrier = threading.Barrier(2)

    def transition_from_independent_session(action):
        session = SessionLocal()
        try:
            local_draft = session.get(HermesDraft, draft_id)
            start_barrier.wait(timeout=10)
            try:
                if action == "apply":
                    apply_draft(session, local_draft)
                    return "applied", None
                reject_draft(session, local_draft, "concurrent rejection")
                return "rejected", None
            except HermesApplyError as exc:
                return "error", str(exc)
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(transition_from_independent_session, ("apply", "reject")))

        verification_session = SessionLocal()
        try:
            persisted_draft = verification_session.get(HermesDraft, draft_id)
            successful_statuses = [status for status, error in results if error is None]
            errors = [error for status, error in results if status == "error"]

            assert successful_statuses in (["applied"], ["rejected"])
            assert len(errors) == 1
            assert persisted_draft.status == successful_statuses[0]

            workflow_count = (
                verification_session.query(WorkflowProfile)
                .filter(WorkflowProfile.name == workflow_name)
                .count()
            )
            if persisted_draft.status == "applied":
                assert workflow_count == 1
                assert "already been applied" in errors[0]
            else:
                assert workflow_count == 0
                assert "Rejected drafts cannot be applied" in errors[0]
        finally:
            verification_session.close()
    finally:
        cleanup_session = SessionLocal()
        try:
            cleanup_session.query(WorkflowProfile).filter(
                WorkflowProfile.name == workflow_name
            ).delete(synchronize_session=False)
            cleanup_session.query(HermesDraft).filter(HermesDraft.id == draft_id).delete(
                synchronize_session=False
            )
            cleanup_session.commit()
        finally:
            cleanup_session.close()
            engine.dispose()


def test_hermes_apply_tool_requires_runtime_approval_interrupt():
    config = create_hermes_platform_builder()
    registry_config = DeepAgentTemplateRegistry.get_template("HERMES_PLATFORM_BUILDER")

    assert config.interrupt_on["langconfig_apply_draft"] is True
    assert config.interrupt_on["codex_run_task"] is True
    assert registry_config.interrupt_on["langconfig_apply_draft"] is True
    assert registry_config.interrupt_on["codex_run_task"] is True
    codex_subagent = next(subagent for subagent in config.subagents if subagent.name == "codex_engineer")
    assert codex_subagent.interrupt_on["codex_run_task"] is True


def test_regular_agent_factory_excludes_privileged_hermes_tools():
    from core.agents.factory import AgentFactory

    selected_tools = AgentFactory._filter_regular_agent_native_tools(
        [
            "langconfig_search",
            "langconfig_apply_draft",
            "codex_run_task",
            "codex_get_status",
        ]
    )

    assert selected_tools == ["langconfig_search", "codex_get_status"]


@pytest.mark.asyncio
async def test_hermes_approval_interrupt_is_forwarded_to_deepagents(monkeypatch):
    import sys
    import types

    import core.workflows.checkpointing.manager as checkpoint_manager
    from core.agents.factory import AgentFactory
    from core.middleware.deep import DeepAgentsMiddlewareFactory

    captured_kwargs = {}

    def fake_create_deep_agent(**kwargs):
        captured_kwargs.update(kwargs)
        return object()

    fake_deepagents = types.ModuleType("deepagents")
    fake_deepagents.create_deep_agent = fake_create_deep_agent

    async def no_callbacks(*args, **kwargs):
        return []

    async def no_tools(*args, **kwargs):
        return []

    async def no_subagents(*args, **kwargs):
        return []

    async def fake_model(*args, **kwargs):
        return "test-model"

    monkeypatch.setitem(sys.modules, "deepagents", fake_deepagents)
    monkeypatch.setattr(DeepAgentFactory, "_setup_callbacks", no_callbacks)
    monkeypatch.setattr(DeepAgentFactory, "_load_base_tools", no_tools)
    monkeypatch.setattr(DeepAgentFactory, "_prepare_subagents", no_subagents)
    monkeypatch.setattr(DeepAgentsMiddlewareFactory, "create_all_tools", no_tools)
    monkeypatch.setattr(AgentFactory, "_create_llm", fake_model)
    monkeypatch.setattr(checkpoint_manager, "get_checkpointer", lambda: None)
    monkeypatch.setattr(checkpoint_manager, "get_store", lambda: None)

    config = create_hermes_platform_builder()
    config.interrupt_on = {
        "langconfig_apply_draft": False,
        "codex_run_task": False,
    }

    await DeepAgentFactory.create_deep_agent(
        config=config,
        project_id=0,
        task_id=0,
        context="",
    )

    assert captured_kwargs["interrupt_on"]["langconfig_apply_draft"] is True
    assert captured_kwargs["interrupt_on"]["codex_run_task"] is True


def test_hermes_apply_is_idempotent_and_rejects_terminal_states():
    engine, session = _db_session()
    try:
        draft = create_draft(
            session,
            artifact_type="workflow",
            title="Apply Once",
            payload_json=_workflow_payload("Apply Once"),
        )
        apply_draft(session, draft, approval_note="approved")

        with pytest.raises(HermesApplyError, match="already been applied"):
            apply_draft(session, draft, approval_note="approved again")
        with pytest.raises(HermesApplyError, match="already been applied"):
            reject_draft(session, draft, "too late")

        assert session.query(WorkflowProfile).count() == 1

        rejected = create_draft(
            session,
            artifact_type="workflow",
            title="Never Apply",
            payload_json=_workflow_payload("Never Apply"),
        )
        reject_draft(session, rejected, "not approved")

        with pytest.raises(HermesApplyError, match="already been rejected"):
            reject_draft(session, rejected, "different reason")

        with pytest.raises(HermesApplyError, match="Rejected drafts"):
            apply_draft(session, rejected)

        assert session.query(WorkflowProfile).count() == 1
    finally:
        session.close()
        engine.dispose()


def test_hermes_apply_commits_once(monkeypatch):
    engine, session = _db_session()
    try:
        draft = create_draft(
            session,
            artifact_type="workflow",
            title="Single Transaction",
            payload_json=_workflow_payload("Single Transaction"),
        )
        original_commit = session.commit
        commit_calls = 0

        def counting_commit():
            nonlocal commit_calls
            commit_calls += 1
            return original_commit()

        monkeypatch.setattr(session, "commit", counting_commit)

        apply_draft(session, draft, approval_note="approved")

        assert commit_calls == 1
    finally:
        session.close()
        engine.dispose()


def test_hermes_apply_rolls_back_artifact_when_finalization_fails(monkeypatch):
    engine, session = _db_session()
    try:
        draft = create_draft(
            session,
            artifact_type="workflow",
            title="Atomic Apply",
            payload_json=_workflow_payload("Atomic Apply"),
        )

        def fail_after_artifact_flush(db, payload, *, target_id, lock_version):
            db.add(WorkflowProfile(name="Partial Artifact", configuration=payload["configuration"]))
            db.flush()
            raise RuntimeError("simulated finalization failure")

        monkeypatch.setattr(hermes_service, "_apply_workflow", fail_after_artifact_flush)

        with pytest.raises(RuntimeError, match="simulated finalization failure"):
            apply_draft(session, draft, approval_note="approved")

        session.expire_all()
        persisted_draft = session.get(HermesDraft, draft.id)
        assert persisted_draft.status == "validated"
        assert persisted_draft.apply_result in (None, {})
        assert session.query(WorkflowProfile).count() == 0
    finally:
        session.close()
        engine.dispose()
