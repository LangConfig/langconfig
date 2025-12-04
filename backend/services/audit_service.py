# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Audit Logging Service


Provides centralized audit logging for all important operations.

Usage:
    from services.audit_service import audit_log
    from models.audit_log import AuditAction

    # In endpoint
    @router.patch("/workflows/{workflow_id}")
    async def update_workflow(workflow_id: int, request: Request, db: Session):
        old_name = workflow.name
        workflow.name = "New Name"
        db.commit()

        # Log the operation
        await audit_log(
            db=db,
            request=request,
            action=AuditAction.UPDATE,
            resource_type="Workflow",
            resource_id=workflow_id,
            changes={"name": {"old": old_name, "new": workflow.name}},
            message="Updated workflow name"
        )

Features:
- Automatic request context extraction (IP, user agent, endpoint)
- Optional change tracking (before/after values)
- Flexible additional context storage
- Async-safe (doesn't block request processing)
- Handles errors gracefully (won't crash app if logging fails)

Privacy Notes (for open-source self-hosted software):
- IP tracking is OPTIONAL (can be disabled via AUDIT_LOG_TRACK_IP=false)
- All data stays on your local server (never sent anywhere)
- Useful for security monitoring and debugging in production
- If you don't need it, disable it in .env
"""

import logging
import os
from typing import Optional, Dict, Any
from fastapi import Request
from sqlalchemy.orm import Session
from models.audit_log import AuditLog, AuditAction
import json

logger = logging.getLogger(__name__)

# Configuration: Allow disabling IP tracking for privacy
AUDIT_LOG_ENABLED = os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true"
AUDIT_LOG_TRACK_IP = os.getenv("AUDIT_LOG_TRACK_IP", "true").lower() == "true"
AUDIT_LOG_TRACK_USER_AGENT = os.getenv("AUDIT_LOG_TRACK_USER_AGENT", "true").lower() == "true"


# =============================================================================
# Core Audit Logging Functions
# =============================================================================

async def audit_log(
    db: Session,
    request: Optional[Request],
    action: AuditAction,
    resource_type: str,
    resource_id: Optional[int] = None,
    user_id: Optional[int] = None,
    changes: Optional[Dict[str, Any]] = None,
    additional_context: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    status_code: Optional[int] = None,
    duration_ms: Optional[float] = None
) -> Optional[AuditLog]:
    """
    Log an operation to the audit log.

    Args:
        db: Database session
        request: FastAPI Request object (for extracting IP, user agent, etc.)
        action: Type of action (CREATE, UPDATE, DELETE, etc.)
        resource_type: Type of resource (Workflow, Agent, Tool, etc.)
        resource_id: ID of affected resource (optional for bulk operations)
        user_id: User who performed the action (optional)
        changes: Before/after values for updates (optional)
        additional_context: Additional context (optional)
        message: Human-readable description (optional)
        status_code: HTTP status code (optional, auto-detected from request)
        duration_ms: Request duration in milliseconds (optional)

    Returns:
        AuditLog: Created audit log entry, or None if logging failed

    Example:
        await audit_log(
            db=db,
            request=request,
            action=AuditAction.UPDATE,
            resource_type="Workflow",
            resource_id=123,
            changes={"name": {"old": "Old", "new": "New"}},
            message="Updated workflow name"
        )
    """
    try:
        # Check if audit logging is enabled
        if not AUDIT_LOG_ENABLED:
            return None

        # Extract request context
        ip_address = None
        user_agent = None
        request_method = None
        endpoint = None
        query_params = None

        if request:
            # Extract IP address (only if enabled)
            if AUDIT_LOG_TRACK_IP:
                ip_address = (
                    request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                    or request.headers.get("X-Real-IP")
                    or (request.client.host if request.client else None)
                )

            # Extract user agent (only if enabled)
            if AUDIT_LOG_TRACK_USER_AGENT:
                user_agent = request.headers.get("User-Agent")

            # Extract request details
            request_method = request.method
            endpoint = str(request.url.path)

            # Extract query parameters
            if request.url.query:
                query_params = dict(request.query_params)

        # Determine success based on status code
        success = 1  # Default to success
        if status_code and status_code >= 400:
            success = 0

        # Create audit log entry
        audit_entry = AuditLog(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action=action.value if isinstance(action, AuditAction) else action,
            resource_type=resource_type,
            resource_id=resource_id,
            duration_ms=duration_ms,
            status_code=status_code,
            success=success,
            request_method=request_method,
            endpoint=endpoint,
            query_params=query_params,
            changes=changes,
            additional_context=additional_context,
            message=message
        )

        # Save to database
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)

        logger.debug(
            f"Audit log created: {action} {resource_type} {resource_id}",
            extra={
                "audit_id": audit_entry.id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id
            }
        )

        return audit_entry

    except Exception as e:
        # Log error but don't crash the application
        logger.error(
            f"Failed to create audit log: {e}",
            exc_info=True,
            extra={
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id
            }
        )
        # Rollback to prevent transaction issues
        db.rollback()
        return None


def audit_log_sync(
    db: Session,
    action: AuditAction,
    resource_type: str,
    resource_id: Optional[int] = None,
    user_id: Optional[int] = None,
    changes: Optional[Dict[str, Any]] = None,
    additional_context: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    status_code: Optional[int] = None,
    ip_address: Optional[str] = None
) -> Optional[AuditLog]:
    """
    Synchronous version of audit_log for non-async contexts.

    Use this in background tasks, scripts, or synchronous code.

    Args:
        db: Database session
        action: Type of action (CREATE, UPDATE, DELETE, etc.)
        resource_type: Type of resource (Workflow, Agent, Tool, etc.)
        resource_id: ID of affected resource (optional)
        user_id: User who performed the action (optional)
        changes: Before/after values (optional)
        additional_context: Additional context (optional)
        message: Human-readable description (optional)
        status_code: HTTP status code (optional)
        ip_address: Client IP address (optional)

    Returns:
        AuditLog: Created audit log entry, or None if logging failed

    Example:
        audit_log_sync(
            db=db,
            action=AuditAction.EXECUTE,
            resource_type="Workflow",
            resource_id=123,
            message="Workflow executed successfully"
        )
    """
    try:
        # Determine success based on status code
        success = 1  # Default to success
        if status_code and status_code >= 400:
            success = 0

        # Create audit log entry
        audit_entry = AuditLog(
            user_id=user_id,
            ip_address=ip_address,
            action=action.value if isinstance(action, AuditAction) else action,
            resource_type=resource_type,
            resource_id=resource_id,
            status_code=status_code,
            success=success,
            changes=changes,
            additional_context=additional_context,
            message=message
        )

        # Save to database
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)

        logger.debug(
            f"Audit log created (sync): {action} {resource_type} {resource_id}",
            extra={
                "audit_id": audit_entry.id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id
            }
        )

        return audit_entry

    except Exception as e:
        # Log error but don't crash
        logger.error(
            f"Failed to create audit log (sync): {e}",
            exc_info=True,
            extra={
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id
            }
        )
        # Rollback to prevent transaction issues
        db.rollback()
        return None


# =============================================================================
# Helper Functions
# =============================================================================

def extract_changes(old_obj: Any, new_obj: Any, fields: list[str]) -> Dict[str, Dict[str, Any]]:
    """
    Extract changes between old and new objects for specified fields.

    Args:
        old_obj: Original object (before update)
        new_obj: Updated object (after update)
        fields: List of field names to track

    Returns:
        dict: Changes in format {"field": {"old": value, "new": value}}

    Example:
        changes = extract_changes(
            old_workflow,
            new_workflow,
            ["name", "description", "configuration"]
        )
        # {"name": {"old": "Old Name", "new": "New Name"}}
    """
    changes = {}

    for field in fields:
        old_value = getattr(old_obj, field, None)
        new_value = getattr(new_obj, field, None)

        # Convert to JSON-serializable format
        if hasattr(old_value, "__dict__"):
            old_value = old_value.__dict__
        if hasattr(new_value, "__dict__"):
            new_value = new_value.__dict__

        # Only log if actually changed
        if old_value != new_value:
            changes[field] = {
                "old": old_value,
                "new": new_value
            }

    return changes if changes else None


# =============================================================================
# Query Helpers
# =============================================================================

def get_audit_logs(
    db: Session,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    user_id: Optional[int] = None,
    action: Optional[AuditAction] = None,
    success: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0
) -> list[AuditLog]:
    """
    Query audit logs with filters.

    Args:
        db: Database session
        resource_type: Filter by resource type (optional)
        resource_id: Filter by resource ID (optional)
        user_id: Filter by user ID (optional)
        action: Filter by action type (optional)
        success: Filter by success status (optional)
        limit: Max results to return (default: 100)
        offset: Pagination offset (default: 0)

    Returns:
        list[AuditLog]: Matching audit log entries

    Example:
        # Get all failed operations
        failed_logs = get_audit_logs(db, success=False, limit=50)

        # Get all updates to a specific workflow
        workflow_logs = get_audit_logs(
            db,
            resource_type="Workflow",
            resource_id=123,
            action=AuditAction.UPDATE
        )
    """
    query = db.query(AuditLog)

    # Apply filters
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    if resource_id is not None:
        query = query.filter(AuditLog.resource_id == resource_id)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)

    if action:
        query = query.filter(AuditLog.action == action.value)

    if success is not None:
        query = query.filter(AuditLog.success == (1 if success else 0))

    # Order by most recent first
    query = query.order_by(AuditLog.timestamp.desc())

    # Apply pagination
    query = query.limit(limit).offset(offset)

    return query.all()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "audit_log",
    "audit_log_sync",
    "extract_changes",
    "get_audit_logs"
]
