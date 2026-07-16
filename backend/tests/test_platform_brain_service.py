import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models  # noqa: F401 - registers SQLAlchemy models
from db.database import Base
from models.core import Project, Task
from models.custom_tool import CustomTool, ToolTemplateType, ToolType
from models.execution_event import ExecutionEvent
from models.workflow import WorkflowProfile
from models.workflow_schedule import WorkflowSchedule
from models.workflow_trigger import TriggerType, WorkflowTrigger
from services.platform_brain_service import (
    DOC_PATHS,
    REPO_ROOT,
    BrainSource,
    PlatformBrainService,
    _safe_database_json,
)


def _db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal()


def test_platform_brain_public_doc_sources_exist():
    missing = [relative for relative in DOC_PATHS if not (REPO_ROOT / relative).is_file()]

    assert missing == []


def test_platform_brain_indexes_static_operating_model_sources():
    service = PlatformBrainService()

    status = service.reindex()
    result = service.query("workflow routes recipes DeepAgent", top_k=5)

    assert status["source_count"] > 0
    assert "docs" in status["source_counts"] or "workflow.recipe" in status["source_counts"]
    assert result["total_results"] > 0
    assert result["results"][0]["metadata"]


def test_project_scope_keeps_static_sources_and_denies_unowned_database_sources():
    service = PlatformBrainService()
    service._sources = [
        BrainSource("doc:shared", "docs", "Shared guide", "shared source", {}),
        BrainSource("db:owned", "db.project", "Owned", "shared source", {"project_id": 7}),
        BrainSource("db:other", "db.project", "Other", "shared source", {"project_id": 8}),
        BrainSource("db:unowned", "db.deep_agent", "Unowned", "shared source", {}),
    ]

    result = service.query("shared", project_id=7)

    assert {item["source_id"] for item in result["results"]} == {"doc:shared", "db:owned"}


def test_missing_project_scope_excludes_all_database_sources():
    service = PlatformBrainService()
    service._sources = [
        BrainSource("doc:shared", "docs", "Shared guide", "shared source", {}),
        BrainSource("db:one", "db.project", "Project one", "shared source", {"project_id": 1}),
        BrainSource("db:two", "db.chat_history", "Project two", "shared source", {"project_id": 2}),
    ]

    result = service.query("shared")

    assert {item["source_id"] for item in result["results"]} == {"doc:shared"}


def test_missing_project_scope_does_not_refresh_database_sources(monkeypatch):
    service = PlatformBrainService()
    service._sources = [
        BrainSource("doc:shared", "docs", "Shared guide", "shared source", {}),
    ]

    def unexpected_database_refresh(*args, **kwargs):
        raise AssertionError("database sources must not be collected without project_id")

    monkeypatch.setattr(service, "_collect_database_sources", unexpected_database_refresh)

    result = service.query("shared", db=object())

    assert [item["source_id"] for item in result["results"]] == ["doc:shared"]


def test_query_collects_only_requested_database_source_for_project(monkeypatch):
    service = PlatformBrainService()
    service._sources = [
        BrainSource("doc:shared", "docs", "Shared guide", "shared source", {}),
    ]
    calls = []

    def collect_database_sources(db, *, project_id=None, source_types=None):
        calls.append((db, project_id, source_types))
        return [
            BrainSource(
                "workflow:7",
                "db.workflow",
                "Owned workflow",
                "shared workflow",
                {"project_id": 7},
            )
        ]

    monkeypatch.setattr(service, "_collect_database_sources", collect_database_sources)
    db = object()

    result = service.query(
        "shared",
        db=db,
        project_id=7,
        source_types=["db.workflow"],
    )

    assert calls == [(db, 7, {"db.workflow"})]
    assert [item["source_id"] for item in result["results"]] == ["workflow:7"]


def test_database_automation_and_execution_sources_are_project_isolated():
    engine, session = _db_session()
    try:
        project_a = Project(name="Brain Project A")
        project_b = Project(name="Brain Project B")
        session.add_all([project_a, project_b])
        session.flush()

        workflow_a = WorkflowProfile(
            name="Brain Workflow A",
            project_id=project_a.id,
            configuration={"nodes": [], "edges": []},
        )
        workflow_b = WorkflowProfile(
            name="Brain Workflow B",
            project_id=project_b.id,
            configuration={"nodes": [], "edges": []},
        )
        session.add_all([workflow_a, workflow_b])
        session.flush()

        session.add_all([
            WorkflowSchedule(
                workflow_id=workflow_a.id,
                name="Shared schedule A",
                cron_expression="0 9 * * *",
            ),
            WorkflowSchedule(
                workflow_id=workflow_b.id,
                name="Shared schedule B",
                cron_expression="0 10 * * *",
            ),
            WorkflowTrigger(
                workflow_id=workflow_a.id,
                name="Shared trigger A",
                trigger_type=TriggerType.WEBHOOK.value,
                config={"require_signature": True},
                webhook_secret="projectasecret",
            ),
            WorkflowTrigger(
                workflow_id=workflow_b.id,
                name="Shared trigger B",
                trigger_type=TriggerType.WEBHOOK.value,
                config={"require_signature": True},
                webhook_secret="projectbsecret",
            ),
        ])

        task_a = Task(project_id=project_a.id, description="Shared execution A")
        task_b = Task(project_id=project_b.id, description="Shared execution B")
        session.add_all([task_a, task_b])
        session.flush()
        session.add_all([
            ExecutionEvent(
                task_id=task_a.id,
                workflow_id=workflow_a.id,
                event_type="shared_execution",
                event_data={"message": "shared execution A"},
            ),
            ExecutionEvent(
                task_id=task_b.id,
                workflow_id=workflow_b.id,
                event_type="shared_execution",
                event_data={"message": "shared execution B"},
            ),
        ])
        session.commit()

        service = PlatformBrainService()
        service.reindex(session)

        expected_types = {
            "db.schedule": "schedule",
            "db.trigger": "trigger",
            "db.execution_trace": "execution_event",
        }
        for source_type, source_prefix in expected_types.items():
            result = service.query(
                "shared",
                db=session,
                project_id=project_a.id,
                source_types=[source_type],
                top_k=20,
            )

            assert result["total_results"] == 1
            assert result["results"][0]["source_id"].startswith(f"{source_prefix}:")
            assert result["results"][0]["metadata"]["project_id"] == project_a.id
    finally:
        session.close()
        engine.dispose()


