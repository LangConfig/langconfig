# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI Error Handlers for LangConfig


Registers global error handlers to convert exceptions into standardized JSON responses.

Usage:
    from fastapi import FastAPI
    from core.error_handlers import register_error_handlers

    app = FastAPI()
    register_error_handlers(app)

Features:
- Catches all LangConfigException subclasses
- Returns standardized JSON error responses
- Logs errors with appropriate levels
- Handles SQLAlchemy exceptions (IntegrityError, etc.)
- Handles Pydantic validation errors
- Provides fallback handler for unexpected errors
"""

import logging
from typing import Union
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pydantic import ValidationError as PydanticValidationError

from core.exceptions import (
    LangConfigException,
    ResourceNotFoundError,
    ConflictError,
    ValidationError,
    DatabaseError
)

logger = logging.getLogger(__name__)


# =============================================================================
# Error Response Format
# =============================================================================

def create_error_response(
    status_code: int,
    error_type: str,
    message: str,
    detail: dict = None
) -> JSONResponse:
    """
    Create standardized JSON error response.

    Format:
        {
            "error": "ResourceNotFoundError",
            "message": "Workflow with id 123 not found",
            "status_code": 404,
            "detail": {
                "resource_type": "Workflow",
                "resource_id": 123
            }
        }
    """
    content = {
        "error": error_type,
        "message": message,
        "status_code": status_code
    }

    if detail:
        content["detail"] = detail

    return JSONResponse(
        status_code=status_code,
        content=content
    )


# =============================================================================
# Exception Handlers
# =============================================================================

async def langconfig_exception_handler(request: Request, exc: LangConfigException) -> JSONResponse:
    """
    Handle all LangConfigException subclasses.

    Converts custom exceptions to standardized JSON responses.
    Logs errors with appropriate severity levels.
    """
    # Log based on status code
    if exc.status_code >= 500:
        logger.error(
            f"Server error: {exc.message}",
            exc_info=True,
            extra={
                "exception_type": exc.__class__.__name__,
                "status_code": exc.status_code,
                "detail": exc.detail
            }
        )
    elif exc.status_code >= 400:
        logger.warning(
            f"Client error: {exc.message}",
            extra={
                "exception_type": exc.__class__.__name__,
                "status_code": exc.status_code,
                "detail": exc.detail
            }
        )

    return create_error_response(
        status_code=exc.status_code,
        error_type=exc.__class__.__name__,
        message=exc.message,
        detail=exc.detail
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle FastAPI/Pydantic validation errors.

    Converts validation errors to standardized format.
    """
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(
        f"Validation error: {len(errors)} fields failed validation",
        extra={"validation_errors": errors}
    )

    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_type="ValidationError",
        message="Request validation failed",
        detail={"errors": errors}
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """
    Handle SQLAlchemy IntegrityError (unique constraints, foreign keys, etc.).

    Provides user-friendly messages for database constraint violations.
    """
    error_message = str(exc.orig) if hasattr(exc, 'orig') else str(exc)

    # Parse common constraint violations
    if "unique constraint" in error_message.lower():
        message = "A record with this value already exists"
        detail_type = "unique_constraint_violation"
    elif "foreign key constraint" in error_message.lower():
        message = "Referenced resource does not exist"
        detail_type = "foreign_key_violation"
    elif "not null constraint" in error_message.lower():
        message = "Required field is missing"
        detail_type = "not_null_violation"
    else:
        message = "Database constraint violation"
        detail_type = "constraint_violation"

    logger.error(
        f"Database integrity error: {error_message}",
        exc_info=True,
        extra={"detail_type": detail_type}
    )

    return create_error_response(
        status_code=status.HTTP_409_CONFLICT,
        error_type="DatabaseIntegrityError",
        message=message,
        detail={
            "type": detail_type,
            "database_message": error_message
        }
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    Handle generic SQLAlchemy errors.

    Catches database errors not handled by specific handlers.
    """
    error_message = str(exc.orig) if hasattr(exc, 'orig') else str(exc)

    logger.error(
        f"Database error: {error_message}",
        exc_info=True,
        extra={"exception_type": exc.__class__.__name__}
    )

    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type="DatabaseError",
        message="Database operation failed",
        detail={
            "database_message": error_message
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions.

    Logs full stack trace and returns generic error response.
    """
    logger.error(
        f"Unexpected error: {str(exc)}",
        exc_info=True,
        extra={
            "exception_type": exc.__class__.__name__,
            "request_path": request.url.path,
            "request_method": request.method
        }
    )

    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type="InternalServerError",
        message="An unexpected error occurred",
        detail={
            "exception_type": exc.__class__.__name__
        }
    )


# =============================================================================
# Registration
# =============================================================================

def register_error_handlers(app: FastAPI) -> None:
    """
    Register all error handlers with FastAPI application.

    Call this function during application startup to enable
    standardized error handling across all endpoints.

    Usage:
        from fastapi import FastAPI
        from core.error_handlers import register_error_handlers

        app = FastAPI()
        register_error_handlers(app)
    """
    # Custom LangConfig exceptions
    app.add_exception_handler(LangConfigException, langconfig_exception_handler)

    # FastAPI/Pydantic validation errors
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    # SQLAlchemy database errors
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)

    # Generic catch-all for unexpected errors
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Error handlers registered successfully")


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "register_error_handlers",
    "create_error_response",
    "langconfig_exception_handler",
    "validation_error_handler",
    "integrity_error_handler",
    "sqlalchemy_error_handler",
    "generic_exception_handler"
]
