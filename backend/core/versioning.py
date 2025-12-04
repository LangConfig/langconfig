# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Optimistic Locking Framework


Provides optimistic locking to prevent lost updates from concurrent modifications.

Key Features:
- Version column tracks modification count
- Automatic version increment on update
- Conflict detection when versions don't match
- Works with any SQLAlchemy model

Usage:
    from core.versioning import OptimisticLockMixin, check_version_conflict

    class WorkflowProfile(Base, OptimisticLockMixin):
        __tablename__ = "workflow_profiles"
        # ... other fields

    # In endpoint
    if check_version_conflict(workflow, client_version):
        raise ConflictError("Workflow modified by another user")

    # Update workflow (version auto-increments)
    workflow.name = "Updated Name"
    db.commit()

Architecture:
- OptimisticLockMixin: Adds version column to models
- check_version_conflict(): Validates client version matches database
- get_current_version(): Retrieves latest version from database
- SQLAlchemy event listener: Auto-increments version on update

Concurrency Scenario:
    User A                  User B
    ─────────────────       ─────────────────
    GET /workflows/1        GET /workflows/1
    version=5               version=5

    PATCH /workflows/1
    version=5 ✓
    → version=6
                            PATCH /workflows/1
                            version=5 ✗
                            → 409 Conflict!
