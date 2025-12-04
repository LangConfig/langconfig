# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Database Migration: Add Audit Log Table


Creates audit_logs table for tracking all important operations.

Features:
- Comprehensive operation tracking (WHO, WHAT, WHEN, HOW)
- Efficient querying with composite indexes
- JSONB for flexible metadata storage
- Performance metrics (duration, status code)

Usage:
    python backend/migrations/add_audit_log_table.py

Rollback:
    python backend/migrations/add_audit_log_table.py --rollback
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
    Apply migration: Create audit_logs table.

    Table Structure:
    - id: Primary key
    - user_id: Who performed the action (optional)
    - ip_address: Client IP address
    - user_agent: Client user agent string
    - action: Type of action (CREATE, UPDATE, DELETE, etc.)
    - resource_type: Type of resource (Workflow, Agent, etc.)
    - resource_id: ID of affected resource
    - timestamp: When the action occurred
    - duration_ms: Request duration in milliseconds
    - status_code: HTTP status code
    - success: Whether operation succeeded (1=yes, 0=no)
    - request_method: HTTP method (GET, POST, etc.)
    - endpoint: API endpoint path
    - query_params: Query string parameters (JSONB)
    - changes: Before/after values (JSONB)
    - metadata: Additional context (JSONB)
    - message: Human-readable description
    """
    logger.info("=" * 80)
    logger.info("MIGRATION: Add Audit Log Table")
    logger.info("=" * 80)

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # Check if table already exists
            if table_exists(engine, "audit_logs"):
                logger.warning("Table 'audit_logs' already exists. Skipping creation.")
                trans.commit()
                return

            logger.info("Creating audit_logs table...")

            # Create audit_logs table
            conn.execute(text("""
                CREATE TABLE audit_logs (
                    id SERIAL PRIMARY KEY,

                    -- Who (Actor)
                    user_id INTEGER,
                    ip_address VARCHAR(45),
                    user_agent VARCHAR(500),

                    -- What (Action)
                    action VARCHAR(50) NOT NULL,
                    resource_type VARCHAR(100) NOT NULL,
                    resource_id INTEGER,

                    -- When (Timing)
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    duration_ms FLOAT,

                    -- How (Result)
                    status_code INTEGER,
                    success INTEGER NOT NULL DEFAULT 1,

                    -- Context (Request Details)
                    request_method VARCHAR(10),
                    endpoint VARCHAR(500),
                    query_params JSONB,

                    -- Changes (What changed)
                    changes JSONB,
                    metadata JSONB,

                    -- Message
                    message TEXT
                )
            """))

            logger.info("✓ Created audit_logs table")

            # Create indexes for efficient querying
            logger.info("Creating indexes...")

            # Basic indexes
            conn.execute(text("""
                CREATE INDEX idx_audit_user_id ON audit_logs(user_id);
            """))
            logger.info("✓ Created index on user_id")

            conn.execute(text("""
                CREATE INDEX idx_audit_action ON audit_logs(action);
            """))
            logger.info("✓ Created index on action")

            conn.execute(text("""
                CREATE INDEX idx_audit_resource_type ON audit_logs(resource_type);
            """))
            logger.info("✓ Created index on resource_type")

            conn.execute(text("""
                CREATE INDEX idx_audit_resource_id ON audit_logs(resource_id);
            """))
            logger.info("✓ Created index on resource_id")

            conn.execute(text("""
                CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);
            """))
            logger.info("✓ Created index on timestamp")

            conn.execute(text("""
                CREATE INDEX idx_audit_status_code ON audit_logs(status_code);
            """))
            logger.info("✓ Created index on status_code")

            conn.execute(text("""
                CREATE INDEX idx_audit_endpoint ON audit_logs(endpoint);
            """))
            logger.info("✓ Created index on endpoint")

            # Composite indexes for common queries
            conn.execute(text("""
                CREATE INDEX idx_audit_resource_lookup
                ON audit_logs(resource_type, resource_id, timestamp DESC);
            """))
            logger.info("✓ Created composite index for resource lookups")

            conn.execute(text("""
                CREATE INDEX idx_audit_user_activity
                ON audit_logs(user_id, timestamp DESC);
            """))
            logger.info("✓ Created composite index for user activity")

            conn.execute(text("""
                CREATE INDEX idx_audit_failed_operations
                ON audit_logs(success, timestamp DESC);
            """))
            logger.info("✓ Created composite index for failed operations")

            # Commit transaction
            trans.commit()
            logger.info("=" * 80)
            logger.info("✅ Migration completed successfully!")
            logger.info("=" * 80)

            # Summary
            logger.info("")
            logger.info("Summary:")
            logger.info("- Created audit_logs table")
            logger.info("- Created 7 single-column indexes")
            logger.info("- Created 3 composite indexes for common queries")
            logger.info("")
            logger.info("Audit logging is now enabled!")
            logger.info("All operations can be tracked for compliance and debugging.")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"❌ Migration failed: {e}")
            logger.error("Transaction rolled back")
            raise


def migrate_down(engine):
    """
    Rollback migration: Drop audit_logs table.

    WARNING: This will delete all audit log data!
    """
    logger.info("=" * 80)
    logger.info("ROLLBACK: Drop Audit Log Table")
    logger.info("=" * 80)

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            if not table_exists(engine, "audit_logs"):
                logger.warning("Table 'audit_logs' does not exist. Nothing to rollback.")
                trans.commit()
                return

            logger.info("Dropping audit_logs table...")
            conn.execute(text("DROP TABLE audit_logs CASCADE"))
            logger.info("✓ Dropped audit_logs table")

            # Commit transaction
            trans.commit()
            logger.info("=" * 80)
            logger.info("✅ Rollback completed successfully!")
            logger.info("=" * 80)

            logger.warning("⚠️  Audit logging is now DISABLED!")
            logger.warning("All audit log data has been deleted.")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"❌ Rollback failed: {e}")
            logger.error("Transaction rolled back")
            raise


def main():
    """Main migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Audit Log Table Migration")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (drop audit_logs table)"
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

            if args.rollback:
                logger.info("Would drop audit_logs table")
            else:
                logger.info("Would create audit_logs table with 10 indexes")

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
