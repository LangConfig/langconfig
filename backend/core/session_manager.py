# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Transaction Management Framework

Provides context managers for safe, consistent transaction handling across the application.

Features:
- Automatic commit/rollback based on context exit
- Nested savepoints for complex operations
- Transaction logging and metrics
- Deadlock retry logic with exponential backoff
- Clear transaction boundaries

Usage:
    from core.session_manager import managed_transaction

    @router.patch("/{workflow_id}")
    async def update_workflow(workflow_id: int, db: Session = Depends(get_db)):
        with managed_transaction(db, "update_workflow") as tx:
            # Update workflow
            workflow.name = "Updated"

            # Nested savepoint for optional operation
            try:
                with tx.savepoint("auto_export"):
                    await export_operation()  # Can fail independently
            except Exception:
                pass  # Export fails but main update succeeds

            # Automatic commit here (or rollback on exception)
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional, Generator
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DBAPIError
import psycopg2.errors

logger = logging.getLogger(__name__)


# =============================================================================
# Transaction Context Manager
# =============================================================================

class TransactionContext:
    """
    Manages a database transaction with support for savepoints.

    Attributes:
        session: SQLAlchemy session
        name: Transaction name for logging
        start_time: Transaction start timestamp
        committed: Whether transaction was successfully committed
    """

    def __init__(self, session: Session, name: str):
        """
        Initialize transaction context.

        Args:
            session: SQLAlchemy session
            name: Transaction name for logging/metrics
        """
        self.session = session
        self.name = name
        self.start_time = None
        self.committed = False
        self._in_transaction = False

    def __enter__(self):
        """Enter transaction context."""
        self.start_time = time.time()
        self._in_transaction = True
        logger.debug(f"Transaction started: {self.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit transaction context.

        Automatically commits on success or rolls back on exception.

        Args:
            exc_type: Exception type if any
            exc_val: Exception value if any
            exc_tb: Exception traceback if any
        """
        duration_ms = (time.time() - self.start_time) * 1000

        if exc_type is None:
            # No exception - commit transaction
            try:
                self.session.commit()
                self.committed = True
                logger.debug(f"Transaction committed: {self.name} ({duration_ms:.2f}ms)")

                # Log structured event for metrics
                logger.info(
                    "TRANSACTION_COMMITTED",
                    extra={
                        "transaction_name": self.name,
                        "duration_ms": duration_ms,
                        "committed": True
                    }
                )
            except Exception as e:
                logger.error(f"Transaction commit failed: {self.name} - {e}")
                self.session.rollback()
                self.committed = False
                raise
        else:
            # Exception occurred - rollback transaction
            self.session.rollback()
            self.committed = False
            logger.warning(
                f"Transaction rolled back: {self.name} ({duration_ms:.2f}ms) "
                f"due to {exc_type.__name__}: {exc_val}"
            )

            # Log structured event for metrics
            logger.info(
                "TRANSACTION_ROLLBACK",
                extra={
                    "transaction_name": self.name,
                    "duration_ms": duration_ms,
                    "committed": False,
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val)
                }
            )

        self._in_transaction = False

        # Don't suppress exceptions - let them propagate
        return False

    @contextmanager
    def savepoint(self, name: str) -> Generator[None, None, None]:
        """
        Create a nested savepoint within the transaction.

        Savepoints allow partial rollback - if the savepoint operation fails,
        only that part is rolled back, not the entire transaction.

        Args:
            name: Savepoint name for logging

        Example:
            with managed_transaction(db, "update_workflow") as tx:
                workflow.name = "Updated"

                try:
                    with tx.savepoint("auto_export"):
                        await export_operation()  # Can fail
                except Exception:
                    pass  # Export fails, but workflow update succeeds

        Yields:
            None
        """
        if not self._in_transaction:
            raise RuntimeError("Cannot create savepoint outside of transaction")

        savepoint_start = time.time()
        logger.debug(f"Savepoint started: {self.name}.{name}")

        # Begin nested transaction (savepoint)
        nested = self.session.begin_nested()

        try:
            yield
            # Commit savepoint on success
            nested.commit()
            duration_ms = (time.time() - savepoint_start) * 1000
            logger.debug(f"Savepoint committed: {self.name}.{name} ({duration_ms:.2f}ms)")

        except Exception as e:
            # Rollback savepoint on error
            nested.rollback()
            duration_ms = (time.time() - savepoint_start) * 1000
            logger.warning(
                f"Savepoint rolled back: {self.name}.{name} ({duration_ms:.2f}ms) "
                f"due to {type(e).__name__}: {e}"
            )
            raise


# =============================================================================
# Context Manager Functions
# =============================================================================

@contextmanager
def managed_transaction(
    session: Session,
    name: str,
    max_retries: int = 3,
    retry_delay: float = 0.1
) -> Generator[TransactionContext, None, None]:
    """
    Create a managed database transaction with automatic commit/rollback.

    Handles:
    - Automatic commit on success
    - Automatic rollback on exception
    - Deadlock detection and retry
    - Transaction logging and metrics

    Args:
        session: SQLAlchemy session
        name: Transaction name for logging/metrics
        max_retries: Maximum retry attempts for deadlocks (default: 3)
        retry_delay: Initial retry delay in seconds (default: 0.1)

    Yields:
        TransactionContext: Transaction context with savepoint support

    Raises:
        Exception: Any exception from the transaction block

    Example:
        with managed_transaction(db, "update_workflow") as tx:
            workflow.name = "Updated"
            # Auto-commits here

    Example with savepoint:
        with managed_transaction(db, "complex_operation") as tx:
            # Main operation
            workflow.update(...)

            # Optional sub-operation
            try:
                with tx.savepoint("export"):
                    export_workflow(...)
            except Exception:
                pass  # Export fails, main update succeeds
    """
    attempts = 0
    last_exception = None

    while attempts < max_retries:
        attempts += 1

        try:
            # Create and enter transaction context
            with TransactionContext(session, name) as tx:
                yield tx
                return  # Success - exit retry loop

        except (OperationalError, DBAPIError) as e:
            # Check if this is a deadlock error
            is_deadlock = False

            if isinstance(e.orig, psycopg2.errors.DeadlockDetected):
                is_deadlock = True

            if is_deadlock and attempts < max_retries:
                # Retry with exponential backoff
                delay = retry_delay * (2 ** (attempts - 1))
                logger.warning(
                    f"Deadlock detected in transaction {name}, "
                    f"retrying ({attempts}/{max_retries}) after {delay}s"
                )
                time.sleep(delay)
                last_exception = e
                continue
            else:
                # Not a deadlock, or max retries exceeded
                raise

        except Exception as e:
            # Non-deadlock exception - don't retry
            raise

    # Max retries exceeded
    logger.error(
        f"Transaction {name} failed after {max_retries} attempts due to deadlocks"
    )
    raise last_exception


# =============================================================================
# Utility Functions
# =============================================================================

def is_in_transaction(session: Session) -> bool:
    """
    Check if session is currently in a transaction.

    Args:
        session: SQLAlchemy session

    Returns:
        bool: True if in transaction, False otherwise
    """
    return session.in_transaction()


def get_transaction_isolation_level(session: Session) -> Optional[str]:
    """
    Get the current transaction isolation level.

    Args:
        session: SQLAlchemy session

    Returns:
        Optional[str]: Isolation level name or None
    """
    try:
        result = session.execute("SHOW transaction_isolation")
        return result.scalar()
    except Exception as e:
        logger.error(f"Failed to get transaction isolation level: {e}")
        return None


@contextmanager
def transaction_isolation(
    session: Session,
    level: str
) -> Generator[None, None, None]:
    """
    Temporarily set transaction isolation level.

    Args:
        session: SQLAlchemy session
        level: Isolation level ('READ UNCOMMITTED', 'READ COMMITTED',
               'REPEATABLE READ', 'SERIALIZABLE')

    Yields:
        None

    Example:
        with transaction_isolation(db, 'SERIALIZABLE'):
            # Critical operation requiring serializable isolation
            update_workflow_version(...)
    """
    # Get current isolation level
    original_level = get_transaction_isolation_level(session)

    try:
        # Set new isolation level
        session.execute(f"SET TRANSACTION ISOLATION LEVEL {level}")
        logger.debug(f"Set transaction isolation level to {level}")
        yield

    finally:
        # Restore original isolation level if we got it
        if original_level:
            session.execute(f"SET TRANSACTION ISOLATION LEVEL {original_level}")
            logger.debug(f"Restored transaction isolation level to {original_level}")


# =============================================================================
# Metrics and Monitoring
# =============================================================================

class TransactionMetrics:
    """
    Tracks transaction metrics for monitoring.

    Can be used to expose metrics to Prometheus, StatsD, or other monitoring systems.
    """

    def __init__(self):
        """Initialize metrics tracking."""
        self.transaction_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.deadlock_count = 0
        self.total_duration_ms = 0.0

    def record_commit(self, duration_ms: float):
        """Record a successful commit."""
        self.transaction_count += 1
        self.commit_count += 1
        self.total_duration_ms += duration_ms

    def record_rollback(self, duration_ms: float):
        """Record a rollback."""
        self.transaction_count += 1
        self.rollback_count += 1
        self.total_duration_ms += duration_ms

    def record_deadlock(self):
        """Record a deadlock occurrence."""
        self.deadlock_count += 1

    def get_stats(self) -> dict:
        """
        Get current metrics statistics.

        Returns:
            dict: Statistics including counts, rates, and averages
        """
        avg_duration = (
            self.total_duration_ms / self.transaction_count
            if self.transaction_count > 0
            else 0.0
        )

        commit_rate = (
            self.commit_count / self.transaction_count
            if self.transaction_count > 0
            else 0.0
        )

        return {
            "transaction_count": self.transaction_count,
            "commit_count": self.commit_count,
            "rollback_count": self.rollback_count,
            "deadlock_count": self.deadlock_count,
            "commit_rate": commit_rate,
            "avg_duration_ms": avg_duration,
            "total_duration_ms": self.total_duration_ms
        }

    def reset(self):
        """Reset all metrics to zero."""
        self.transaction_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.deadlock_count = 0
        self.total_duration_ms = 0.0


# Global metrics instance
transaction_metrics = TransactionMetrics()
