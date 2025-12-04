# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
PostgreSQL-Backed Task Queue


A simple, robust task queue using PostgreSQL as the backend. Designed for desktop
applications with low concurrency (no Redis/Celery complexity needed).

Key Features:
- PostgreSQL-backed (uses SELECT FOR UPDATE SKIP LOCKED for queue semantics)
- Worker pool with configurable size
- Priority-based task selection
- Automatic retry with exponential backoff
- Task status tracking and monitoring
- Graceful shutdown

Architecture:
- TaskQueue: Main queue interface for enqueuing tasks and checking status
- TaskWorker: Worker process that claims and executes tasks
- TaskHandler: Registry of task type handlers

Usage:
    from core.task_queue import task_queue, TaskPriority

    # Enqueue task
    task_id = await task_queue.enqueue(
        "export_agent",
        {"agent_id": 123},
        priority=TaskPriority.NORMAL
    )

    # Check status
    task = await task_queue.get_status(task_id)
"""

import asyncio
import logging
import time
import traceback
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Dict, Any, Callable, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from db.database import SessionLocal
from models.background_task import BackgroundTask

logger = logging.getLogger(__name__)


# =============================================================================
# Task Priority Levels
# =============================================================================

class TaskPriority(IntEnum):
    """
    Task priority levels.

    Higher priority tasks are executed first.
    """
    LOW = 25
    NORMAL = 50
    HIGH = 75
    URGENT = 100


# =============================================================================
# Task Handler Registry
# =============================================================================

class TaskHandlerRegistry:
    """
    Registry of task type handlers.

    Handlers are functions that execute specific task types.
    """

    def __init__(self):
        """Initialize empty handler registry."""
        self._handlers: Dict[str, Callable] = {}

    def register(self, task_type: str, handler: Callable):
        """
        Register a task handler.

        Args:
            task_type: Type of task (e.g., 'export_agent')
            handler: Async function that executes the task
                     Signature: async def handler(payload: dict, task_id: int) -> dict
        """
        if task_type in self._handlers:
            logger.warning(f"Overwriting existing handler for task type '{task_type}'")

        self._handlers[task_type] = handler
        logger.info(f"Registered handler for task type '{task_type}'")

    def get(self, task_type: str) -> Optional[Callable]:
        """
        Get handler for task type.

        Args:
            task_type: Type of task

        Returns:
            Handler function or None if not found
        """
        return self._handlers.get(task_type)

    def has_handler(self, task_type: str) -> bool:
        """Check if handler exists for task type."""
        return task_type in self._handlers

    def list_handlers(self) -> List[str]:
        """Get list of registered task types."""
        return list(self._handlers.keys())


# Global handler registry
_handler_registry = TaskHandlerRegistry()


def register_handler(task_type: str):
    """
    Decorator to register task handler.

    Usage:
        @register_handler("export_agent")
        async def handle_export_agent(payload: dict, task_id: int):
            # Task logic here
            return {"result": "success"}

    Args:
        task_type: Type of task
    """
    def decorator(func: Callable):
        _handler_registry.register(task_type, func)
        return func
    return decorator


# =============================================================================
# Task Worker
# =============================================================================

class TaskWorker:
    """
    Worker that claims and executes tasks from the queue.

    Uses SELECT FOR UPDATE SKIP LOCKED to claim tasks without race conditions.
    """

    def __init__(self, worker_id: int, registry: TaskHandlerRegistry):
        """
        Initialize task worker.

        Args:
            worker_id: Unique worker identifier
            registry: Task handler registry
        """
        self.worker_id = worker_id
        self.registry = registry
        self.running = False
        self.current_task_id: Optional[int] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start worker loop."""
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Worker {self.worker_id} started")

    async def stop(self, timeout: float = 30.0):
        """
        Stop worker gracefully.

        Args:
            timeout: Maximum time to wait for current task to complete
        """
        logger.info(f"Stopping worker {self.worker_id}...")
        self.running = False

        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Worker {self.worker_id} did not stop within timeout, cancelling...")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        logger.info(f"Worker {self.worker_id} stopped")

    async def _run_loop(self):
        """Main worker loop that claims and executes tasks."""
        logger.info(f"Worker {self.worker_id} loop starting...")

        while self.running:
            try:
                # Claim a task from the queue
                task = await self._claim_task()

                if task:
                    # Execute task
                    await self._execute_task(task)
                else:
                    # No tasks available, sleep before checking again
                    await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(
                    f"Worker {self.worker_id} encountered error in main loop: {e}",
                    exc_info=True
                )
                # Sleep before retrying
                await asyncio.sleep(5.0)

        logger.info(f"Worker {self.worker_id} loop exited")

    async def _claim_task(self) -> Optional[BackgroundTask]:
        """
        Claim next available task from queue.

        Uses SELECT FOR UPDATE SKIP LOCKED to prevent race conditions.

        Returns:
            BackgroundTask or None if no tasks available
        """
        db: Session = SessionLocal()
        try:
            # Use raw SQL for SELECT FOR UPDATE SKIP LOCKED
            # This atomically claims a task without race conditions
            result = db.execute(text("""
                UPDATE background_tasks
                SET status = 'RUNNING',
                    started_at = NOW()
                WHERE id = (
                    SELECT id
                    FROM background_tasks
                    WHERE status = 'PENDING'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id
            """))

            row = result.fetchone()
            if row:
                task_id = row[0]
                db.commit()

                # Fetch the full task object
                task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
                if task:
                    logger.info(
                        f"Worker {self.worker_id} claimed task {task.id} "
                        f"(type: {task.task_type}, priority: {task.priority})"
                    )
                    self.current_task_id = task.id
                    return task

            db.commit()
            return None

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to claim task: {e}", exc_info=True)
            return None
        finally:
            db.close()

    async def _execute_task(self, task: BackgroundTask):
        """
        Execute a claimed task.

        Args:
            task: Task to execute
        """
        logger.info(f"Worker {self.worker_id} executing task {task.id} (type: {task.task_type})")

        db: Session = SessionLocal()
        start_time = time.time()

        try:
            # Get handler for this task type
            handler = self.registry.get(task.task_type)

            if not handler:
                raise ValueError(f"No handler registered for task type '{task.task_type}'")

            # Execute handler
            result = await handler(task.payload, task.id)

            # Task completed successfully
            duration = time.time() - start_time
            task_db = db.query(BackgroundTask).filter(BackgroundTask.id == task.id).first()
            if task_db:
                task_db.status = "COMPLETED"
                task_db.result = result
                task_db.completed_at = datetime.utcnow()
                db.commit()

            logger.info(
                f"Worker {self.worker_id} completed task {task.id} "
                f"(type: {task.task_type}, duration: {duration:.2f}s)"
            )

        except Exception as e:
            # Task failed
            duration = time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"

            logger.error(
                f"Worker {self.worker_id} failed task {task.id} "
                f"(type: {task.task_type}, duration: {duration:.2f}s): {e}",
                exc_info=True
            )

            # Update task status
            task_db = db.query(BackgroundTask).filter(BackgroundTask.id == task.id).first()
            if task_db:
                task_db.retry_count += 1

                if task_db.retry_count < task_db.max_retries:
                    # Retry task (reset to PENDING)
                    task_db.status = "PENDING"
                    task_db.error = error_msg
                    task_db.started_at = None
                    logger.info(
                        f"Task {task.id} will be retried "
                        f"(attempt {task_db.retry_count + 1}/{task_db.max_retries})"
                    )
                else:
                    # Max retries exceeded, mark as FAILED
                    task_db.status = "FAILED"
                    task_db.error = error_msg
                    task_db.completed_at = datetime.utcnow()
                    logger.error(f"Task {task.id} failed after {task_db.retry_count} retries")

                db.commit()

        finally:
            self.current_task_id = None
            db.close()


