# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Database initialization for Custom Tools.

Run this script to seed default custom tools for new users.

Usage:
    python backend/db/init_custom_tools.py
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import engine, SessionLocal, Base
from models.custom_tool import CustomTool, ToolExecutionLog
from core.tools.seed import seed_custom_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_custom_tool_tables():
    """Initialize CustomTool tables in the database."""
    try:
        logger.info("Initializing Custom Tool tables...")

        # Import all models to register them with Base
        from models import custom_tool

        # Create all tables
        Base.metadata.create_all(bind=engine)

        logger.info("✓ Custom Tool tables created successfully")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to create Custom Tool tables: {e}")
        return False


def seed_tools():
    """Seed the database with pre-configured custom tools."""
    try:
        logger.info("Seeding custom tools...")

        db = SessionLocal()
        try:
            results = seed_custom_tools(db)
            logger.info(f"✓ Custom tools seeded: {results['created']} created, {results['skipped']} skipped")
            for detail in results.get("details", []):
                logger.info(f"  - {detail}")
            return True
        finally:
            db.close()

    except Exception as e:
        logger.error(f"✗ Failed to seed custom tools: {e}")
        return False


def verify_tools():
    """Verify that custom tools were created correctly."""
    try:
        db = SessionLocal()

        # Check if tables exist by querying them
        tool_count = db.query(CustomTool).count()
        log_count = db.query(ToolExecutionLog).count()

        logger.info(f"✓ Verification complete:")
        logger.info(f"  - custom_tools: {tool_count} records")
        logger.info(f"  - tool_execution_logs: {log_count} records")

        # List the tools
        tools = db.query(CustomTool).all()
        if tools:
            logger.info("  - Available tools:")
            for tool in tools:
                logger.info(f"    * {tool.tool_id}: {tool.name} ({tool.tool_type.value})")

        db.close()
        return True

    except Exception as e:
        logger.error(f"✗ Verification failed: {e}")
        return False


def main():
    """Main entry point for custom tool initialization."""
    logger.info("=" * 50)
    logger.info("Custom Tool Database Initialization")
    logger.info("=" * 50)

    # Step 1: Create tables
    if not init_custom_tool_tables():
        logger.error("Table creation failed, aborting")
        return False

    # Step 2: Seed tools
    if not seed_tools():
        logger.error("Tool seeding failed, but tables were created")
        # Continue to verification anyway

    # Step 3: Verify
    if not verify_tools():
        logger.warning("Verification had issues")

    logger.info("=" * 50)
    logger.info("Custom Tool initialization complete!")
    logger.info("=" * 50)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
