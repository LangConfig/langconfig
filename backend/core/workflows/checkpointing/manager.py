# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
PostgreSQL checkpointing configuration for LangGraph orchestration.

This module sets up persistent storage for LangGraph workflow states,
enabling durability, recovery, and Human-in-the-Loop capabilities.

Updated: October 2025 for LangGraph v1.0 (langgraph-checkpoint-postgres 3.0.0)
Pattern: AsyncConnectionPool passed directly to AsyncPostgresSaver
"""

import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

# Try to import PostgresSaver, Store, and connection pool, but make it optional
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver as PostgresSaver
    from langgraph.store.postgres import AsyncPostgresStore
    from psycopg_pool import AsyncConnectionPool
    from psycopg.rows import dict_row
    CHECKPOINTING_AVAILABLE = True
    STORE_AVAILABLE = True
except ImportError as e:
    PostgresSaver = None
    AsyncPostgresStore = None
    AsyncConnectionPool = None
    dict_row = None
    CHECKPOINTING_AVAILABLE = False
    STORE_AVAILABLE = False
    _import_error = str(e)

from sqlalchemy import text

from db.database import engine
from config import settings
import os
import sys

logger = logging.getLogger(__name__)

if not CHECKPOINTING_AVAILABLE:
    logger.warning("⚠ PostgreSQL checkpointing not available - langgraph-checkpoint-postgres not installed")
    logger.warning(f"  Import error: {_import_error}")
    logger.warning("  Install with: pip install langgraph-checkpoint-postgres psycopg-pool")

# Global connection pool and checkpointer instances
# Per LangGraph docs: "Neither the graph nor the checkpointer keep any internal state
# so using one global instance or a new one per request makes no difference"
_connection_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[PostgresSaver] = None
_store: Optional[AsyncPostgresStore] = None


async def initialize_checkpointer() -> PostgresSaver:
    """
    Initialize the PostgreSQL checkpointer for LangGraph persistence using connection pool.

    This creates a global AsyncConnectionPool and initializes the checkpointer.
    Per LangGraph v1.0 docs (langgraph-checkpoint-postgres 3.0.0):
    - Connection pool can be passed directly to AsyncPostgresSaver
    - Neither graph nor checkpointer keep internal state (safe to use global instance)
    - Must set autocommit=True and row_factory=dict_row

    Returns:
        Initialized PostgresSaver instance

    Raises:
        ValueError: If ASYNC_DB_URL is not set or checkpointing not available
        Exception: If initialization fails
    """
    global _connection_pool, _checkpointer

    if not CHECKPOINTING_AVAILABLE:
        raise ValueError(
            "Checkpointing dependencies not installed. "
            "Install with: pip install langgraph-checkpoint-postgres psycopg-pool"
        )

    if _checkpointer is not None:
        # Already initialized
        logger.info("✓ Checkpointer already initialized (reusing global instance)")
        return _checkpointer

    # Get database URL from environment or settings
    async_db_url = os.getenv("ASYNC_DB_URL") or settings.database_url

    if not async_db_url:
        raise ValueError(
            "Database URL not configured. Set ASYNC_DB_URL environment variable "
            "or ensure settings.database_url is set."
        )

    # Convert asyncpg URL to standard PostgreSQL format for psycopg
    # psycopg expects: postgresql://user:pass@host:port/db
    connection_string = async_db_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        logger.info("Initializing LangGraph PostgreSQL Checkpointer with connection pool...")

        # Windows-specific: Ensure we're using SelectorEventLoop for psycopg compatibility
        if sys.platform == 'win32':
            loop = asyncio.get_event_loop()
            if loop.__class__.__name__ == 'ProactorEventLoop':
                logger.warning("Windows detected: ProactorEventLoop not compatible with psycopg")
                logger.warning("psycopg requires SelectorEventLoop on Windows")
                logger.info("Note: FastAPI/uvicorn should handle this automatically")

        # Create AsyncConnectionPool with required configuration
        # autocommit=True is required for .setup() to properly commit checkpoint tables
        _connection_pool = AsyncConnectionPool(
            conninfo=connection_string,
            max_size=20,  # Adjust based on your needs
            kwargs={
                "autocommit": True,
                "row_factory": dict_row
            },
            open=False  # Don't open in constructor (deprecated)
        )

        # Open the connection pool
        await _connection_pool.open()
        logger.info("✓ Connection pool created and opened")

        # Create checkpointer with the connection pool
        _checkpointer = PostgresSaver(_connection_pool)

        # Setup checkpoint tables (idempotent - safe to always call)
        logger.info("Creating/verifying checkpoint tables (with migrations)...")
        await _checkpointer.setup()
        logger.info("✓ Checkpoint tables created/verified successfully")

        # Success!
        logger.info("✓ LangGraph PostgreSQL Checkpointer initialized successfully")
        logger.info("  - Checkpoint persistence: ENABLED")
        logger.info("  - Connection pool: ACTIVE (max_size=20)")
        logger.info("  - Checkpoint tables: READY")
        logger.info("  - Pattern: Global checkpointer instance (stateless)")

        return _checkpointer

    except Exception as e:
        logger.error(f"CRITICAL: Failed to initialize LangGraph Checkpointer: {e}")
        logger.error("  - Checkpoint persistence will NOT be available")
        logger.error("  - Workflows cannot be recovered after restart")
        logger.error("  - HITL workflows will NOT function")
        # The application should fail to start if persistence is not available
        raise


async def initialize_store() -> AsyncPostgresStore:
    """
    Initialize the PostgreSQL Store for LangGraph long-term memory.

    This creates a global AsyncPostgresStore using the same connection pool
    as the checkpointer. The Store enables workflow-scoped long-term memory
    that persists across sessions.

    Returns:
        Initialized AsyncPostgresStore instance

    Raises:
        ValueError: If ASYNC_DB_URL is not set or Store not available
        Exception: If initialization fails
    """
    global _connection_pool, _store

    if not STORE_AVAILABLE:
        raise ValueError(
            "Store dependencies not installed. "
            "Install with: pip install langgraph-checkpoint-postgres psycopg-pool"
        )

    if _store is not None:
        # Already initialized
        logger.info("✓ Store already initialized (reusing global instance)")
        return _store

    # Ensure connection pool is available
    if _connection_pool is None:
        raise ValueError(
            "Connection pool not initialized. "
            "Call initialize_checkpointer() before initialize_store()"
        )

    try:
        logger.info("Initializing LangGraph PostgreSQL Store for long-term memory...")

        # Create Store with the connection pool
        _store = AsyncPostgresStore(conn=_connection_pool)

        # Setup store tables (idempotent - safe to always call)
        logger.info("Creating/verifying store tables...")
        await _store.setup()
        logger.info("✓ Store tables created/verified successfully")

        # Success!
        logger.info("✓ LangGraph PostgreSQL Store initialized successfully")
        logger.info("  - Long-term memory: ENABLED")
        logger.info("  - Workflow-scoped memory: READY")
        logger.info("  - Pattern: Global store instance (stateless)")

        return _store

    except Exception as e:
        logger.error(f"CRITICAL: Failed to initialize LangGraph Store: {e}")
        logger.error("  - Long-term memory will NOT be available")
        logger.error("  - Workflows will run without persistent memory")
        raise


async def verify_checkpoint_tables():
    """
    Verify that checkpoint tables exist and are accessible.

    This is an optional verification function. The actual table creation
    is handled by PostgresSaver.setup() during initialization.

    Note: Uses psycopg connection pool directly to avoid sync/async engine issues.
    """
    global _connection_pool

    if _connection_pool is None:
        logger.debug("Connection pool not available for verification")
        return

    try:
        # Use the psycopg connection pool directly (already async)
        async with _connection_pool.connection() as conn:
            # Check if checkpoints table exists using psycopg3 async API
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'checkpoints'
                    )
                """)

                row = await cur.fetchone()
                table_exists = row[0] if row else False

                if table_exists:
                    logger.info("✓ Checkpoint tables verified in database")

                    # Get table statistics
                    await cur.execute("SELECT COUNT(*) FROM checkpoints")
                    count_row = await cur.fetchone()
                    count = count_row[0] if count_row else 0
                    logger.info(f"  - Existing checkpoints: {count}")
                else:
                    logger.info("ℹ Checkpoint tables will be created automatically on first workflow execution")

    except Exception as e:
        logger.warning(f"Could not verify checkpoint tables: {e}")
        # Don't fail - tables will be created by setup()