def test_database_collectors_filter_by_project_before_materializing_rows():
    engine, session = _db_session()
    try:
        project_a = Project(name="Collector Project A")
        project_b = Project(name="Collector Project B")
        session.add_all([project_a, project_b])
        session.flush()
        session.add_all([
            WorkflowProfile(
                name="Collector Workflow A",
                project_id=project_a.id,
                configuration={"nodes": [], "edges": []},
            ),
            WorkflowProfile(
                name="Collector Workflow B",
                project_id=project_b.id,
                configuration={"nodes": [], "edges": []},
            ),
        ])
        session.commit()

        service = PlatformBrainService()
        sources = service._collect_database_sources(
            session,
            project_id=project_a.id,
            source_types={"db.workflow"},
        )

        assert [source.title for source in sources] == ["Workflow: Collector Workflow A"]
        assert {source.source_type for source in sources} == {"db.workflow"}
    finally:
        session.close()
        engine.dispose()


def test_platform_brain_never_indexes_webhook_secrets():
    engine, session = _db_session()
    try:
        project = Project(name="Secret Project")
        session.add(project)
        session.flush()
        workflow = WorkflowProfile(
            name="Secret Workflow",
            project_id=project.id,
            configuration={"nodes": [], "edges": []},
        )
        session.add(workflow)
        session.flush()
        secret = "brainwebhooksecretxyz"
        session.add(WorkflowTrigger(
            workflow_id=workflow.id,
            name="Secret-safe trigger",
            trigger_type=TriggerType.WEBHOOK.value,
            config={"require_signature": True},
            webhook_secret=secret,
        ))
        session.commit()

        service = PlatformBrainService()
        service.reindex(session)

        indexed_payload = json.dumps(
            [
                {"content": source.content, "metadata": source.metadata}
                for source in service._sources
                if source.source_type == "db.trigger"
            ]
        )
        result = service.query(
            secret,
            db=session,
            source_types=["db.trigger"],
            project_id=project.id,
        )

        assert secret not in indexed_payload
        assert result["total_results"] == 0
    finally:
        session.close()
        engine.dispose()


def test_platform_brain_recursively_redacts_custom_tool_credentials():
    engine, session = _db_session()
    try:
        project = Project(name="Credential Project")
        session.add(project)
        session.flush()
        session.add(CustomTool(
            tool_id="credential_tool",
            name="Credential Tool",
            description="Tool with nested credential fields",
            tool_type=ToolType.API,
            template_type=ToolTemplateType.CUSTOM,
            implementation_config={
                "api_key": "skzqtopapi987",
                "nested_token": "tokzqnested654",
                "headers": {"Authorization": "bearerzqprivate321"},
                "destinations": [{"webhook_secret": "hookzqdeep999"}],
            },
            input_schema={"type": "object", "properties": {}},
            project_id=project.id,
        ))
        session.commit()

        service = PlatformBrainService()
        service.reindex(session)

        indexed_payload = json.dumps(
            [source.content for source in service._sources if source.source_type == "db.custom_tool"]
        )
        assert "REDACTED" in indexed_payload
        for secret in (
            "skzqtopapi987",
            "tokzqnested654",
            "bearerzqprivate321",
            "hookzqdeep999",
        ):
            assert secret not in indexed_payload
            assert service.query(
                secret,
                project_id=project.id,
                source_types=["db.custom_tool"],
            )["total_results"] == 0
    finally:
        session.close()
        engine.dispose()


def test_database_redaction_preserves_non_secret_token_configuration():
    serialized = _safe_database_json({
        "max_tokens": 4096,
        "token_count": 12,
        "token_limits": {"daily": 1000},
        "nested_token": "private-token",
        "access_token": "private-access-token",
        "max_access_token": "private-max-access-token",
    })

    assert '"max_tokens": 4096' in serialized
    assert '"token_count": 12' in serialized
    assert '"token_limits": {"daily": 1000}' in serialized
    assert "private-token" not in serialized
    assert "private-access-token" not in serialized
    assert "private-max-access-token" not in serialized
