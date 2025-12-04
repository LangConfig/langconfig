# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Health Check and Diagnostics API

Provides comprehensive health checks and system diagnostics.

Endpoints:
- GET /health - Basic health check (fast, for load balancers)
- GET /health/detailed - Detailed system diagnostics
- GET /health/metrics - Performance metrics

Usage:
    # Basic health check
    curl http://localhost:8000/health

    # Detailed diagnostics
    curl http://localhost:8000/health/detailed

    # Performance metrics
    curl http://localhost:8000/health/metrics
"""

import logging
import os
import sys
import time
import psutil
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any, Optional
from pydantic import BaseModel

from db.database import get_db, check_db_health
from middleware.performance import performance_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


# =============================================================================
# Response Models
# =============================================================================

class HealthStatus(BaseModel):
    """Basic health status."""
    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    timestamp: float


class DetailedHealthStatus(BaseModel):
    """Detailed health status with diagnostics."""
    status: str
    message: str
    timestamp: float
    components: Dict[str, Dict[str, Any]]
    system: Dict[str, Any]


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics."""
    total_requests: int
    avg_duration_ms: float
    slow_requests: int
    errors: int
    error_rate: float
    by_endpoint: Dict[str, Dict[str, Any]]
    by_status_code: Dict[int, int]


# =============================================================================
# Health Check Endpoints
# =============================================================================

@router.get("/", response_model=HealthStatus)
async def health_check():
    """
    Basic health check endpoint.

    Fast and lightweight - suitable for load balancer health checks.

    Returns:
        HealthStatus: Current health status

    Example:
        {
            "status": "healthy",
            "message": "LangConfig API is running",
            "timestamp": 1701234567.89
        }
    """
    return HealthStatus(
        status="healthy",
        message="LangConfig API is running",
        timestamp=time.time()
    )


