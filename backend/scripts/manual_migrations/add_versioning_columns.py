# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Database Migration: Add Optimistic Locking Columns


Adds lock_version columns to tables for optimistic locking.

Tables Updated:
- workflow_profiles: Add lock_version column (default: 1)
- deep_agent_templates: Add lock_version column (default: 1)

This enables detection of concurrent modifications:
- User A and B both load workflow with lock_version=5
- User A updates → lock_version becomes 6
- User B tries to update with lock_version=5 → Conflict detected!

Note: Column named 'lock_version' to avoid conflicts with semantic versioning fields.

Usage:
    python backend/migrations/add_versioning_columns.py

Rollback:
    python backend/migrations/add_versioning_columns.py --rollback
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, MetaData, inspect
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def get_database_url():
    """Get database URL from environment variables."""
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://langconfig:langconfig_dev@localhost:5433/langconfig"
    )
    logger.info(f"Using database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    return db_url


def column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if column exists in table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    exists = column_name in columns
    logger.info(f"Column '{table_name}.{column_name}' exists: {exists}")
    return exists


def table_exists(engine, table_name: str) -> bool:
    """Check if table exists in database."""
    inspector = inspect(engine)
    exists = table_name in inspector.get_table_names()
    logger.info(f"Table '{table_name}' exists: {exists}")
    return exists


def migrate_up(engine):
    """
    Apply migration: Add lock_version columns for optimistic locking.

    Adds lock_version column to:
    - workflow_profiles (default: 1)
    - deep_agent_templates (default: 1)

    Lock version column:
    - Type: INTEGER
    - NOT NULL
    - Default: 1
    - Increments on every update
    """
    logger.info("=" * 80)
    logger.info("MIGRATION: Add Optimistic Locking Columns (lock_version)")
    logger.info("=" * 80)

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # ================================================================
            # Add lock_version column to workflow_profiles
            # ================================================================

            if not table_exists(engine, "workflow_profiles"):
                logger.warning("Table 'workflow_profiles' does not exist. Skipping.")
            elif column_exists(engine, "workflow_profiles", "lock_version"):
                logger.warning("Column 'workflow_profiles.lock_version' already exists. Skipping.")
            else:
                logger.info("Adding lock_version column to workflow_profiles...")

                # Add column with default value
                conn.execute(text("""
                    ALTER TABLE workflow_profiles
                    ADD COLUMN lock_version INTEGER NOT NULL DEFAULT 1
                """))

                logger.info("✓ Added lock_version column to workflow_profiles")

                # Set existing rows to lock_version=1 (already done by DEFAULT)
                result = conn.execute(text("""
                    UPDATE workflow_profiles
                    SET lock_version = 1
                    WHERE lock_version IS NULL
                """))

                if result.rowcount > 0:
                    logger.info(f"✓ Initialized lock_version=1 for {result.rowcount} existing workflows")

            # ================================================================
            # Add lock_version column to deep_agent_templates
            # ================================================================

            if not table_exists(engine, "deep_agent_templates"):
                logger.warning("Table 'deep_agent_templates' does not exist. Skipping.")
            elif column_exists(engine, "deep_agent_templates", "lock_version"):
                logger.warning("Column 'deep_agent_templates.lock_version' already exists. Skipping.")
            else:
                logger.info("Adding lock_version column to deep_agent_templates...")

                # Add column with default value
                conn.execute(text("""
                    ALTER TABLE deep_agent_templates
                    ADD COLUMN lock_version INTEGER NOT NULL DEFAULT 1
                """))

                logger.info("✓ Added lock_version column to deep_agent_templates")

                # Set existing rows to lock_version=1 (already done by DEFAULT)
                result = conn.execute(text("""
                    UPDATE deep_agent_templates
                    SET lock_version = 1
                    WHERE lock_version IS NULL
                """))

                if result.rowcount > 0:
                    logger.info(f"✓ Initialized lock_version=1 for {result.rowcount} existing agents")

            # Commit transaction
            trans.commit()
            logger.info("=" * 80)
            logger.info("✅ Migration completed successfully!")
            logger.info("=" * 80)

            # Summary
            logger.info("")
            logger.info("Summary:")
            logger.info("- Added lock_version column to workflow_profiles (default: 1)")
            logger.info("- Added lock_version column to deep_agent_templates (default: 1)")
            logger.info("- All existing records initialized to lock_version=1")
            logger.info("")
            logger.info("Optimistic locking is now enabled!")
            logger.info("Lock version will auto-increment on every update.")
            logger.info("Concurrent modifications will be detected and prevented.")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"❌ Migration failed: {e}")
            logger.error("Transaction rolled back")
            raise


def migrate_down(engine):
    """
    Rollback migration: Remove lock_version columns.

    WARNING: This will remove optimistic locking!
    Concurrent modifications will no longer be detected.
    """
    logger.info("=" * 80)
    logger.info("ROLLBACK: Remove Optimistic Locking Columns (lock_version)")
    logger.info("=" * 80)

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # Remove lock_version from workflow_profiles
            if table_exists(engine, "workflow_profiles") and column_exists(engine, "workflow_profiles", "lock_version"):
                logger.info("Removing lock_version column from workflow_profiles...")
                conn.execute(text("""
                    ALTER TABLE workflow_profiles
                    DROP COLUMN lock_version
                """))
                logger.info("✓ Removed lock_version column from workflow_profiles")

            # Remove lock_version from deep_agent_templates
            if table_exists(engine, "deep_agent_templates") and column_exists(engine, "deep_agent_templates", "lock_version"):
                logger.info("Removing lock_version column from deep_agent_templates...")
                conn.execute(text("""
                    ALTER TABLE deep_agent_templates
                    DROP COLUMN lock_version
                """))
                logger.info("✓ Removed lock_version column from deep_agent_templates")

            # Commit transaction
            trans.commit()
            logger.info("=" * 80)
            logger.info("✅ Rollback completed successfully!")
            logger.info("=" * 80)

            logger.warning("⚠️  Optimistic locking is now DISABLED!")
            logger.warning("Concurrent modifications will NOT be detected.")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"❌ Rollback failed: {e}")
            logger.error("Transaction rolled back")
            raise


def main():
    """Main migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Versioning Columns Migration")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (remove version columns)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    # Get database URL
    db_url = get_database_url()

    # Create engine
    engine = create_engine(db_url)

    try:
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
            logger.info(f"Would {'rollback' if args.rollback else 'apply'} migration")

            # Show what tables would be affected
            if args.rollback:
                logger.info("Would remove lock_version column from:")
            else:
                logger.info("Would add lock_version column to:")

            if table_exists(engine, "workflow_profiles"):
                logger.info("  - workflow_profiles")
            if table_exists(engine, "deep_agent_templates"):
                logger.info("  - deep_agent_templates")

            return

        if args.rollback:
            migrate_down(engine)
        else:
            migrate_up(engine)

    except Exception as e:
        logger.error(f"Migration script failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
