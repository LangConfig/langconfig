# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Database Migration: Add Background Tasks Table


Creates the background_tasks table for PostgreSQL-backed task queue.

Features:
- Task lifecycle tracking (PENDING → RUNNING → COMPLETED/FAILED)
- Priority-based task selection
- Retry logic with configurable max retries
- JSONB payload and result storage
- Comprehensive indexing for efficient task claiming

Usage:
    python backend/migrations/add_background_tasks_table.py

Rollback:
    python backend/migrations/add_background_tasks_table.py --rollback
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


def table_exists(engine, table_name: str) -> bool:
    """Check if table exists in database."""
    inspector = inspect(engine)
    exists = table_name in inspector.get_table_names()
    logger.info(f"Table '{table_name}' exists: {exists}")
    return exists


def migrate_up(engine):
    """
    Apply migration: Create background_tasks table.

    Table Schema:
    - id: Serial primary key
    - task_type: Type of task (e.g., 'export_agent')
    - payload: JSONB task input data
    - priority: Integer priority (higher = more urgent)
    - status: VARCHAR(20) - PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    - result: JSONB task output data
    - error: TEXT error message
    - retry_count: Integer retry attempts
    - max_retries: Integer maximum retries
    - created_at: Timestamp with timezone
    - started_at: Timestamp with timezone (nullable)
    - completed_at: Timestamp with timezone (nullable)

    Indexes:
    - Primary key on id
    - Index on task_type for filtering by type
    - Composite index on (status, priority DESC, created_at) for efficient task claiming
    """
    logger.info("=" * 80)
    logger.info("MIGRATION: Add Background Tasks Table")
    logger.info("=" * 80)

    # Check if table already exists
    if table_exists(engine, "background_tasks"):
        logger.warning("Table 'background_tasks' already exists. Skipping migration.")
        return

    logger.info("Creating background_tasks table...")

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # Create background_tasks table
            conn.execute(text("""
                CREATE TABLE background_tasks (
                    id SERIAL PRIMARY KEY,
                    task_type VARCHAR(100) NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    priority INTEGER NOT NULL DEFAULT 50,
                    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                    result JSONB,
                    error TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ
                )
            """))
            logger.info("✓ Created background_tasks table")

            # Create indexes
            logger.info("Creating indexes...")

            # Index for filtering by task type
            conn.execute(text("""
                CREATE INDEX idx_background_tasks_type
                ON background_tasks(task_type)
            """))
            logger.info("✓ Created index on task_type")

            # Composite index for efficient task claiming
            # Workers will query: WHERE status='PENDING' ORDER BY priority DESC, created_at
            conn.execute(text("""
                CREATE INDEX idx_background_tasks_status_priority
                ON background_tasks(status, priority DESC, created_at)
            """))
            logger.info("✓ Created composite index on (status, priority, created_at)")

            # Index on status for status filtering
            conn.execute(text("""
                CREATE INDEX idx_background_tasks_status
                ON background_tasks(status)
            """))
            logger.info("✓ Created index on status")

            # Index on created_at for time-based queries
            conn.execute(text("""
                CREATE INDEX idx_background_tasks_created_at
                ON background_tasks(created_at)
            """))
            logger.info("✓ Created index on created_at")

            # Add check constraint on status
            conn.execute(text("""
                ALTER TABLE background_tasks
                ADD CONSTRAINT chk_background_tasks_status
                CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'))
            """))
            logger.info("✓ Added check constraint on status")

            # Add check constraint on priority
            conn.execute(text("""
                ALTER TABLE background_tasks
                ADD CONSTRAINT chk_background_tasks_priority
                CHECK (priority >= 0 AND priority <= 100)
            """))
            logger.info("✓ Added check constraint on priority")

            # Add check constraint on retry_count
            conn.execute(text("""
                ALTER TABLE background_tasks
                ADD CONSTRAINT chk_background_tasks_retry_count
                CHECK (retry_count >= 0 AND retry_count <= max_retries)
            """))
            logger.info("✓ Added check constraint on retry_count")

            # Commit transaction
            trans.commit()
            logger.info("=" * 80)
            logger.info("✅ Migration completed successfully!")
            logger.info("=" * 80)

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"❌ Migration failed: {e}")
            logger.error("Transaction rolled back")
            raise


def migrate_down(engine):
    """
    Rollback migration: Drop background_tasks table.

    WARNING: This will delete all task data!
    """
    logger.info("=" * 80)
    logger.info("ROLLBACK: Drop Background Tasks Table")
    logger.info("=" * 80)

    # Check if table exists
    if not table_exists(engine, "background_tasks"):
        logger.warning("Table 'background_tasks' does not exist. Nothing to rollback.")
        return

    logger.warning("⚠️  This will delete all background task data!")
    logger.info("Dropping background_tasks table...")

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # Drop table (cascades to indexes and constraints)
            conn.execute(text("DROP TABLE IF EXISTS background_tasks CASCADE"))

            # Commit transaction
            trans.commit()
            logger.info("=" * 80)
            logger.info("✅ Rollback completed successfully!")
            logger.info("=" * 80)

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"❌ Rollback failed: {e}")
            logger.error("Transaction rolled back")
            raise


def main():
    """Main migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Background Tasks Table Migration")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (drop table)"
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
