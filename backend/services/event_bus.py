# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
In-memory event bus for desktop application.

Replaces Redis Pub/Sub with asyncio.Queue for single-process desktop apps.
Designed for LangConfig's Tauri desktop architecture with SSE streaming.

Usage:
    from services.event_bus import get_event_bus

    # Publish events
    event_bus = get_event_bus()
    await event_bus.publish("workflow:123", {
        "type": "node_started",
        "data": {"node_id": "embed_documents"}
    })

    # Subscribe to events (in SSE endpoint)
    queue = await event_bus.subscribe("workflow:123")
    while True:
        event = await queue.get()
        yield event
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class EventBus:
    """
    Lightweight in-memory event bus for single-process desktop application.

    Features:
    - Non-blocking publish (slow consumers get dropped events)
    - Automatic cleanup of disconnected subscribers
    - Statistics for monitoring
    - Thread-safe with asyncio locks
    """

    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._event_count = 0
        self._channel_sequences: Dict[str, int] = defaultdict(int)  # Per-channel sequence tracking

    async def subscribe(self, channel: str, maxsize: int = 500) -> asyncio.Queue:
        """
        Subscribe to channel. Returns queue for receiving events.

        Args:
            channel: Channel name (e.g., "workflow:123", "project:456:execution")
            maxsize: Max queue size (default 500, increased from 100 to reduce event drops)

        Returns:
            asyncio.Queue that will receive events published to this channel

        Example:
            queue = await event_bus.subscribe("workflow:123")
            while True:
                event = await queue.get()
                process(event)
        """
        async with self._lock:
            queue = asyncio.Queue(maxsize=maxsize)
            self._subscribers[channel].append(queue)
            logger.info(f"Subscribed to '{channel}' (total subscribers: {len(self._subscribers[channel])})")
            return queue

    async def unsubscribe(self, channel: str, queue: asyncio.Queue):
        """
        Unsubscribe from channel.

        Args:
            channel: Channel name
            queue: Queue returned from subscribe()
        """
        async with self._lock:
            if queue in self._subscribers[channel]:
                self._subscribers[channel].remove(queue)
                logger.info(f"Unsubscribed from '{channel}' (remaining: {len(self._subscribers[channel])})")

                # Clean up empty channel lists
                if not self._subscribers[channel]:
                    del self._subscribers[channel]

    async def publish(self, channel: str, event: Dict[str, Any]):
        """
        Publish event to all channel subscribers.

        Non-blocking - slow consumers with full queues will have events dropped.
        This prevents one slow subscriber from blocking the entire system.

        Args:
            channel: Channel name
            event: Event data (will be augmented with metadata)

        Example:
            await event_bus.publish("workflow:123", {
                "type": "node_started",
                "data": {"node_id": "analyze", "status": "running"}
            })
        """
        # Get copy of subscribers list (avoid holding lock during iteration)
        async with self._lock:
            subscribers = list(self._subscribers.get(channel, []))

        if not subscribers:
            # No subscribers, event is lost (expected for desktop app)
            return

        # Add metadata with sequence number for ordering and gap detection
        self._event_count += 1
        self._channel_sequences[channel] += 1
        event_with_metadata = {
            **event,
            "event_id": self._event_count,
            "sequence_number": self._channel_sequences[channel],  # Per-channel sequence for ordering
            "timestamp": datetime.utcnow().isoformat(),
            "channel": channel
        }

        # Publish to all subscribers (non-blocking)
        dropped_count = 0
        delivered_count = 0
        for queue in subscribers:
            try:
                queue.put_nowait(event_with_metadata)
                delivered_count += 1
                # Log stream events specifically
                if event.get('type') == 'on_chat_model_stream':
                    logger.info(f"[EVENT BUS] ✅ Delivered stream token to queue: {event.get('data', {}).get('agent_label')}")
            except asyncio.QueueFull:
                dropped_count += 1
                logger.warning(
                    f"Queue full for channel '{channel}', dropping event {self._event_count}. "
                    f"Slow consumer detected."
                )

        if dropped_count > 0:
            logger.warning(
                f"Dropped {dropped_count}/{len(subscribers)} events on channel '{channel}'. "
                f"Consider increasing queue size or improving consumer performance."
            )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get event bus statistics.

        Returns:
            Dictionary with statistics:
            - total_channels: Number of active channels
            - total_subscribers: Total number of subscribers across all channels
            - events_published: Total events published since start
            - channels: Per-channel subscriber counts
        """
        return {
            "total_channels": len(self._subscribers),
            "total_subscribers": sum(len(subs) for subs in self._subscribers.values()),
            "events_published": self._event_count,
            "channels": {
                channel: len(subs)
                for channel, subs in self._subscribers.items()
            }
        }

    async def clear_channel(self, channel: str):
        """
        Clear all subscribers from a channel.
        Useful for cleanup when workflow completes.

        Args:
            channel: Channel name to clear
        """
        async with self._lock:
            if channel in self._subscribers:
                count = len(self._subscribers[channel])
                del self._subscribers[channel]
                logger.info(f"Cleared {count} subscribers from channel '{channel}'")


# Global singleton instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    Get or create the global event bus instance.

    Returns:
        Global EventBus singleton

    Usage:
        from services.event_bus import get_event_bus

        event_bus = get_event_bus()
        await event_bus.publish("workflow:123", {...})
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
        logger.info("Initialized global event bus")
    return _event_bus


def reset_event_bus():
    """
    Reset the global event bus.

    Used for testing and cleanup. Not needed in normal operation.
    """
    global _event_bus
    _event_bus = None
    logger.info("Reset global event bus")
