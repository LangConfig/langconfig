# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Performance Monitoring Middleware


Tracks request duration, logs slow requests, and provides performance insights.

Features:
- Automatic request timing
- Slow request detection and logging
- Response status code tracking
- Optional metrics collection
- Integration with audit logging

Usage:
    from fastapi import FastAPI
    from middleware.performance import PerformanceMiddleware

    app = FastAPI()
    app.add_middleware(PerformanceMiddleware)
"""

import logging
import time
import os
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Configuration
PERFORMANCE_MONITORING_ENABLED = os.getenv("PERFORMANCE_MONITORING_ENABLED", "true").lower() == "true"
SLOW_REQUEST_THRESHOLD_MS = float(os.getenv("SLOW_REQUEST_THRESHOLD_MS", "1000"))  # 1 second default
LOG_ALL_REQUESTS = os.getenv("LOG_ALL_REQUESTS", "false").lower() == "true"


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware for monitoring request performance.

    Measures request duration, logs slow requests, and tracks response codes.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info(f"Performance monitoring enabled (slow request threshold: {SLOW_REQUEST_THRESHOLD_MS}ms)")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and measure performance.

        Args:
            request: FastAPI request
            call_next: Next middleware in chain

        Returns:
            Response: FastAPI response with performance headers
        """
        # Skip if disabled
        if not PERFORMANCE_MONITORING_ENABLED:
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error and re-raise
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path} ({duration_ms:.2f}ms)",
                exc_info=True,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(e)
                }
            )
            raise

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Add performance header to response
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Log request
        self._log_request(request, response, duration_ms)

        return response

    def _log_request(self, request: Request, response: Response, duration_ms: float):
        """
        Log request with performance metrics.

        Args:
            request: FastAPI request
            response: FastAPI response
            duration_ms: Request duration in milliseconds
        """
        # Determine if request is slow
        is_slow = duration_ms >= SLOW_REQUEST_THRESHOLD_MS

        # Build log message
        method = request.method
        path = request.url.path
        status_code = response.status_code

        # Log level based on status code and duration
        if status_code >= 500:
            log_level = logging.ERROR
        elif status_code >= 400:
            log_level = logging.WARNING
        elif is_slow:
            log_level = logging.WARNING
        elif LOG_ALL_REQUESTS:
            log_level = logging.INFO
        else:
            log_level = logging.DEBUG

        # Log message
        message = f"{method} {path} → {status_code} ({duration_ms:.2f}ms)"
        if is_slow:
            message += " [SLOW REQUEST]"

        # Log with context
        logger.log(
            log_level,
            message,
            extra={
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "is_slow": is_slow,
                "query_params": dict(request.query_params) if request.query_params else None
            }
        )


# =============================================================================
# Performance Metrics Collector (Optional)
# =============================================================================

class PerformanceMetrics:
    """
    Collects and aggregates performance metrics.

    Tracks:
    - Request counts by endpoint and status code
    - Average/min/max response times
    - Slow request counts
    - Error rates
    """

    def __init__(self):
        self.metrics = {
            "total_requests": 0,
            "total_duration_ms": 0,
            "slow_requests": 0,
            "errors": 0,
            "by_endpoint": {},  # {endpoint: {count, total_duration, errors}}
            "by_status_code": {}  # {status_code: count}
        }

    def record_request(
        self,
        endpoint: str,
        status_code: int,
        duration_ms: float,
        is_slow: bool = False
    ):
        """Record a request in the metrics."""
        # Update totals
        self.metrics["total_requests"] += 1
        self.metrics["total_duration_ms"] += duration_ms

        if is_slow:
            self.metrics["slow_requests"] += 1

        if status_code >= 400:
            self.metrics["errors"] += 1

        # Update by endpoint
        if endpoint not in self.metrics["by_endpoint"]:
            self.metrics["by_endpoint"][endpoint] = {
                "count": 0,
                "total_duration_ms": 0,
                "errors": 0,
                "slow_requests": 0
            }

        endpoint_metrics = self.metrics["by_endpoint"][endpoint]
        endpoint_metrics["count"] += 1
        endpoint_metrics["total_duration_ms"] += duration_ms

        if status_code >= 400:
            endpoint_metrics["errors"] += 1

        if is_slow:
            endpoint_metrics["slow_requests"] += 1

        # Update by status code
        if status_code not in self.metrics["by_status_code"]:
            self.metrics["by_status_code"][status_code] = 0

        self.metrics["by_status_code"][status_code] += 1

    def get_metrics(self) -> dict:
        """Get current metrics."""
        metrics = self.metrics.copy()

        # Calculate averages
        if metrics["total_requests"] > 0:
            metrics["avg_duration_ms"] = (
                metrics["total_duration_ms"] / metrics["total_requests"]
            )
            metrics["error_rate"] = (
                metrics["errors"] / metrics["total_requests"]
            )
        else:
            metrics["avg_duration_ms"] = 0
            metrics["error_rate"] = 0

        # Calculate per-endpoint averages
        for endpoint, data in metrics["by_endpoint"].items():
            if data["count"] > 0:
                data["avg_duration_ms"] = data["total_duration_ms"] / data["count"]
                data["error_rate"] = data["errors"] / data["count"]

        return metrics

    def reset(self):
        """Reset all metrics."""
        self.__init__()


# Global metrics instance
performance_metrics = PerformanceMetrics()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "PerformanceMiddleware",
    "PerformanceMetrics",
    "performance_metrics"
]
