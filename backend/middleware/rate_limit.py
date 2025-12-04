# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Rate Limiting Middleware


Prevents API abuse by limiting requests per IP address.

Features:
- Configurable rate limits (requests per minute)
- Per-IP tracking using in-memory cache
- Automatic cleanup of old entries
- Bypass for health check endpoints
- Clear error messages when rate limited

Usage:
    from fastapi import FastAPI
    from middleware.rate_limit import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

Configuration (.env):
    RATE_LIMIT_ENABLED=true
    RATE_LIMIT_REQUESTS_PER_MINUTE=60
    RATE_LIMIT_CLEANUP_INTERVAL=300  # 5 minutes
"""

import logging
import time
import os
from typing import Callable
from collections import defaultdict
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
RATE_LIMIT_CLEANUP_INTERVAL = int(os.getenv("RATE_LIMIT_CLEANUP_INTERVAL", "300"))  # 5 minutes

# Endpoints to bypass rate limiting
RATE_LIMIT_BYPASS_PATHS = [
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json"
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting API requests.

    Tracks requests per IP address and blocks excessive requests.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

        # In-memory storage: {ip_address: [(timestamp, ...)] }
        self.request_history = defaultdict(list)

        # Last cleanup timestamp
        self.last_cleanup = time.time()

        logger.info(
            f"Rate limiting enabled: {RATE_LIMIT_REQUESTS_PER_MINUTE} requests/minute per IP"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check rate limit before processing request.

        Args:
            request: FastAPI request
            call_next: Next middleware in chain

        Returns:
            Response: FastAPI response or 429 Too Many Requests
        """
        # Skip if disabled
        if not RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Bypass rate limiting for certain endpoints
        if any(request.url.path.startswith(path) for path in RATE_LIMIT_BYPASS_PATHS):
            return await call_next(request)

        # Extract IP address
        ip_address = self._get_client_ip(request)

        # Check rate limit
        if self._is_rate_limited(ip_address):
            logger.warning(
                f"Rate limit exceeded for IP: {ip_address} ({request.method} {request.url.path})",
                extra={
                    "ip_address": ip_address,
                    "method": request.method,
                    "path": request.url.path
                }
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "TooManyRequestsError",
                    "message": f"Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS_PER_MINUTE} requests per minute.",
                    "status_code": 429,
                    "detail": {
                        "limit": RATE_LIMIT_REQUESTS_PER_MINUTE,
                        "window": "1 minute",
                        "retry_after": 60
                    }
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS_PER_MINUTE),
                    "X-RateLimit-Remaining": "0"
                }
            )

        # Record request
        self._record_request(ip_address)

        # Cleanup old entries periodically
        self._cleanup_old_entries()

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        remaining = self._get_remaining_requests(ip_address)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.

        Checks proxy headers (X-Forwarded-For, X-Real-IP) before falling back to client.host.

        Args:
            request: FastAPI request

        Returns:
            str: Client IP address
        """
        # Check X-Forwarded-For header (proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the list (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to client.host
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, ip_address: str) -> bool:
        """
        Check if IP address has exceeded rate limit.

        Args:
            ip_address: Client IP address

        Returns:
            bool: True if rate limited, False otherwise
        """
        current_time = time.time()
        one_minute_ago = current_time - 60

        # Get requests from last minute
        recent_requests = [
            timestamp
            for timestamp in self.request_history[ip_address]
            if timestamp > one_minute_ago
        ]

        # Update history (remove old requests)
        self.request_history[ip_address] = recent_requests

        # Check if exceeded limit
        return len(recent_requests) >= RATE_LIMIT_REQUESTS_PER_MINUTE

    def _record_request(self, ip_address: str):
        """
        Record a request timestamp for an IP address.

        Args:
            ip_address: Client IP address
        """
        self.request_history[ip_address].append(time.time())

    def _get_remaining_requests(self, ip_address: str) -> int:
        """
        Get remaining requests for IP address in current window.

        Args:
            ip_address: Client IP address

        Returns:
            int: Number of remaining requests
        """
        current_time = time.time()
        one_minute_ago = current_time - 60

        # Count recent requests
        recent_count = sum(
            1
            for timestamp in self.request_history[ip_address]
            if timestamp > one_minute_ago
        )

        return RATE_LIMIT_REQUESTS_PER_MINUTE - recent_count

    def _cleanup_old_entries(self):
        """
        Periodically cleanup old entries to prevent memory leak.

        Removes entries older than cleanup interval.
        """
        current_time = time.time()

        # Only cleanup at intervals
        if current_time - self.last_cleanup < RATE_LIMIT_CLEANUP_INTERVAL:
            return

        logger.debug("Running rate limit cleanup...")

        # Cleanup threshold (requests older than 5 minutes)
        cleanup_threshold = current_time - RATE_LIMIT_CLEANUP_INTERVAL

        # Remove old entries
        removed_count = 0
        for ip_address in list(self.request_history.keys()):
            # Filter out old timestamps
            recent_requests = [
                timestamp
                for timestamp in self.request_history[ip_address]
                if timestamp > cleanup_threshold
            ]

            if recent_requests:
                self.request_history[ip_address] = recent_requests
            else:
                # Remove IP if no recent requests
                del self.request_history[ip_address]
                removed_count += 1

        self.last_cleanup = current_time

        logger.debug(
            f"Rate limit cleanup complete: removed {removed_count} IP addresses, "
            f"{len(self.request_history)} active"
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "RateLimitMiddleware"
]