def get_checkpointer() -> Optional[PostgresSaver]:
    """
    Get the global checkpointer instance for workflow persistence.

    Per LangGraph v1.0 docs: "Neither the graph nor the checkpointer keep any
    internal state so using one global instance or a new one per request makes
    no difference."

    Returns:
        PostgresSaver instance or None if not initialized

    Usage:
        checkpointer = get_checkpointer()
        workflow = graph.compile(checkpointer=checkpointer)
        result = await workflow.ainvoke(state, config)
    """
    if not CHECKPOINTING_AVAILABLE:
        logger.debug("Checkpointing not available")
        return None

    if _checkpointer is None:
        logger.warning("Checkpointer requested but not initialized - workflows will run without persistence")
        logger.warning("Call await initialize_checkpointer() during application startup")
        return None

    return _checkpointer


def get_store() -> Optional[AsyncPostgresStore]:
    """
    Get the global Store instance for workflow long-term memory.

    Per LangGraph v1.0 docs: Store is stateless and can be shared globally.
    The Store enables persistent memory across workflow sessions using
    workflow-scoped namespaces.

    Returns:
        AsyncPostgresStore instance or None if not initialized

    Usage:
        store = get_store()
        config = {
            "configurable": {
                "thread_id": thread_id,
                "store": store
            }
        }
        result = await workflow.ainvoke(state, config)
    """
    if not STORE_AVAILABLE:
        logger.debug("Store not available")
        return None

    if _store is None:
        logger.debug("Store requested but not initialized - long-term memory disabled")
        logger.debug("Call await initialize_store() during application startup")
        return None

    return _store


