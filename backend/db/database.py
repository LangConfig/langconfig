# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Database Setup - PostgreSQL with pgvector
Unified database for all data: workflows, projects, tasks, vector storage, and LangGraph checkpoints
"""
import os
import time
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from contextlib import asynccontextmanager
from typing import Generator, AsyncGenerator
import logging

logger = logging.getLogger(__name__)

# Environment variables for configuration
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"
LOG_SLOW_QUERIES = os.getenv("LOG_SLOW_QUERIES", "true").lower() == "true"
SLOW_QUERY_THRESHOLD = float(os.getenv("SLOW_QUERY_THRESHOLD", "1.0"))
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))

# PostgreSQL URL (unified database for everything)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://langconfig:langconfig_dev@localhost:5433/langconfig"
)

# Async PostgreSQL URL (for async operations like event persistence)
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

# Create PostgreSQL engine with connection pooling (sync)
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    echo=SQL_ECHO,
    pool_recycle=3600  # Recycle connections after 1 hour
)

# Create async PostgreSQL engine for async operations
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=SQL_ECHO,
    pool_recycle=3600
)

# =============================================================================
# Database Event Listeners
# =============================================================================

# Timezone enforcement - sync engine
@event.listens_for(engine, "connect")
def set_timezone_sync(dbapi_conn, connection_record):
    """Enforce UTC timezone for all sync connections"""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET timezone='UTC'")
    cursor.close()

# Timezone enforcement - async engine
@event.listens_for(async_engine.sync_engine, "connect")
def set_timezone_async(dbapi_conn, connection_record):
    """Enforce UTC timezone for all async connections"""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET timezone='UTC'")
    cursor.close()

# Slow query logging - before execution
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Record query start time for slow query detection"""
    conn.info.setdefault('query_start_time', []).append(time.time())

# Slow query logging - after execution
@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log slow queries that exceed threshold"""
    total = time.time() - conn.info['query_start_time'].pop()
    if LOG_SLOW_QUERIES and total > SLOW_QUERY_THRESHOLD:
        logger.warning(f"Slow query ({total:.2f}s): {statement[:200]}")

# =============================================================================
# Session Management
# =============================================================================

# Create sessionmaker (sync)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create async sessionmaker
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()

# Dependency for FastAPI routes (sync)
def get_db() -> Generator:
    """Get PostgreSQL database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Async context manager for async operations
@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async PostgreSQL database session for async operations (e.g., event persistence)"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def init_db():
    """
    Initialize PostgreSQL database (sync version).

    Creates pgvector extension and all SQLAlchemy tables.
    Use async_init_db() for async contexts (FastAPI lifespan).
    """
    try:
        # Enable PostgreSQL extensions
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            logger.info("✓ PostgreSQL extensions enabled")

        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✓ PostgreSQL database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}")
        raise

async def async_init_db():
    """
    Initialize PostgreSQL database (async version).

    Creates pgvector extension and all SQLAlchemy tables asynchronously.
    Use this from FastAPI lifespan or other async contexts.
    """
    try:
        # Enable PostgreSQL extensions
        async with async_engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            logger.info("✓ PostgreSQL extensions enabled (async)")

        # Create all tables
        async with async_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        logger.info("✓ PostgreSQL database initialized successfully (async)")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL (async): {e}")
        raise

async def check_db_health() -> dict:
    """
    Check database health status.

    Returns:
        dict: Health status including connection pool metrics
    """
    try:
        # Test database connectivity
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()

        # Get connection pool status
        pool_status = {
            "pool_size": async_engine.pool.size(),
            "checked_in": async_engine.pool.checkedin(),
            "checked_out": async_engine.pool.checkedout(),
            "overflow": async_engine.pool.overflow()
        }

        return {
            "status": "healthy",
            "database": "postgresql",
            "extensions": ["pgvector", "uuid-ossp"],
            "pool": pool_status
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "postgresql",
            "error": str(e)
        }

async def dispose_engines():
    """
    Dispose database engines on shutdown.

    Gracefully closes all database connections.
    Call this during application shutdown.
    """
    try:
        await async_engine.dispose()
        engine.dispose()
        logger.info("✓ Database connections closed gracefully")
    except Exception as e:
        logger.error(f"Error disposing database engines: {e}")
        raise

def get_connection_string() -> str:
    """Get PostgreSQL connection string for LangGraph and LlamaIndex"""
    return DATABASE_URL
