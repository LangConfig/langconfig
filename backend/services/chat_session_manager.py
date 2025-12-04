# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Chat Session Manager

Handles lifecycle management for chat sessions including:
- Agent instance caching with TTL
- Automatic cleanup of abandoned sessions
- Checkpoint cleanup on session end
- Session health monitoring
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from models.deep_agent import ChatSession

logger = logging.getLogger(__name__)


class SessionMetadata:
    """Metadata for cached agent sessions."""

    def __init__(self, agent_instance: Any, session_id: str):
        self.agent_instance = agent_instance
        self.session_id = session_id
        self.last_accessed = datetime.utcnow()
        self.created_at = datetime.utcnow()
        self.message_count = 0

    def touch(self):
        """Update last accessed time."""
        self.last_accessed = datetime.utcnow()

    def is_stale(self, ttl_seconds: int = 3600) -> bool:
        """Check if session is stale (inactive for > ttl_seconds)."""
        return (datetime.utcnow() - self.last_accessed).total_seconds() > ttl_seconds


class ChatSessionManager:
    """
    Manages chat session lifecycle and agent instance caching.

    Features:
    - TTL-based cleanup of inactive sessions
    - Agent instance caching for performance
    - Memory leak prevention
    - Session health monitoring
    """

    def __init__(self, ttl_seconds: int = 3600, cleanup_interval: int = 300):
        """
        Initialize session manager.

        Args:
            ttl_seconds: Time-to-live for inactive sessions (default: 1 hour)
            cleanup_interval: How often to run cleanup (default: 5 minutes)
        """
        self.active_sessions: Dict[str, SessionMetadata] = {}
        self.ttl_seconds = ttl_seconds
        self.cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False

        logger.info(f"ChatSessionManager initialized (TTL: {ttl_seconds}s, cleanup: {cleanup_interval}s)")

    def get_agent(self, session_id: str) -> Optional[Any]:
        """
        Get cached agent instance for a session.

        Args:
            session_id: Session ID

        Returns:
            Agent instance if cached, None otherwise
        """
        metadata = self.active_sessions.get(session_id)
        if metadata:
            metadata.touch()
            return metadata.agent_instance
        return None

    def cache_agent(self, session_id: str, agent_instance: Any):
        """
        Cache an agent instance for a session.

        Args:
            session_id: Session ID
            agent_instance: Agent instance to cache
        """
        if session_id in self.active_sessions:
            # Update existing
            self.active_sessions[session_id].agent_instance = agent_instance
            self.active_sessions[session_id].touch()
        else:
            # Create new
            self.active_sessions[session_id] = SessionMetadata(agent_instance, session_id)

        logger.debug(f"Cached agent for session {session_id} (total: {len(self.active_sessions)})")

    def remove_session(self, session_id: str) -> bool:
        """
        Remove a session from cache.

        Args:
            session_id: Session ID to remove

        Returns:
            True if session was removed, False if not found
        """
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            logger.info(f"Removed session {session_id} from cache (remaining: {len(self.active_sessions)})")
            return True
        return False

    async def cleanup_stale_sessions(self) -> int:
        """
        Remove stale sessions from cache.

        Returns:
            Number of sessions cleaned up
        """
        stale_sessions = [
            session_id
            for session_id, metadata in self.active_sessions.items()
            if metadata.is_stale(self.ttl_seconds)
        ]

        for session_id in stale_sessions:
            metadata = self.active_sessions[session_id]
            inactive_time = (datetime.utcnow() - metadata.last_accessed).total_seconds()
            logger.info(
                f"Cleaning up stale session {session_id} "
                f"(inactive for {inactive_time:.0f}s, created {metadata.created_at})"
            )
            del self.active_sessions[session_id]

        if stale_sessions:
            logger.info(f"Cleaned up {len(stale_sessions)} stale sessions (remaining: {len(self.active_sessions)})")

        return len(stale_sessions)

    async def _cleanup_loop(self):
        """Background task to periodically clean up stale sessions."""
        logger.info(f"Starting session cleanup loop (interval: {self.cleanup_interval}s)")

        while self._is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                cleaned = await self.cleanup_stale_sessions()

                # Log statistics
                if len(self.active_sessions) > 0:
                    logger.debug(f"Active sessions: {len(self.active_sessions)}")

            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                # Continue running even if cleanup fails

    async def start(self):
        """Start the background cleanup task."""
        if self._is_running:
            logger.warning("Session manager already running")
            return

        self._is_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session manager started")

    async def stop(self):
        """Stop the background cleanup task."""
        if not self._is_running:
            return

        self._is_running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info(f"Session manager stopped (cleaned up {len(self.active_sessions)} remaining sessions)")
        self.active_sessions.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get session manager statistics.

        Returns:
            Dictionary with stats
        """
        now = datetime.utcnow()

        active_count = len(self.active_sessions)
        stale_count = sum(
            1 for metadata in self.active_sessions.values()
            if metadata.is_stale(self.ttl_seconds)
        )

        # Calculate average session age
        if active_count > 0:
            total_age = sum(
                (now - metadata.created_at).total_seconds()
                for metadata in self.active_sessions.values()
            )
            avg_age = total_age / active_count
        else:
            avg_age = 0

        return {
            "active_sessions": active_count,
            "stale_sessions": stale_count,
            "avg_session_age_seconds": avg_age,
            "ttl_seconds": self.ttl_seconds,
            "is_running": self._is_running
        }


# Global session manager instance
_session_manager: Optional[ChatSessionManager] = None


def get_session_manager() -> ChatSessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = ChatSessionManager(
            ttl_seconds=3600,  # 1 hour
            cleanup_interval=300  # 5 minutes
        )
    return _session_manager


async def start_session_manager():
    """Start the global session manager."""
    manager = get_session_manager()
    await manager.start()


async def stop_session_manager():
    """Stop the global session manager."""
    global _session_manager
    if _session_manager:
        await _session_manager.stop()
        _session_manager = None
