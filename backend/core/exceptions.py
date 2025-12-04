# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Custom Exception Hierarchy for LangConfig


Provides standardized exceptions for consistent error handling across the application.

Usage:
    from core.exceptions import ResourceNotFoundError, ConflictError

    if not workflow:
        raise ResourceNotFoundError("Workflow", workflow_id)

    if version_conflict:
        raise ConflictError(f"Workflow {workflow_id} was modified by another user")

Architecture:
- Base LangConfigException for all custom exceptions
- HTTP-specific exceptions (NotFound, Conflict, ValidationError, etc.)
- Business logic exceptions (ResourceNotFound, PermissionDenied, etc.)
- All exceptions include status_code and detail attributes
- Error handlers convert exceptions to standardized JSON responses
"""

from typing import Optional, Dict, Any


# =============================================================================
# Base Exception
# =============================================================================

class LangConfigException(Exception):
    """
    Base exception for all LangConfig custom exceptions.

    All custom exceptions should inherit from this class to ensure
    consistent error handling across the application.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        detail: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "status_code": self.status_code,
            "detail": self.detail
        }


# =============================================================================
# HTTP Status Code Exceptions (4xx Client Errors)
# =============================================================================

class BadRequestError(LangConfigException):
    """400 Bad Request - Client sent invalid data."""

    def __init__(self, message: str = "Bad request", detail: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, detail=detail)


class UnauthorizedError(LangConfigException):
    """401 Unauthorized - Authentication required."""

    def __init__(self, message: str = "Unauthorized", detail: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=401, detail=detail)


class ForbiddenError(LangConfigException):
    """403 Forbidden - User lacks permission."""

    def __init__(self, message: str = "Forbidden", detail: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=403, detail=detail)


class ResourceNotFoundError(LangConfigException):
    """404 Not Found - Resource does not exist."""

    def __init__(
        self,
        resource_type: str,
        resource_id: Any,
        detail: Optional[Dict[str, Any]] = None
    ):
        message = f"{resource_type} with id {resource_id} not found"
        super().__init__(message, status_code=404, detail=detail)


class ConflictError(LangConfigException):
    """409 Conflict - Resource state conflict (e.g., version mismatch)."""

    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=409, detail=detail)


class ValidationError(LangConfigException):
    """422 Unprocessable Entity - Validation failed."""

    def __init__(
        self,
        field: str,
        message: str,
        detail: Optional[Dict[str, Any]] = None
    ):
        full_message = f"Validation failed for field '{field}': {message}"
        detail = detail or {}
        detail["field"] = field
        super().__init__(full_message, status_code=422, detail=detail)


class TooManyRequestsError(LangConfigException):
    """429 Too Many Requests - Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Too many requests",
        retry_after: Optional[int] = None,
        detail: Optional[Dict[str, Any]] = None
    ):
        detail = detail or {}
        if retry_after:
            detail["retry_after"] = retry_after
        super().__init__(message, status_code=429, detail=detail)


# =============================================================================
# HTTP Status Code Exceptions (5xx Server Errors)
# =============================================================================

class InternalServerError(LangConfigException):
    """500 Internal Server Error - Unexpected server error."""

    def __init__(
        self,
        message: str = "Internal server error",
        detail: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=500, detail=detail)


class ServiceUnavailableError(LangConfigException):
    """503 Service Unavailable - Service temporarily unavailable."""

    def __init__(
        self,
        message: str = "Service unavailable",
        retry_after: Optional[int] = None,
        detail: Optional[Dict[str, Any]] = None
    ):
        detail = detail or {}
        if retry_after:
            detail["retry_after"] = retry_after
        super().__init__(message, status_code=503, detail=detail)


# =============================================================================
# Business Logic Exceptions
# =============================================================================

class WorkflowExecutionError(LangConfigException):
    """Workflow execution failed."""

    def __init__(
        self,
        workflow_id: int,
        message: str,
        detail: Optional[Dict[str, Any]] = None
    ):
        full_message = f"Workflow {workflow_id} execution failed: {message}"
        detail = detail or {}
        detail["workflow_id"] = workflow_id
        super().__init__(full_message, status_code=500, detail=detail)


class AgentExecutionError(LangConfigException):
    """Agent execution failed."""

    def __init__(
        self,
        agent_id: int,
        message: str,
        detail: Optional[Dict[str, Any]] = None
    ):
        full_message = f"Agent {agent_id} execution failed: {message}"
        detail = detail or {}
        detail["agent_id"] = agent_id
        super().__init__(full_message, status_code=500, detail=detail)


class ExportError(LangConfigException):
    """Export operation failed."""

    def __init__(
        self,
        export_type: str,
        message: str,
        detail: Optional[Dict[str, Any]] = None
    ):
        full_message = f"{export_type} export failed: {message}"
        detail = detail or {}
        detail["export_type"] = export_type
        super().__init__(full_message, status_code=500, detail=detail)


class DatabaseError(LangConfigException):
    """Database operation failed."""

    def __init__(
        self,
        operation: str,
        message: str,
        detail: Optional[Dict[str, Any]] = None
    ):
        full_message = f"Database {operation} failed: {message}"
        detail = detail or {}
        detail["operation"] = operation
        super().__init__(full_message, status_code=500, detail=detail)


class OptimisticLockError(ConflictError):
    """Optimistic locking conflict detected."""

    def __init__(
        self,
        resource_type: str,
        resource_id: int,
        client_version: int,
        database_version: int
    ):
        message = (
            f"{resource_type} {resource_id} was modified by another user. "
            f"Your version: {client_version}, current version: {database_version}. "
            f"Please refresh and try again."
        )
        detail = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "client_version": client_version,
            "database_version": database_version
        }
        super().__init__(message, detail=detail)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Base
    "LangConfigException",

    # HTTP 4xx
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "ResourceNotFoundError",
    "ConflictError",
    "ValidationError",
    "TooManyRequestsError",

    # HTTP 5xx
    "InternalServerError",
    "ServiceUnavailableError",

    # Business Logic
    "WorkflowExecutionError",
    "AgentExecutionError",
    "ExportError",
    "DatabaseError",
    "OptimisticLockError"
]
