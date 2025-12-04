# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Migration: Add project_id column to workflow_profiles table
"""
from sqlalchemy import text
from db.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_project_id_column():
    """Add project_id column to workflow_profiles table if it doesn't exist."""
    try:
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'workflow_profiles'
                AND column_name = 'project_id'
            """))

            if result.fetchone() is None:
                # Column doesn't exist, add it
                logger.info("Adding project_id column to workflow_profiles table...")
                conn.execute(text("""
                    ALTER TABLE workflow_profiles
                    ADD COLUMN project_id INTEGER REFERENCES projects(id)
                """))
                conn.commit()
                logger.info("✓ Successfully added project_id column")
            else:
                logger.info("✓ project_id column already exists")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    add_project_id_column()