@router.get("/detailed", response_model=DetailedHealthStatus)
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check with system diagnostics.

    Checks:
    - Database connectivity
    - Background workers status
    - System resources (CPU, memory, disk)
    - Component health

    Returns:
        DetailedHealthStatus: Comprehensive health status

    Example:
        {
            "status": "healthy",
            "message": "All systems operational",
            "timestamp": 1701234567.89,
            "components": {
                "database": {"status": "healthy", "response_time_ms": 5.2},
                "background_workers": {"status": "healthy", "active_workers": 2}
            },
            "system": {
                "cpu_percent": 25.3,
                "memory_percent": 45.2,
                "disk_percent": 60.1
            }
        }
    """
    components = {}
    overall_status = "healthy"

    # Check database
    db_health = await _check_database(db)
    components["database"] = db_health
    if db_health["status"] != "healthy":
        overall_status = "degraded"

    # Check background workers
    worker_health = _check_background_workers()
    components["background_workers"] = worker_health
    if worker_health["status"] != "healthy":
        overall_status = "degraded"

    # Check MCP manager
    mcp_health = _check_mcp_manager()
    components["mcp_manager"] = mcp_health
    # MCP is optional, don't degrade health if it's not running

    # Check LangGraph checkpointing
    checkpoint_health = _check_langgraph_checkpointing(db)
    components["langgraph_checkpointing"] = checkpoint_health
    # Checkpointing is optional

    # Get system resources
    system_resources = _get_system_resources()

    # Determine message
    if overall_status == "healthy":
        message = "All systems operational"
    else:
        message = "Some components are degraded"

    return DetailedHealthStatus(
        status=overall_status,
        message=message,
        timestamp=time.time(),
        components=components,
        system=system_resources
    )


@router.get("/metrics", response_model=PerformanceMetricsResponse)
async def get_performance_metrics():
    """
    Get performance metrics from monitoring middleware.

    Returns:
        PerformanceMetricsResponse: Current performance metrics

    Example:
        {
            "total_requests": 1543,
            "avg_duration_ms": 125.3,
            "slow_requests": 12,
            "errors": 8,
            "error_rate": 0.0052,
            "by_endpoint": {
                "/api/workflows": {"count": 523, "avg_duration_ms": 98.2}
            },
            "by_status_code": {
                "200": 1450,
                "404": 85,
                "500": 8
            }
        }
    """
    metrics = performance_metrics.get_metrics()
    return PerformanceMetricsResponse(**metrics)


# =============================================================================
# Health Check Helpers
# =============================================================================

async def _check_database(db: Session) -> Dict[str, Any]:
    """
    Check database connectivity and response time.

    Args:
        db: Database session

    Returns:
        dict: Database health status with pool metrics
    """
    try:
        start_time = time.time()

        # Execute simple query
        result = db.execute(text("SELECT 1"))
        result.fetchone()

        response_time_ms = (time.time() - start_time) * 1000

        # Get comprehensive health status including pool metrics
        health_status = await check_db_health()

        # Combine response time with health check results
        return {
            "status": health_status.get("status", "healthy"),
            "response_time_ms": round(response_time_ms, 2),
            "message": "Database connection OK",
            "extensions": health_status.get("extensions", []),
            "pool": health_status.get("pool", {})
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Database connection failed"
        }


def _check_background_workers() -> Dict[str, Any]:
    """
    Check background worker status.

    Returns:
        dict: Worker health status
    """
    try:
        from core.task_queue import task_queue

        if not task_queue._workers:
            return {
                "status": "unhealthy",
                "active_workers": 0,
                "message": "No background workers running"
            }

        # Count running workers
        active_workers = sum(1 for worker in task_queue._workers if not worker.done())

        return {
            "status": "healthy",
            "active_workers": active_workers,
            "total_workers": len(task_queue._workers),
            "message": "Background workers operational"
        }
    except Exception as e:
        logger.error(f"Worker health check failed: {e}", exc_info=True)
        return {
            "status": "unknown",
            "error": str(e),
            "message": "Could not check worker status"
        }


def _check_mcp_manager() -> Dict[str, Any]:
    """
    Check MCP manager status.

    Returns:
        dict: MCP manager health status
    """
    try:
        from services.mcp_manager import _mcp_manager

        if _mcp_manager is None:
            return {
                "status": "not_initialized",
                "message": "MCP manager not initialized (optional)"
            }

        # Check if manager is running
        active_servers = len(_mcp_manager.mcp_servers)

        return {
            "status": "healthy",
            "active_servers": active_servers,
            "message": "MCP manager operational"
        }
    except Exception as e:
        logger.error(f"MCP health check failed: {e}", exc_info=True)
        return {
            "status": "unknown",
            "error": str(e),
            "message": "Could not check MCP manager status"
        }


def _check_langgraph_checkpointing(db: Session) -> Dict[str, Any]:
    """
    Check LangGraph checkpointing status.

    Args:
        db: Database session

    Returns:
        dict: Checkpointing health status
    """
    try:
        # Check if checkpoints table exists
        result = db.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'checkpoints'
        """))
        table_exists = result.scalar() > 0

        if not table_exists:
            return {
                "status": "not_initialized",
                "message": "Checkpointing table not found (optional feature)"
            }

        # Count checkpoints
        result = db.execute(text("SELECT COUNT(*) FROM checkpoints"))
        checkpoint_count = result.scalar()

        return {
            "status": "healthy",
            "checkpoint_count": checkpoint_count,
            "message": "LangGraph checkpointing operational"
        }
    except Exception as e:
        logger.error(f"Checkpointing health check failed: {e}", exc_info=True)
        return {
            "status": "unknown",
            "error": str(e),
            "message": "Could not check checkpointing status"
        }


def _get_system_resources() -> Dict[str, Any]:
    """
    Get system resource usage.

    Returns:
        dict: System resource metrics
    """
    try:
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=0.1), 2),
            "memory_percent": round(psutil.virtual_memory().percent, 2),
            "disk_percent": round(psutil.disk_usage("/").percent, 2),
            "python_version": sys.version.split()[0],
            "process_uptime_seconds": round(time.time() - psutil.Process().create_time(), 2)
        }
    except Exception as e:
        logger.error(f"System resource check failed: {e}", exc_info=True)
        return {
            "error": str(e)
        }


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "router"
]