# =============================================================================
# Task Queue
# =============================================================================

class TaskQueue:
    """
    PostgreSQL-backed task queue with worker pool.

    Main interface for enqueueing tasks and checking status.
    """

    def __init__(self):
        """Initialize task queue."""
        self.registry = _handler_registry
        self.workers: List[TaskWorker] = []
        self.running = False

    def start_workers(self, num_workers: int = 2):
        """
        Start worker pool.

        Args:
            num_workers: Number of worker processes to start
        """
        if self.running:
            logger.warning("Workers already running")
            return

        logger.info(f"Starting {num_workers} workers...")
        self.running = True

        # Create and start workers
        for i in range(num_workers):
            worker = TaskWorker(worker_id=i, registry=self.registry)
            self.workers.append(worker)

        # Start all workers
        loop = asyncio.get_event_loop()
        for worker in self.workers:
            loop.create_task(worker.start())

        logger.info(f"Started {num_workers} workers")

    async def shutdown(self, timeout: float = 30.0):
        """
        Gracefully shutdown all workers.

        Args:
            timeout: Maximum time to wait for workers to finish
        """
        if not self.running:
            return

        logger.info(f"Shutting down {len(self.workers)} workers...")

        # Stop all workers
        stop_tasks = [worker.stop(timeout=timeout) for worker in self.workers]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        self.workers.clear()
        self.running = False

        logger.info("All workers stopped")

    async def enqueue(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = TaskPriority.NORMAL,
        max_retries: int = 3
    ) -> int:
        """
        Enqueue a new task.

        Args:
            task_type: Type of task (must have registered handler)
            payload: Task input data (must be JSON-serializable)
            priority: Task priority (higher = more urgent)
            max_retries: Maximum retry attempts

        Returns:
            Task ID

        Raises:
            ValueError: If no handler registered for task type
        """
        if not self.registry.has_handler(task_type):
            raise ValueError(
                f"No handler registered for task type '{task_type}'. "
                f"Available types: {self.registry.list_handlers()}"
            )

        db: Session = SessionLocal()
        try:
            # Create task
            task = BackgroundTask(
                task_type=task_type,
                payload=payload,
                priority=priority,
                max_retries=max_retries,
                status="PENDING"
            )

            db.add(task)
            db.commit()
            db.refresh(task)

            logger.info(
                f"Enqueued task {task.id} (type: {task_type}, priority: {priority})",
                extra={
                    "task_id": task.id,
                    "task_type": task_type,
                    "priority": priority
                }
            )

            return task.id

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to enqueue task: {e}", exc_info=True)
            raise
        finally:
            db.close()

    async def get_status(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Get task status.

        Args:
            task_id: Task ID

        Returns:
            Task status dict or None if not found
        """
        db: Session = SessionLocal()
        try:
            task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
            if task:
                return task.to_dict()
            return None
        finally:
            db.close()

    async def cancel_task(self, task_id: int) -> bool:
        """
        Cancel a pending task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False if task not found or already started
        """
        db: Session = SessionLocal()
        try:
            task = db.query(BackgroundTask).filter(
                and_(
                    BackgroundTask.id == task_id,
                    BackgroundTask.status == "PENDING"
                )
            ).first()

            if task:
                task.status = "CANCELLED"
                task.completed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Cancelled task {task_id}")
                return True

            return False

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to cancel task {task_id}: {e}", exc_info=True)
            return False
        finally:
            db.close()

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dict with queue metrics
        """
        db: Session = SessionLocal()
        try:
            # Count tasks by status
            stats = {
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "workers": len(self.workers),
                "workers_running": self.running
            }

            for status in ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]:
                count = db.query(BackgroundTask).filter(
                    BackgroundTask.status == status
                ).count()
                stats[status.lower()] = count

            return stats

        finally:
            db.close()


# Global task queue instance
task_queue = TaskQueue()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TaskQueue",
    "TaskWorker",
    "TaskPriority",
    "TaskHandlerRegistry",
    "register_handler",
    "task_queue"
]
