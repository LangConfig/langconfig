# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Database Migration: Add Export Status Tracking

Adds columns to workflow_profiles table to track auto-export status.

This enables:
- Tracking export status (pending, in_progress, completed, failed)
- Recording export errors
- Timestamp of last successful export
- Ability to retry failed exports

Usage:
    # Execute migration
    python migrations/add_export_status_tracking.py

    # Rollback (remove columns)
    python migrations/add_export_status_tracking.py --rollback
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# Migration Functions
# =============================================================================

def add_export_columns(session, dry_run: bool = False):
    """
    Add export status tracking columns to workflow_profiles table.

    Columns added:
    - export_status: VARCHAR(50) - 'pending', 'in_progress', 'completed', 'failed'
    - export_error: TEXT - Error message if export failed
    - last_export_at: TIMESTAMPTZ - Timestamp of last successful export

    Args:
        session: Database session
        dry_run: If True, only simulate the migration
    """
    logger.info(f"{'DRY RUN: ' if dry_run else ''}Adding export status columns...")

    queries = [
        text("""
            ALTER TABLE workflow_profiles
            ADD COLUMN IF NOT EXISTS export_status VARCHAR(50)
        """),
        text("""
            ALTER TABLE workflow_profiles
            ADD COLUMN IF NOT EXISTS export_error TEXT
        """),
        text("""
            ALTER TABLE workflow_profiles
            ADD COLUMN IF NOT EXISTS last_export_at TIMESTAMPTZ
        """)
    ]

    if not dry_run:
        for query in queries:
            try:
                session.execute(query)
                logger.info(f"  Executed: {query.text.strip()}")
            except Exception as e:
                logger.error(f"  Failed to execute query: {e}")
                raise

        session.commit()
        logger.info("✓ Export status columns added successfully")
    else:
        logger.info("✓ DRY RUN: Would add export status columns")
        for query in queries:
            logger.info(f"  Would execute: {query.text.strip()}")


def remove_export_columns(session):
    """
    Remove export status tracking columns from workflow_profiles table (rollback).

    Args:
        session: Database session
    """
    logger.info("Removing export status columns...")

    queries = [
        text("ALTER TABLE workflow_profiles DROP COLUMN IF EXISTS export_status"),
        text("ALTER TABLE workflow_profiles DROP COLUMN IF EXISTS export_error"),
        text("ALTER TABLE workflow_profiles DROP COLUMN IF EXISTS last_export_at")
    ]

    for query in queries:
        try:
            session.execute(query)
            logger.info(f"  Executed: {query.text.strip()}")
        except Exception as e:
            logger.error(f"  Failed to execute query: {e}")
            raise

    session.commit()
    logger.info("✓ Export status columns removed successfully")


def verify_columns(session):
    """
    Verify that the export status columns exist.

    Args:
        session: Database session

    Returns:
        dict: Status of each column
    """
    logger.info("Verifying export status columns...")

    columns = ["export_status", "export_error", "last_export_at"]
    results = {}

    for column in columns:
        query = text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'workflow_profiles'
            AND column_name = :column_name
        """)

        result = session.execute(query, {"column_name": column}).fetchone()

        if result:
            results[column] = {
                "exists": True,
                "data_type": result[1]
            }
            logger.info(f"  ✓ Column '{column}' exists (type: {result[1]})")
        else:
            results[column] = {
                "exists": False,
                "data_type": None
            }
            logger.warning(f"  ✗ Column '{column}' does not exist")

    return results


# =============================================================================
# Main CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Add export status tracking columns to workflow_profiles"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Remove the export status columns"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify columns exist"
    )

    args = parser.parse_args()

    # Get database URL from environment
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://langconfig:langconfig_dev@localhost:5433/langconfig"
    )

    # Create database session
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Verify mode
        if args.verify:
            results = verify_columns(session)
            all_exist = all(r["exists"] for r in results.values())

            if all_exist:
                logger.info("\n✓ All export status columns exist")
                return 0
            else:
                logger.warning("\n✗ Some export status columns are missing")
                return 1

        # Rollback mode
        if args.rollback:
            remove_export_columns(session)
            logger.info("\n=== Rollback Complete ===")
            logger.info("✓ Export status columns removed")
            return 0

        # Migration mode
        logger.info("=== Starting Migration ===\n")

        # Add columns
        add_export_columns(session, dry_run=args.dry_run)

        # Summary
        logger.info("\n=== Migration Summary ===")
        if args.dry_run:
            logger.info("✓ DRY RUN completed successfully")
            logger.info("Run without --dry-run to execute migration")
        else:
            logger.info("✓ Migration completed successfully")
            logger.info("\nExport status tracking columns added:")
            logger.info("  - export_status: VARCHAR(50) - Current export status")
            logger.info("  - export_error: TEXT - Error message if failed")
            logger.info("  - last_export_at: TIMESTAMPTZ - Last successful export time")

            # Verify
            logger.info("\nVerifying columns...")
            verify_columns(session)

        return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return 1

    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
