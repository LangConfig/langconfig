# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangConfig - FastAPI Backend
Main application entry point
"""
import sys
import asyncio
import selectors

# Fix for Windows: psycopg requires SelectorEventLoop, not ProactorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import warnings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Suppress Pydantic warnings from dependencies
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")
warnings.filterwarnings("ignore", message=".*validate_default.*")

# Import settings for environment configuration
from config import settings

# Configure logging based on environment
log_level = logging.DEBUG if settings.debug else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"Starting in {settings.environment} mode (debug={settings.debug})")

# Import database setup
from db.database import async_init_db, dispose_engines
import models  # Import models to register them with Base

# Import MCP Manager singleton from services (canonical location)
from services.mcp_manager import get_mcp_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("Starting LangConfig API...")

    # Initialize PostgreSQL database (unified database for everything)
    try:
        await async_init_db()
        logger.info("PostgreSQL database initialized successfully")
    except Exception as e:
        logger.error(f"PostgreSQL initialization failed: {e}")
        logger.error("Make sure PostgreSQL is running: docker-compose up -d postgres")
        raise

    # Initialize LangGraph checkpointing for workflow persistence and HITL
    try:
        from core.workflows.checkpointing.manager import setup_checkpointing
        await setup_checkpointing()
        logger.info("LangGraph checkpointing initialized successfully")
    except Exception as e:
        logger.error(f"LangGraph checkpointing initialization failed: {e}")
        logger.error("Workflow persistence and HITL features will NOT be available")
        logger.error("Workflows will still execute but state will not be saved")
        # Don't fail startup - workflows can still run without checkpointing

    # Initialize MCP Manager
    try:
        await get_mcp_manager()
        logger.info("MCP Manager initialized successfully")
    except Exception as e:
        logger.warning(f"MCP Manager initialization failed: {e}. MCP tools may not be available.")

    # Start chat session manager for automatic cleanup
    try:
        from services.chat_session_manager import start_session_manager
        await start_session_manager()
        logger.info("Chat session manager started successfully")
    except Exception as e:
        logger.warning(f"Chat session manager failed to start: {e}. Abandoned sessions won't be cleaned up automatically.")

    # Start background task queue workers
    try:
        # Import task handlers to register them
        import core.task_handlers  # noqa - registers handlers via decorators

        from core.task_queue import task_queue
        task_queue.start_workers(num_workers=2)
        logger.info("Background task queue workers started (2 workers)")
    except Exception as e:
        logger.error(f"Failed to start background workers: {e}")
        logger.error("Long-running operations will not work properly")
        # Don't fail startup - app can still run without background workers

    # Start workflow scheduler service
    try:
        from services.scheduler_service import start_scheduler
        await start_scheduler()
        logger.info("Workflow scheduler service started")
    except Exception as e:
        logger.warning(f"Workflow scheduler failed to start: {e}. Scheduled workflows will not run automatically.")

    # Start file watcher service for file-based triggers
    try:
        from services.triggers.file_watcher import start_file_watchers
        await start_file_watchers()
        logger.info("File watcher service started")
    except ImportError:
        logger.info("File watcher service not started (watchdog package not installed - optional)")
    except Exception as e:
        logger.warning(f"File watcher service failed to start: {e}. File triggers will not work.")

    logger.info("LangConfig API startup complete")

    yield  # Server is running

    # Shutdown
    logger.info("Shutting down LangConfig API...")

    # Shutdown file watcher service
    try:
        from services.triggers.file_watcher import stop_file_watchers
        await stop_file_watchers()
        logger.info("File watcher service stopped")
    except Exception as e:
        logger.error(f"Error stopping file watcher service: {e}")

    # Shutdown workflow scheduler service (before task queue)
    try:
        from services.scheduler_service import stop_scheduler
        await stop_scheduler()
        logger.info("Workflow scheduler service stopped")
    except Exception as e:
        logger.error(f"Error stopping workflow scheduler: {e}")

    # Shutdown background task queue workers
    try:
        from core.task_queue import task_queue
        await task_queue.shutdown(timeout=30)
        logger.info("Background task queue workers stopped")
    except Exception as e:
        logger.error(f"Error stopping background workers: {e}")

    # Shutdown chat session manager
    try:
        from services.chat_session_manager import stop_session_manager
        await stop_session_manager()
        logger.info("Chat session manager stopped")
    except Exception as e:
        logger.error(f"Error stopping chat session manager: {e}")

    # Shutdown LangGraph checkpointing
    try:
        from core.workflows.checkpointing.manager import cleanup_checkpointing
        await cleanup_checkpointing()
        logger.info("LangGraph checkpointing cleanup completed")
    except Exception as e:
        logger.error(f"Error during checkpointing cleanup: {e}")

    # Shutdown MCP Manager
    try:
        # Get the manager instance if it was initialized
        from services.mcp_manager import _mcp_manager
        if _mcp_manager:
            await _mcp_manager.stop()
            logger.info("MCP Manager stopped")
    except Exception as e:
        logger.error(f"Error stopping MCP Manager: {e}")

    # Dispose database engines
    try:
        await dispose_engines()
    except Exception as e:
        logger.error(f"Error disposing database engines: {e}")

    logger.info("Shutdown complete")

# Create FastAPI app with lifespan
app = FastAPI(
    title="LangConfig API",
    description="""
    # LangConfig - Local-First AI Workflow Builder

    Build, test, and deploy AI workflows locally with:
    - **Visual Workflow Canvas** - Drag-and-drop workflow design
    - **DeepAgents Framework** - Advanced agentic AI with middleware and subagents
    - **Background Jobs** - Non-blocking operations with PostgreSQL-backed queue
    - **Optimistic Locking** - Concurrent edit detection and prevention
    - **Audit Logging** - Complete operation tracking for compliance
    - **Performance Monitoring** - Request timing and slow query detection
    - **Rate Limiting** - API abuse protection

    ## Features
    - Fast and lightweight (no external dependencies except PostgreSQL)
    - Secure by default (SSRF protection, validation, error handling)
    - Production-ready (monitoring, logging, health checks)
    - Self-hosted (all data stays on your server)
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    openapi_url="/openapi.json",
    contact={
        "name": "LangConfig",
        "url": "https://github.com/yourusername/langconfig"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Register standardized error handlers
from core.error_handlers import register_error_handlers
register_error_handlers(app)
logger.info("Standardized error handlers registered")

# Register performance monitoring and rate limiting
from middleware.performance import PerformanceMiddleware
from middleware.rate_limit import RateLimitMiddleware

app.add_middleware(PerformanceMiddleware)
app.add_middleware(RateLimitMiddleware)
logger.info("Performance monitoring and rate limiting enabled")

# CORS middleware (allow Tauri frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "http://tauri.localhost",
        "http://localhost:1420",  # Tauri default port
        "http://127.0.0.1:1420",  # localhost IP equivalent
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",  # Vite dev server IP equivalent
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "app": "LangConfig",
        "version": "0.1.0",
        "description": "Local-first AI Workflow Builder + RAG Database"
    }