# Utility functions for workflow state management
async def save_workflow_checkpoint(
    thread_id: str,
    state: dict,
    metadata: Optional[dict] = None
):
    """
    Save a workflow checkpoint to PostgreSQL.
    
    Args:
        thread_id: Unique identifier for the workflow thread
        state: The workflow state to checkpoint
        metadata: Optional metadata about the checkpoint
    """
    checkpointer = get_checkpointer()
    
    # The actual checkpointing is handled by LangGraph during workflow execution
    # This is a utility for manual checkpointing if needed
    logger.debug(f"Saving checkpoint for thread {thread_id}")


async def load_workflow_checkpoint(thread_id: str) -> Optional[dict]:
    """
    Load a workflow checkpoint from PostgreSQL.
    
    Args:
        thread_id: Unique identifier for the workflow thread
        
    Returns:
        The loaded workflow state, or None if not found
    """
    checkpointer = get_checkpointer()
    
    # The actual checkpoint loading is handled by LangGraph during workflow execution
    # This is a utility for manual checkpoint loading if needed
    logger.debug(f"Loading checkpoint for thread {thread_id}")
    return None


async def cleanup_old_checkpoints(days_old: int = 30):
    """
    Clean up old checkpoints to prevent database bloat.
    
    Args:
        days_old: Remove checkpoints older than this many days
    """
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                DELETE FROM checkpoints 
                WHERE created_at < NOW() - INTERVAL '%s days'
                RETURNING checkpoint_id;
            """), (days_old,))
            
            deleted_count = len(result.fetchall())
            logger.info(f"Cleaned up {deleted_count} old checkpoints")
            
    except Exception as e:
        logger.error(f"Failed to cleanup old checkpoints: {e}")


async def cleanup_checkpointing():
    """
    Cleanup checkpointing and store resources during application shutdown.

    This function should be called in the FastAPI lifespan context manager
    shutdown phase to properly close the connection pool.
    """
    global _connection_pool, _checkpointer, _store

    if _connection_pool is not None:
        try:
            logger.info("Closing LangGraph checkpointer and store connection pool...")
            await _connection_pool.close()
            logger.info("✓ Connection pool closed successfully")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
        finally:
            _connection_pool = None
            _checkpointer = None
            _store = None


# Startup function to be called during FastAPI initialization
async def setup_checkpointing():
    """
    Initialize checkpointing and store during application startup.

    This function should be called in the FastAPI lifespan context manager
    startup phase. It initializes the AsyncConnectionPool, creates the
    checkpointer, and initializes the Store for long-term memory.

    Raises:
        Exception: If checkpointing initialization fails
    """
    try:
        # Initialize the checkpointer with connection pool
        await initialize_checkpointer()

        # Initialize the Store for long-term memory (uses same connection pool)
        try:
            await initialize_store()
            logger.info("✓ Long-term memory (Store) initialized")
        except Exception as e:
            logger.warning(f"Store initialization failed: {e}")
            logger.warning("Long-term memory will NOT be available")
            # Don't fail startup - workflows can run without Store

        # Skip optional verification - tables are already verified by LangGraph's setup()
        # await verify_checkpoint_tables()

        logger.info("✓ LangGraph checkpointing setup completed")
        logger.info("  System ready for workflow persistence and HITL")

    except Exception as e:
        logger.error(f"CRITICAL: Failed to setup checkpointing: {e}")
        logger.error("Application startup FAILED - checkpointing is required")
        raise
