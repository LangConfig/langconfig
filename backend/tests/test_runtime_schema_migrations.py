"""Exercise the schema-only upgrade with legacy rows and no runtime fixtures."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import models
import pytest
from db.database import Base
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from tests.database_safety import is_disposable_test_database

BACKEND_ROOT = Path(__file__).resolve().parents[1]
BASELINE = "022_add_hermes_drafts"
HEAD = "026_subagent_jobs"
NEW_TABLES = {"workflow_evaluations", "workflow_evaluation_cases", "subagent_jobs"}
LEGACY_TABLES = (
    "projects", "workflow_profiles", "workflow_versions", "tasks",
    "workflow_executions", "git_repositories", "skills",
)


def alembic(database_url, *arguments, check=True):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments], cwd=BACKEND_ROOT,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True, text=True, timeout=60, check=False,
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def rebuild_current_schema(engine, database_url):
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(connection)
    alembic(database_url, "stamp", HEAD)


@pytest.fixture
def schema_database():
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("Set TEST_DATABASE_URL to an exclusively owned disposable database")
    if not is_disposable_test_database(raw_url):
        pytest.fail("TEST_DATABASE_URL must name a disposable test database")
    parsed = make_url(raw_url)
    if parsed.get_backend_name() != "postgresql":
        pytest.fail("The runtime schema migration regression requires PostgreSQL")
    database_url = parsed.set(drivername="postgresql").render_as_string(hide_password=False)
    engine = create_engine(database_url)
    try:
        # Historical revision 001 upgrades an existing schema. Bootstrap using
        # the supported fresh-install metadata path, then use real migrations
        # to reach revision 022 before inserting any regression data.
        rebuild_current_schema(engine, database_url)
        alembic(database_url, "downgrade", BASELINE)
        yield engine, database_url
    finally:
        try:
            # Explicit legacy IDs do not advance PostgreSQL sequences. Leave
            # a clean current schema so later tests and repeated runs cannot
            # collide with seeded rows or inherit a partially downgraded DB.
            rebuild_current_schema(engine, database_url)
        finally:
            engine.dispose()


def reflect(engine, name):
    return Table(name, MetaData(), autoload_with=engine)


def seed_legacy_records(engine):
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)
    tables = {name: reflect(engine, name) for name in LEGACY_TABLES}
    with engine.begin() as connection:
        connection.execute(tables["projects"].insert(), [
            {"id": 1, "name": "Legacy project", "configuration": {"kept": True}},
            {"id": 2, "name": "Other project", "configuration": {}},
        ])
        connection.execute(tables["workflow_profiles"].insert(), {
            "id": 1, "name": "Legacy workflow", "project_id": 1,
            "configuration": {"nodes": [{"id": "legacy-node"}], "edges": []},
            "is_template": False, "usage_count": 3, "debug_mode": False,
            "created_at": now, "updated_at": now,
        })
        connection.execute(tables["workflow_versions"].insert(), {
            "id": 1, "workflow_id": 1, "version_number": 7,
            "config_snapshot": {"legacy": "preserved"}, "notes": "Original notes",
            "is_current": True, "created_at": now,
        })
        connection.execute(tables["tasks"].insert(), {
            "id": 1, "project_id": 1, "workflow_profile_id": 1,
            "description": "Completed legacy task", "status": "completed",
            "result": {"answer": "kept"}, "execution_logs": {"entries": ["original"]},
        })
        connection.execute(tables["workflow_executions"].insert(), {
            "id": 1, "workflow_id": 1, "version_id": 1,
            "execution_results": {"legacy_output": [1, 2, 3]}, "status": "success",
            "token_usage": {"input_tokens": 100}, "cost": 0.25, "completed_at": now,
        })
        connection.execute(tables["git_repositories"].insert(), {
            "id": 1, "project_id": 1, "clone_url": "https://example.invalid/legacy.git",
            "repo_name": "legacy", "local_path": "C:/legacy/project",
            "branch": "main", "indexed_files_count": 0,
        })
        skill = {
            "id": 1, "skill_id": "legacy-skill", "name": "Legacy skill",
            "description": "Preserved instructions", "instructions": "Keep these instructions.",
            "version": "1.0.0", "source_type": "personal", "source_path": "/personal/legacy-skill",
            "project_id": None, "tags": ["legacy"], "triggers": [], "required_context": [],
            "usage_count": 4, "avg_success_rate": 1.0, "file_modified_at": now,
            "indexed_at": now, "created_at": now, "updated_at": now,
        }
        connection.execute(tables["skills"].insert(), [skill, {
            **skill, "id": 2, "skill_id": "project-skill", "source_type": "project",
            "source_path": "c:\\LEGACY\\project\\.langconfig\\skills\\project-skill",
        }])
    return tables


def snapshot_rows(engine, tables):
    with engine.connect() as connection:
        return {name: [dict(row) for row in connection.execute(
            select(table).order_by(table.c.id)
        ).mappings()] for name, table in tables.items()}


def original_columns(engine):
    inspector = inspect(engine)
    return {name: {column["name"]: (str(column["type"]), column["nullable"])
                   for column in inspector.get_columns(name)} for name in LEGACY_TABLES}


def assert_legacy_preserved(engine, tables, rows, columns):
    assert snapshot_rows(engine, tables) == rows
    current = original_columns(engine)
    for table_name, expected in columns.items():
        assert {name: current[table_name][name] for name in expected} == expected


def assert_scoped_skill_constraints(engine):
    skills = reflect(engine, "skills")
    with engine.begin() as connection:
        original = dict(connection.execute(select(skills).where(skills.c.id == 1)).mappings().one())
        # Same name in different projects and in the global scope is allowed.
        connection.execute(skills.insert(), [
            {**original, "id": 10, "project_id": 1},
            {**original, "id": 11, "project_id": 2},
        ])
        for scope in (None, 1, 2):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(skills.insert(), {**original, "id": 12, "project_id": scope})


def test_new_models_registered_for_fresh_install():
    assert "SubagentJob" in models.__all__
    assert models.SubagentJob.__table__ is Base.metadata.tables["subagent_jobs"]
    assert models.Skill.__table__ is Base.metadata.tables["skills"]
    assert NEW_TABLES <= Base.metadata.tables.keys()


def test_populated_022_upgrade_downgrade_and_reupgrade(schema_database):
    engine, database_url = schema_database
    assert not NEW_TABLES.intersection(inspect(engine).get_table_names())
    assert "runtime_snapshot" not in original_columns(engine)["workflow_versions"]
    tables = seed_legacy_records(engine)
    rows, columns = snapshot_rows(engine, tables), original_columns(engine)
    # The only intentional legacy-row change is an unambiguous project-skill
    # backfill; downgrade preserves that repaired ownership association.
    rows["skills"][1]["project_id"] = 1

    alembic(database_url, "upgrade", HEAD)
    assert_legacy_preserved(engine, tables, rows, columns)
    with engine.connect() as connection:
        assert connection.execute(text(
            "SELECT dispatch_generation, cancel_requested, dispatch_state FROM tasks WHERE id = 1"
        )).one() == (0, False, None)
        assert connection.execute(text(
            "SELECT runtime_snapshot FROM workflow_versions WHERE id = 1"
        )).scalar_one() is None
    assert NEW_TABLES <= set(inspect(engine).get_table_names())
    assert len(inspect(engine).get_foreign_keys("subagent_jobs")) == 4
    assert_scoped_skill_constraints(engine)

    rejected = alembic(database_url, "downgrade", BASELINE, check=False)
    assert rejected.returncode != 0
    assert "Cannot downgrade scoped skills while duplicate names exist" in rejected.stderr
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD
    assert NEW_TABLES <= set(inspect(engine).get_table_names())
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM skills WHERE id IN (10, 11)"))

    alembic(database_url, "downgrade", BASELINE)
    assert_legacy_preserved(engine, tables, rows, columns)
    assert original_columns(engine) == columns
    assert not NEW_TABLES.intersection(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == BASELINE
    indexes = inspect(engine).get_indexes("skills")
    assert any(index["column_names"] == ["skill_id"] and index["unique"] for index in indexes)

    alembic(database_url, "upgrade", HEAD)
    assert_legacy_preserved(engine, tables, rows, columns)
    assert_scoped_skill_constraints(engine)
