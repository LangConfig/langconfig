# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Pytest Configuration and Fixtures for LangConfig Backend Tests.

Provides test database fixtures for isolated testing.
"""

import pytest
import os
import subprocess
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from db.database import Base
import models  # noqa: F401 - register all application models with Base
from tests.database_safety import is_disposable_test_database

# Test database URL - separate from production
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://langconfig:langconfig_dev@localhost:5433/langconfig_test"
)


@pytest.fixture(scope="session")
async def test_db_engine():
    """
    Create test database engine.

    This fixture:
    1. Creates a test database engine
    2. Rebuilds current metadata and stamps the Alembic head
    3. Yields the engine for tests
    4. Cleans up on teardown
    """
    if not is_disposable_test_database(TEST_DATABASE_URL):
        raise RuntimeError("TEST_DATABASE_URL must name a disposable test database")

    # Create test engine
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Rebuild the disposable test schema from current metadata. The historical
    # baseline migration upgrades legacy schemas and cannot bootstrap an empty DB.
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
            await connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(Base.metadata.create_all)

        sync_database_url = TEST_DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql://"
        )
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "stamp", "head"],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": sync_database_url},
        )

        if result.returncode != 0:
            raise Exception(f"Failed to stamp test schema: {result.stderr}")

    except Exception as e:
        await engine.dispose()
        raise Exception(f"Failed to initialize test database: {e}")

    yield engine

    # Cleanup
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine):
    """
    Create test database session for each test.

    This fixture:
    1. Creates a new session for each test
    2. Yields the session
    3. Rolls back any changes after the test (test isolation)
    4. Closes the session

    Each test gets a clean database state.
    """
    # Create session factory
    async_session = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Create session
    async with async_session() as session:
        # Start a transaction
        async with session.begin():
            yield session
            # Rollback transaction after test (ensures test isolation)
            await session.rollback()


@pytest.fixture(scope="function")
async def test_db_session_commit(test_db_engine):
    """
    Create test database session that commits changes.

    Use this fixture when you need to test actual database commits
    or when testing database constraints, triggers, etc.

    WARNING: This does NOT rollback changes. Use sparingly and clean up manually.
    """
    # Create session factory
    async_session = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Create session
    async with async_session() as session:
        yield session
        await session.close()


# Example fixtures for common test data
@pytest.fixture
def sample_workflow_data():
    """Sample workflow data for testing."""
    return {
        "name": "Test Workflow",
        "description": "A test workflow",
        "graph_json": {
            "nodes": [],
            "edges": []
        }
    }


@pytest.fixture
def sample_project_data():
    """Sample project data for testing."""
    return {
        "name": "Test Project",
        "description": "A test project"
    }


@pytest.fixture
def sample_task_data():
    """Sample task data for testing."""
    return {
        "title": "Test Task",
        "description": "A test task"
    }
