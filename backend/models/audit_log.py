# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Audit Log Models for LangConfig


Tracks all important operations for compliance, security, and debugging.

Features:
- Comprehensive operation tracking (CREATE, READ, UPDATE, DELETE)
- User attribution and IP tracking
- Request/response capture
- Performance metrics (duration, status code)
- Flexible metadata storage (JSONB)
- Efficient querying with indexes

Usage:
    from models.audit_log import AuditLog, AuditAction
    from services.audit_service import audit_log

    # Log operation
    await audit_log(
        user_id=user.id,
        action=AuditAction.UPDATE,
        resource_type="Workflow",
        resource_id=workflow.id,
        changes={"name": {"old": "Old Name", "new": "New Name"}},
        request=request
    )
"""

from sqlalchemy import Column, Integer, String, JSON, DateTime, Float, Text, Index
from sqlalchemy.sql import func
from db.database import Base
from enum import Enum
import datetime


# =============================================================================
# Enums
# =============================================================================

class AuditAction(str, Enum):
    """Actions that can be audited."""
    # CRUD operations
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

    # Authentication
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"

    # Special operations
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    EXECUTE = "EXECUTE"  # For workflow/agent execution
    APPROVE = "APPROVE"  # For HITL approvals
    REJECT = "REJECT"


# =============================================================================
# Database Model
# =============================================================================

class AuditLog(Base):
    """
    Audit log for tracking all important operations.

    Captures:
    - Who performed the action (user_id, ip_address)
    - What action was performed (action, resource_type, resource_id)
    - When it happened (timestamp)
    - How it went (status_code, duration)
    - What changed (changes, metadata)
    - Context (request_method, endpoint, user_agent)
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Who (Actor)
    user_id = Column(Integer, nullable=True, index=True)  # Optional - some operations may be anonymous
    ip_address = Column(String(45), nullable=True)  # IPv4 (15) or IPv6 (45)
    user_agent = Column(String(500), nullable=True)

    # What (Action)
    action = Column(String(50), nullable=False, index=True)  # CREATE, UPDATE, DELETE, etc.
    resource_type = Column(String(100), nullable=False, index=True)  # Workflow, Agent, Tool, etc.
    resource_id = Column(Integer, nullable=True, index=True)  # ID of affected resource

    # When (Timing)
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    duration_ms = Column(Float, nullable=True)  # Request duration in milliseconds

    # How (Result)
    status_code = Column(Integer, nullable=True, index=True)  # HTTP status code (200, 404, 500, etc.)
    success = Column(Integer, nullable=False, default=1)  # 1 = success, 0 = failure (for quick filtering)

    # Context (Request Details)
    request_method = Column(String(10), nullable=True)  # GET, POST, PATCH, DELETE
    endpoint = Column(String(500), nullable=True, index=True)  # /api/workflows/123
    query_params = Column(JSON, nullable=True)  # Query string parameters

    # Changes (What changed)
    changes = Column(JSON, nullable=True)  # Before/after values for updates
    additional_context = Column(JSON, nullable=True)  # Additional context (error details, etc.)

    # Message (Human-readable description)
    message = Column(Text, nullable=True)  # Optional description of the operation

    def __repr__(self):
        return (
            f"<AuditLog(id={self.id}, action='{self.action}', "
            f"resource_type='{self.resource_type}', resource_id={self.resource_id})>"
        )

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "duration_ms": self.duration_ms,
            "status_code": self.status_code,
            "success": bool(self.success),
            "request_method": self.request_method,
            "endpoint": self.endpoint,
            "query_params": self.query_params,
            "changes": self.changes,
            "additional_context": self.additional_context,
            "message": self.message
        }


# Create composite indexes for common queries
Index(
    "idx_audit_resource_lookup",
    AuditLog.resource_type,
    AuditLog.resource_id,
    AuditLog.timestamp.desc()
)

Index(
    "idx_audit_user_activity",
    AuditLog.user_id,
    AuditLog.timestamp.desc()
)

Index(
    "idx_audit_failed_operations",
    AuditLog.success,
    AuditLog.timestamp.desc()
)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AuditLog",
    "AuditAction"
]