"""

import logging
from typing import Optional, Type
from sqlalchemy import Column, Integer, event
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declared_attr

logger = logging.getLogger(__name__)


# =============================================================================
# Optimistic Lock Mixin
# =============================================================================

class OptimisticLockMixin:
    """
    Mixin that adds optimistic locking to SQLAlchemy models.

    Adds a lock_version column that is automatically incremented on each update.
    This prevents lost updates from concurrent modifications.

    Usage:
        class MyModel(Base, OptimisticLockMixin):
            __tablename__ = "my_table"
            # ... other fields

    The lock_version column will be automatically:
    - Added to the model (default: 1)
    - Incremented on every update
    - Checked before updates to detect conflicts

    Note: Named 'lock_version' to avoid conflicts with semantic versioning fields.
    """

    @declared_attr
    def lock_version(cls):
        """
        Lock version column for optimistic locking.

        Default value: 1
        Increments on every update
        """
        return Column(Integer, nullable=False, default=1, server_default="1")

    def increment_lock_version(self):
        """Manually increment lock version (used in UPDATE queries)."""
        self.lock_version += 1

    def get_lock_version(self) -> int:
        """Get current lock version."""
        return self.lock_version


# =============================================================================
# Version Conflict Detection
# =============================================================================

def check_version_conflict(instance: OptimisticLockMixin, client_lock_version: int) -> bool:
    """
    Check if client lock version conflicts with database lock version.

    Args:
        instance: Model instance with OptimisticLockMixin
        client_lock_version: Lock version from client request

    Returns:
        bool: True if conflict detected, False otherwise

    Example:
        if check_version_conflict(workflow, request.lock_version):
            raise HTTPException(409, "Workflow modified by another user")
    """
    if not hasattr(instance, 'lock_version'):
        logger.warning(
            f"Instance {type(instance).__name__} does not have lock_version column. "
            "Skipping version check."
        )
        return False

    current_lock_version = instance.lock_version
    has_conflict = current_lock_version != client_lock_version

    if has_conflict:
        logger.warning(
            f"Version conflict detected for {type(instance).__name__} id={instance.id}: "
            f"client lock_version={client_lock_version}, database lock_version={current_lock_version}",
            extra={
                "model": type(instance).__name__,
                "instance_id": instance.id,
                "client_lock_version": client_lock_version,
                "database_lock_version": current_lock_version
            }
        )

    return has_conflict


def get_current_lock_version(
    db: Session,
    model_class: Type,
    instance_id: int
) -> Optional[int]:
    """
    Get current lock version from database.

    Useful for checking lock version before loading full instance.

    Args:
        db: Database session
        model_class: Model class (e.g., WorkflowProfile)
        instance_id: Instance ID

    Returns:
        int: Current lock version or None if not found

    Example:
        current_lock_version = get_current_lock_version(db, WorkflowProfile, workflow_id)
        if current_lock_version != client_lock_version:
            raise ConflictError("Version mismatch")
    """
    if not hasattr(model_class, 'lock_version'):
        logger.warning(
            f"Model {model_class.__name__} does not have lock_version column. "
            "Skipping version check."
        )
        return None

    result = db.query(model_class.lock_version).filter(
        model_class.id == instance_id
    ).first()

    return result[0] if result else None


# =============================================================================
# Atomic Update with Version Check
# =============================================================================

def atomic_update_with_lock_version(
    db: Session,
    model_class: Type,
    instance_id: int,
    client_lock_version: int,
    updates: dict
) -> bool:
    """
    Atomically update instance with lock version check.

    Uses UPDATE WHERE id=X AND lock_version=Y pattern to ensure atomic
    compare-and-swap operation.

    Args:
        db: Database session
        model_class: Model class (e.g., WorkflowProfile)
        instance_id: Instance ID to update
        client_lock_version: Lock version from client request
        updates: Dictionary of field updates

    Returns:
        bool: True if update succeeded, False if version conflict

    Example:
        success = atomic_update_with_lock_version(
            db,
            WorkflowProfile,
            workflow_id=123,
            client_lock_version=5,
            updates={"name": "New Name", "description": "Updated"}
        )

        if not success:
            raise ConflictError("Workflow modified by another user")

    SQL Generated:
        UPDATE workflow_profiles
        SET name = 'New Name',
            description = 'Updated',
            lock_version = lock_version + 1
        WHERE id = 123 AND lock_version = 5
        RETURNING id;
    """
    from sqlalchemy import update, and_

    # Add lock version increment to updates
    updates_with_version = {**updates, "lock_version": model_class.lock_version + 1}

    # Build atomic update query
    stmt = (
        update(model_class)
        .where(
            and_(
                model_class.id == instance_id,
                model_class.lock_version == client_lock_version
            )
        )
        .values(**updates_with_version)
        .returning(model_class.id)
    )

    # Execute and check if any row was updated
    result = db.execute(stmt)
    updated_id = result.scalar_one_or_none()

    if updated_id:
        logger.info(
            f"Atomic update succeeded for {model_class.__name__} id={instance_id}",
            extra={
                "model": model_class.__name__,
                "instance_id": instance_id,
                "client_lock_version": client_lock_version,
                "new_lock_version": client_lock_version + 1
            }
        )
        return True
    else:
        logger.warning(
            f"Atomic update failed for {model_class.__name__} id={instance_id} - version conflict",
            extra={
                "model": model_class.__name__,
                "instance_id": instance_id,
                "client_lock_version": client_lock_version
            }
        )
        return False


# =============================================================================
# SQLAlchemy Event Listeners
# =============================================================================

def setup_version_listeners():
    """
    Setup SQLAlchemy event listeners for automatic version increment.

    This function should be called once during application startup.

    Event listeners automatically increment version column on update.
    This ensures version is always incremented without manual intervention.
    """
    @event.listens_for(Session, 'before_flush')
    def increment_lock_version_on_update(session, flush_context, instances):
        """
        Automatically increment lock version on update.

        Listens to SQLAlchemy flush event and increments lock_version
        for all modified instances that have OptimisticLockMixin.
        """
        for instance in session.dirty:
            # Skip if not modified (only session state changed)
            if not session.is_modified(instance):
                continue

            # Check if instance has lock_version column
            if hasattr(instance, 'lock_version') and isinstance(instance, OptimisticLockMixin):
                # Increment lock version
                old_lock_version = instance.lock_version
                instance.lock_version += 1

                logger.debug(
                    f"Auto-incremented lock_version for {type(instance).__name__} id={instance.id}: "
                    f"{old_lock_version} → {instance.lock_version}",
                    extra={
                        "model": type(instance).__name__,
                        "instance_id": getattr(instance, 'id', None),
                        "old_lock_version": old_lock_version,
                        "new_lock_version": instance.lock_version
                    }
                )

    logger.info("Optimistic locking event listeners registered")


# =============================================================================
# Helper Functions
# =============================================================================

def is_lock_version_enabled(instance) -> bool:
    """
    Check if instance has optimistic locking enabled.

    Args:
        instance: Model instance

    Returns:
        bool: True if optimistic locking is enabled, False otherwise
    """
    return hasattr(instance, 'lock_version') and isinstance(instance, OptimisticLockMixin)


def format_lock_version_error(
    model_name: str,
    instance_id: int,
    client_lock_version: int,
    database_lock_version: int
) -> str:
    """
    Format user-friendly lock version conflict error message.

    Args:
        model_name: Name of the model (e.g., "Workflow")
        instance_id: Instance ID
        client_lock_version: Lock version from client
        database_lock_version: Current lock version in database

    Returns:
        str: Formatted error message

    Example:
        "Workflow 123 was modified by another user. Your version: 5, current version: 7. Please refresh and try again."
    """
    return (
        f"{model_name} {instance_id} was modified by another user. "
        f"Your version: {client_lock_version}, current version: {database_lock_version}. "
        f"Please refresh and try again."
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "OptimisticLockMixin",
    "check_version_conflict",
    "get_current_lock_version",
    "atomic_update_with_lock_version",
    "setup_version_listeners",
    "is_lock_version_enabled",
    "format_lock_version_error"
]
