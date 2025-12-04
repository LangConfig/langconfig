# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Cancellation Registry

Provides a global registry for tracking and cancelling running workflows.
Uses asyncio Events to coordinate cancellation between API endpoints and executor.
"""
import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CancellationRegistry:
    """
    Global registry for managing workflow cancellation requests.

    Thread-safe registry that uses asyncio.Event for cancellation signaling.
    """

    def __init__(self):
        self._cancellation_events: Dict[int, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def register_task(self, task_id: int) -> asyncio.Event:
        """
        Register a task for potential cancellation.

        Args:
            task_id: Task ID to register

        Returns:
            asyncio.Event that will be set when cancellation is requested
        """
        async with self._lock:
            if task_id not in self._cancellation_events:
                self._cancellation_events[task_id] = asyncio.Event()
                logger.info(f"Registered task {task_id} for cancellation tracking")
            return self._cancellation_events[task_id]

    async def request_cancellation(self, task_id: int) -> bool:
        """
        Request cancellation of a running task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancellation was requested, False if task not found
        """
        async with self._lock:
            if task_id in self._cancellation_events:
                self._cancellation_events[task_id].set()
                logger.info(f"Cancellation requested for task {task_id}")
                return True
            else:
                logger.warning(f"Cannot cancel task {task_id} - not in registry")
                return False

    async def is_cancelled(self, task_id: int) -> bool:
        """
        Check if a task has been cancelled.

        Args:
            task_id: Task ID to check

        Returns:
            True if task has been cancelled
        """
        async with self._lock:
            if task_id in self._cancellation_events:
                return self._cancellation_events[task_id].is_set()
            return False

    async def unregister_task(self, task_id: int):
        """
        Unregister a completed or cancelled task.

        Args:
            task_id: Task ID to unregister
        """
        async with self._lock:
            if task_id in self._cancellation_events:
                del self._cancellation_events[task_id]
                logger.info(f"Unregistered task {task_id} from cancellation tracking")

    def get_active_task_count(self) -> int:
        """Get the number of currently tracked tasks."""
        return len(self._cancellation_events)


# Global singleton instance
_cancellation_registry: Optional[CancellationRegistry] = None


def get_cancellation_registry() -> CancellationRegistry:
    """
    Get the global cancellation registry instance.

    Returns:
        CancellationRegistry singleton
    """
    global _cancellation_registry
    if _cancellation_registry is None:
        _cancellation_registry = CancellationRegistry()
        logger.info("Initialized global cancellation registry")
    return _cancellation_registry
