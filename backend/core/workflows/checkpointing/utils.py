# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Utility functions for managing LangGraph checkpoints and workflow recovery.

This module provides tools for:
- Inspecting checkpoint state
- Resuming interrupted workflows
- Recovering from crashes
- Managing HITL workflows
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db import engine, get_db
from .manager import get_checkpointer
from ..state import WorkflowState, WorkflowStatus
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver as PostgresSaver

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manager for workflow checkpoint operations."""

    def __init__(self):
        self.checkpointer = None

    async def initialize(self):
        """Initialize the checkpoint manager."""
        try:
            self.checkpointer = get_checkpointer()
            logger.info("CheckpointManager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize CheckpointManager: {e}")
            raise

    async def get_workflow_state(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[WorkflowState]:
        """
        Retrieve the workflow state from a checkpoint.

        Args:
            thread_id: The workflow thread ID (typically f"task_{task_id}")
            checkpoint_id: Optional specific checkpoint ID, defaults to latest

        Returns:
            WorkflowState dictionary or None if not found
        """
        try:
            async with engine.begin() as conn:
                if checkpoint_id:
                    # Get specific checkpoint
                    result = await conn.execute(text("""
                        SELECT checkpoint, metadata, created_at
                        FROM checkpoints
                        WHERE checkpoint_namespace = 'langconfig_workflows'
                        AND checkpoint_id = :checkpoint_id
                    """), {"checkpoint_id": checkpoint_id})
                else:
                    # Get latest checkpoint for this thread
                    result = await conn.execute(text("""
                        SELECT checkpoint, metadata, created_at
                        FROM checkpoints
                        WHERE checkpoint_namespace = 'langconfig_workflows'
                        AND checkpoint_id LIKE :thread_pattern
                        ORDER BY created_at DESC
                        LIMIT 1
                    """), {"thread_pattern": f"{thread_id}%"})

                row = result.fetchone()
                if row:
                    checkpoint_data = row[0]  # JSONB column
                    metadata = row[1]
                    created_at = row[2]

                    logger.info(f"Retrieved checkpoint for thread {thread_id} from {created_at}")

                    # Extract the actual state from the checkpoint structure
                    # LangGraph checkpoint format: {"channel_values": {...}, "channel_versions": {...}}
                    if isinstance(checkpoint_data, dict):
                        state = checkpoint_data.get("channel_values", {})
                        return state

                    return checkpoint_data
                else:
                    logger.debug(f"No checkpoint found for thread {thread_id}")
                    return None

        except Exception as e:
            logger.error(f"Failed to retrieve workflow state for {thread_id}: {e}")
            return None

    async def list_checkpoints(
        self,
        thread_id: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List checkpoints matching the given criteria.

        Args:
            thread_id: Optional filter by thread ID
            status: Optional filter by workflow status
            limit: Maximum number of results

        Returns:
            List of checkpoint summaries
        """
        try:
            async with engine.begin() as conn:
                query = """
                    SELECT
                        checkpoint_id,
                        checkpoint->'channel_values'->>'task_id' as task_id,
                        checkpoint->'channel_values'->>'workflow_status' as workflow_status,
                        checkpoint->'channel_values'->>'current_step' as current_step,
                        checkpoint->'channel_values'->>'retry_count' as retry_count,
                        created_at,
                        metadata
                    FROM checkpoints
                    WHERE checkpoint_namespace = 'langconfig_workflows'
                """

                params = {}

                if thread_id:
                    query += " AND checkpoint_id LIKE :thread_pattern"
                    params["thread_pattern"] = f"{thread_id}%"

                if status:
                    query += " AND checkpoint->'channel_values'->>'workflow_status' = :status"
                    params["status"] = status.value

                query += " ORDER BY created_at DESC LIMIT :limit"
                params["limit"] = limit

                result = await conn.execute(text(query), params)
                rows = result.fetchall()

                checkpoints = []
                for row in rows:
                    checkpoints.append({
                        "checkpoint_id": row[0],
                        "task_id": row[1],
                        "workflow_status": row[2],
                        "current_step": row[3],
                        "retry_count": row[4],
                        "created_at": row[5].isoformat() if row[5] else None,
                        "metadata": row[6]
                    })

                logger.info(f"Found {len(checkpoints)} checkpoints")
                return checkpoints

        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
            return []

    async def get_hitl_pending_workflows(self) -> List[Dict[str, Any]]:
        """
        Find all workflows awaiting Human-in-the-Loop intervention.

        Returns:
            List of workflows in AWAITING_HITL or HITL_REVIEWING status
        """
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT DISTINCT ON (checkpoint_id)
                        checkpoint_id,
                        checkpoint->'channel_values'->>'task_id' as task_id,
                        checkpoint->'channel_values'->>'workflow_status' as workflow_status,
                        checkpoint->'channel_values'->>'hitl_reason' as hitl_reason,
                        checkpoint->'channel_values'->>'execution_plan' as execution_plan,
                        created_at
                    FROM checkpoints
                    WHERE checkpoint_namespace = 'langconfig_workflows'
                    AND checkpoint->'channel_values'->>'workflow_status' IN ('AWAITING_HITL', 'HITL_REVIEWING')
                    ORDER BY checkpoint_id, created_at DESC
                """))

                rows = result.fetchall()

                hitl_workflows = []
                for row in rows:
                    hitl_workflows.append({
                        "checkpoint_id": row[0],
                        "task_id": int(row[1]) if row[1] else None,
                        "workflow_status": row[2],
                        "hitl_reason": row[3],
                        "execution_plan": row[4],
                        "created_at": row[5].isoformat() if row[5] else None
                    })

                logger.info(f"Found {len(hitl_workflows)} workflows awaiting HITL")
                return hitl_workflows

        except Exception as e:
            logger.error(f"Failed to retrieve HITL pending workflows: {e}")
            return []

    async def get_failed_workflows(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Find workflows that failed within the specified time window.

        Args:
            hours: Look back this many hours

        Returns:
            List of failed workflows
        """
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT DISTINCT ON (checkpoint_id)
                        checkpoint_id,
                        checkpoint->'channel_values'->>'task_id' as task_id,
                        checkpoint->'channel_values'->>'workflow_status' as workflow_status,
                        checkpoint->'channel_values'->>'error_message' as error_message,
                        checkpoint->'channel_values'->>'retry_count' as retry_count,
                        checkpoint->'channel_values'->>'current_step' as current_step,
                        created_at
                    FROM checkpoints
                    WHERE checkpoint_namespace = 'langconfig_workflows'
                    AND checkpoint->'channel_values'->>'workflow_status' IN
                        ('FAILED_EXECUTION', 'FAILED_VALIDATION', 'TERMINATED')
                    AND created_at > NOW() - INTERVAL ':hours hours'
                    ORDER BY checkpoint_id, created_at DESC
                """), {"hours": hours})

                rows = result.fetchall()

                failed_workflows = []
                for row in rows:
                    failed_workflows.append({
                        "checkpoint_id": row[0],
                        "task_id": int(row[1]) if row[1] else None,
                        "workflow_status": row[2],
                        "error_message": row[3],
                        "retry_count": int(row[4]) if row[4] else 0,
                        "current_step": row[5],
                        "created_at": row[6].isoformat() if row[6] else None
                    })

                logger.info(f"Found {len(failed_workflows)} failed workflows in last {hours} hours")
                return failed_workflows

        except Exception as e:
            logger.error(f"Failed to retrieve failed workflows: {e}")
            return []

    async def delete_checkpoint(
        self,
        checkpoint_id: str
    ) -> bool:
        """
        Delete a specific checkpoint.

        Args:
            checkpoint_id: The checkpoint ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    DELETE FROM checkpoints
                    WHERE checkpoint_namespace = 'langconfig_workflows'
                    AND checkpoint_id = :checkpoint_id
                    RETURNING checkpoint_id
                """), {"checkpoint_id": checkpoint_id})

                deleted = result.fetchone()
                if deleted:
                    logger.info(f"Deleted checkpoint {checkpoint_id}")
                    return True
                else:
                    logger.warning(f"Checkpoint {checkpoint_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            return False

    async def delete_thread_checkpoints(
        self,
        thread_id: str
    ) -> int:
        """
        Delete all checkpoints for a specific thread.

        Args:
            thread_id: The thread ID whose checkpoints to delete

        Returns:
            Number of checkpoints deleted
        """
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    DELETE FROM checkpoints
                    WHERE checkpoint_namespace = 'langconfig_workflows'
                    AND checkpoint_id LIKE :thread_pattern
                    RETURNING checkpoint_id
                """), {"thread_pattern": f"{thread_id}%"})

                deleted_rows = result.fetchall()
                count = len(deleted_rows)

                logger.info(f"Deleted {count} checkpoints for thread {thread_id}")
                return count

        except Exception as e:
            logger.error(f"Failed to delete checkpoints for thread {thread_id}: {e}")
            return 0

    async def get_checkpoint_count(self) -> Dict[str, int]:
        """
        Get statistics about checkpoints in the database.

        Returns:
            Dictionary with checkpoint counts by status
        """
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT
                        checkpoint->'channel_values'->>'workflow_status' as status,
                        COUNT(*) as count
                    FROM checkpoints
                    WHERE checkpoint_namespace = 'langconfig_workflows'
                    GROUP BY checkpoint->'channel_values'->>'workflow_status'
                """))

                rows = result.fetchall()

                stats = {
                    "total": sum(row[1] for row in rows),
                    "by_status": {row[0]: row[1] for row in rows if row[0]}
                }

                logger.debug(f"Checkpoint stats: {stats}")
                return stats

        except Exception as e:
            logger.error(f"Failed to get checkpoint count: {e}")
            return {"total": 0, "by_status": {}}


# Global checkpoint manager instance
_checkpoint_manager: Optional[CheckpointManager] = None


async def get_checkpoint_manager() -> CheckpointManager:
    """Get or create the global checkpoint manager instance."""
    global _checkpoint_manager

    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
        await _checkpoint_manager.initialize()

    return _checkpoint_manager


# Convenience functions for common operations
async def get_workflow_checkpoint(task_id: int) -> Optional[WorkflowState]:
    """
    Get the latest checkpoint for a specific task.

    Args:
        task_id: The task ID

    Returns:
        WorkflowState or None if not found
    """
    manager = await get_checkpoint_manager()
    thread_id = f"task_{task_id}"
    return await manager.get_workflow_state(thread_id)


async def list_pending_hitl_workflows() -> List[Dict[str, Any]]:
    """Get all workflows awaiting HITL intervention."""
    manager = await get_checkpoint_manager()
    return await manager.get_hitl_pending_workflows()


async def cleanup_completed_workflows(days_old: int = 7) -> int:
    """
    Clean up checkpoints for completed workflows older than specified days.

    Args:
        days_old: Delete checkpoints for workflows completed more than this many days ago

    Returns:
        Number of checkpoints deleted
    """
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                DELETE FROM checkpoints
                WHERE checkpoint_namespace = 'langconfig_workflows'
                AND checkpoint->'channel_values'->>'workflow_status' IN ('PASSED', 'TERMINATED')
                AND created_at < NOW() - INTERVAL ':days days'
                RETURNING checkpoint_id
            """), {"days": days_old})

            deleted_rows = result.fetchall()
            count = len(deleted_rows)

            logger.info(f"Cleaned up {count} completed workflow checkpoints older than {days_old} days")
            return count

    except Exception as e:
        logger.error(f"Failed to cleanup completed workflows: {e}")
        return 0


async def get_checkpoint_statistics() -> Dict[str, Any]:
    """
    Get comprehensive statistics about workflow checkpoints.

    Returns:
        Dictionary with various checkpoint statistics
    """
    manager = await get_checkpoint_manager()

    # Get basic counts
    counts = await manager.get_checkpoint_count()

    # Get HITL workflows
    hitl_workflows = await manager.get_hitl_pending_workflows()

    # Get recent failures
    recent_failures = await manager.get_failed_workflows(hours=24)

    return {
        "total_checkpoints": counts["total"],
        "by_status": counts["by_status"],
        "hitl_pending": len(hitl_workflows),
        "recent_failures_24h": len(recent_failures),
        "hitl_workflows": hitl_workflows,
        "recent_failures": recent_failures
    }