# Import and register API routers (domain-based organization)
from api.workflows import routes as workflows
from api.projects import routes as projects
from api.tasks import routes as tasks
from api.knowledge import rag, store
from api.system import settings, health, debug, background_tasks
from api.models import local as local_models
from api.workflows import execution as orchestration, checkpoints
from api.agents import deep_agents as deepagents, routes as agents, generator as agent_generator
from api.chat import routes as chat
from api.hitl import routes as hitl
from api.tools import routes as custom_tools
from api.images import routes as images
from api.memory import routes as memory
from api.workspace import routes as workspace
from api.presets import actions as action_presets
from api.skills import routes as skills
from api import schemas
from api.auth import google_router as google_auth
from api.presentations import router as presentations
from api.schedules import router as schedules
from api.triggers import router as triggers
from api.webhooks import router as webhooks

# Health check endpoints
app.include_router(health.router)

app.include_router(workflows.router)
app.include_router(orchestration.router)  # ✓ Simplified orchestration enabled
app.include_router(hitl.router)  # Human-in-the-loop approval endpoints
app.include_router(checkpoints.router)  # Checkpoint management endpoints
app.include_router(store.router)  # Store (long-term memory) management endpoints
app.include_router(memory.router)  # Agent memory management and viewing
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(rag.router)
app.include_router(background_tasks.router)  # Background task queue management
app.include_router(workspace.router)  # Workspace file management
app.include_router(settings.router)
app.include_router(local_models.router, prefix="/api/local-models", tags=["local-models"])  # Local model configurations
app.include_router(agents.router)  # Agent templates (preset agents)
app.include_router(action_presets.router)  # Action presets library with enhanced metadata
app.include_router(custom_tools.router)  # Custom user-defined tools
app.include_router(skills.router)  # Skills system - modular, context-aware capabilities
app.include_router(images.router)  # Image storage and serving (for AI-generated images)
app.include_router(deepagents.router)  # DeepAgents configuration and export
app.include_router(chat.router)  # DeepAgents chat testing
app.include_router(agent_generator.router)  # AI-powered agent generation
app.include_router(debug.router)  # Debug endpoints for development

app.include_router(schemas.router)  # Structured output schemas
app.include_router(google_auth)  # Google OAuth for presentations
app.include_router(presentations)  # Presentation generation
app.include_router(schedules)  # Workflow cron scheduling
app.include_router(triggers)  # Workflow event triggers (file watch, etc.)
app.include_router(webhooks)  # Webhook receiver endpoints

if __name__ == "__main__":
    import sys

    # Windows-specific: Use SelectorEventLoop for psycopg compatibility
    # psycopg (used by LangGraph checkpointing) requires SelectorEventLoop on Windows
    if sys.platform == 'win32':
        import asyncio
        import selectors
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        logger.info("Windows detected: Using SelectorEventLoop for psycopg compatibility")

    uvicorn.run(
        "main:app",
        host="localhost",
        port=8765,
        reload=True
    )
