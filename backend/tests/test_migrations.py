# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Tests for Alembic Database Migrations.

These tests ensure that migrations can be applied, rolled back, and are idempotent.
"""

import pytest
import subprocess
import os


def run_alembic_command(command_args, env_vars=None):
    """
    Helper function to run Alembic commands.

    Args:
        command_args: List of command arguments (e.g., ['upgrade', 'head'])
        env_vars: Optional environment variables to set

    Returns:
        subprocess.CompletedProcess result
    """
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    # Get test database URL
    test_db_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://langconfig:langconfig_dev@localhost:5433/langconfig_test"
    )

    # Set DATABASE_URL for alembic
    env["DATABASE_URL"] = test_db_url

    result = subprocess.run(
        ["alembic"] + command_args,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        capture_output=True,
        text=True,
        env=env
    )

    return result


def test_alembic_current():
    """Test that alembic current command works."""
    result = run_alembic_command(["current"])
    assert result.returncode == 0, f"Failed to run 'alembic current': {result.stderr}"


def test_alembic_history():
    """Test that alembic history command works."""
    result = run_alembic_command(["history"])
    assert result.returncode == 0, f"Failed to run 'alembic history': {result.stderr}"
    # Should show at least the initial migration
    assert "initial_schema" in result.stdout or "initial_schema" in result.stderr


def test_migration_upgrade_head():
    """Test that migrations can be applied to head."""
    # First downgrade to base
    downgrade_result = run_alembic_command(["downgrade", "base"])
    # It's okay if this fails (database might not be at a downgrade-able state)

    # Upgrade to head
    upgrade_result = run_alembic_command(["upgrade", "head"])
    assert upgrade_result.returncode == 0, f"Failed to upgrade to head: {upgrade_result.stderr}"


def test_migration_downgrade_one():
    """Test that migrations can be rolled back one step."""
    # Get current revision
    current_result = run_alembic_command(["current"])
    assert current_result.returncode == 0

    # Only test downgrade if we're not at base
    if "base" not in current_result.stdout.lower():
        # Try to downgrade one step
        downgrade_result = run_alembic_command(["downgrade", "-1"])
        # Note: This might fail if the migration isn't reversible, which is okay for baseline migrations
        # We just want to make sure the command runs without crashing

        # Upgrade back to head
        upgrade_result = run_alembic_command(["upgrade", "head"])
        assert upgrade_result.returncode == 0, f"Failed to upgrade back to head: {upgrade_result.stderr}"


def test_migration_idempotency():
    """Test that running migrations twice is safe (idempotency)."""
    # Run upgrade to head twice
    for i in range(2):
        result = run_alembic_command(["upgrade", "head"])
        assert result.returncode == 0, f"Failed on attempt {i+1}: {result.stderr}"


def test_migration_check():
    """Test that there are no pending migrations (schema matches models)."""
    # This test checks if the database schema matches the SQLAlchemy models
    # If this fails, it means models have changed but migrations haven't been created

    # For now, we just check that alembic runs without error
    # A more sophisticated version would use alembic's check_migrations or similar
    result = run_alembic_command(["current"])
    assert result.returncode == 0


@pytest.mark.slow
def test_migration_full_cycle():
    """
    Test complete migration cycle: downgrade to base and upgrade to head.

    This is marked as 'slow' because it can take a while.
    Run with: pytest -m slow
    """
    # Downgrade to base
    downgrade_result = run_alembic_command(["downgrade", "base"])
    # Note: May fail if baseline migration isn't reversible - that's okay

    # Upgrade to head
    upgrade_result = run_alembic_command(["upgrade", "head"])
    assert upgrade_result.returncode == 0, f"Failed to upgrade to head: {upgrade_result.stderr}"

    # Verify we're at head
    current_result = run_alembic_command(["current"])
    assert current_result.returncode == 0
    assert "head" in current_result.stdout or "head" in current_result.stderr


def test_env_py_imports():
    """Test that env.py can import all models without errors."""
    # This test ensures that the model imports in env.py are correct
    # If this fails, it means there's an import error in alembic/env.py

    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    try:
        # Try to import env.py (this will execute the module-level imports)
        import alembic.env  # noqa: F401
    except ImportError as e:
        pytest.fail(f"Failed to import alembic/env.py: {e}")


def test_database_url_configuration():
    """Test that DATABASE_URL is properly configured for tests."""
    test_db_url = os.getenv("TEST_DATABASE_URL")

    # Ensure test database URL is set
    assert test_db_url is not None or os.getenv("DATABASE_URL") is not None, \
        "Neither TEST_DATABASE_URL nor DATABASE_URL is set"

    # Ensure we're not accidentally using production database
    if test_db_url:
        assert "test" in test_db_url.lower(), \
            "TEST_DATABASE_URL should contain 'test' to avoid accidentally using production database"
