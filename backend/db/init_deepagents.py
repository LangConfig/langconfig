# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Database initialization for DeepAgent tables.

Run this script to create the DeepAgent tables and seed initial templates.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import engine, SessionLocal, init_db, Base
from models.deep_agent import DeepAgentTemplate, AgentExport, ChatSession
from core.templates.deep_agent import seed_deepagent_templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_deepagent_tables():
    """Initialize DeepAgent tables in the database."""
    try:
        logger.info("Initializing DeepAgent tables...")

        # Import all models to register them with Base
        from models import deep_agent

        # Create all tables
        Base.metadata.create_all(bind=engine)

        logger.info("✓ DeepAgent tables created successfully")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to create DeepAgent tables: {e}")
        return False


async def seed_templates():
    """Seed the database with pre-configured templates."""
    try:
        logger.info("Seeding DeepAgent templates...")

        db = SessionLocal()
        try:
            await seed_deepagent_templates(db)
            logger.info("✓ Templates seeded successfully")
        finally:
            db.close()

        return True

    except Exception as e:
        logger.error(f"✗ Failed to seed templates: {e}")
        return False


def verify_tables():
    """Verify that tables were created correctly."""
    try:
        db = SessionLocal()

        # Check if tables exist by querying them
        deep_agent_count = db.query(DeepAgentTemplate).count()
        export_count = db.query(AgentExport).count()
        session_count = db.query(ChatSession).count()

        logger.info(f"✓ Verification complete:")
        logger.info(f"  - deep_agent_templates: {deep_agent_count} records")
        logger.info(f"  - agent_exports: {export_count} records")
        logger.info(f"  - chat_sessions: {session_count} records")

        db.close()
        return True

    except Exception as e:
        logger.error(f"✗ Verification failed: {e}")
        return False


async def main():
    """Main initialization function."""
    logger.info("=" * 60)
    logger.info("DeepAgent Database Initialization")
    logger.info("=" * 60)

    # Step 1: Create tables
    if not init_deepagent_tables():
        logger.error("Failed to create tables. Exiting.")
        return False

    # Step 2: Verify tables
    if not verify_tables():
        logger.error("Failed to verify tables. Exiting.")
        return False

    # Step 3: Seed templates
    if not await seed_templates():
        logger.error("Failed to seed templates. Exiting.")
        return False

    # Step 4: Verify seeding
    db = SessionLocal()
    template_count = db.query(DeepAgentTemplate).count()
    db.close()

    logger.info("=" * 60)
    logger.info(f"✓ Initialization complete! {template_count} templates available.")
    logger.info("=" * 60)

    return True


if __name__ == "__main__":
    import asyncio
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
