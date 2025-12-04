# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Migration: Rename audit_logs.metadata to additional_context

This migration renames the 'metadata' column to 'additional_context' to avoid
conflicts with SQLAlchemy's reserved 'metadata' attribute.

Run this migration if you have an existing audit_logs table.
"""

from sqlalchemy import text
from db.database import engine, SessionLocal
import logging

logger = logging.getLogger(__name__)


def migrate():
    """Rename metadata column to additional_context in audit_logs table."""
    db = SessionLocal()

    try:
        # Check if audit_logs table exists (PostgreSQL)
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'audit_logs'
            )
        """))

        if not result.scalar():
            logger.info("audit_logs table does not exist, skipping migration")
            return

        # Check if metadata column exists (PostgreSQL)
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'audit_logs'
        """))
        columns = [row[0] for row in result.fetchall()]

        if 'metadata' not in columns:
            logger.info("metadata column does not exist, skipping migration")
            return

        if 'additional_context' in columns:
            logger.info("additional_context column already exists, skipping migration")
            return

        logger.info("Renaming metadata column to additional_context...")

        # PostgreSQL supports ALTER COLUMN RENAME directly
        db.execute(text("""
            ALTER TABLE audit_logs
            RENAME COLUMN metadata TO additional_context
        """))

        db.commit()
        logger.info("✅ Successfully renamed metadata column to additional_context")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate()
