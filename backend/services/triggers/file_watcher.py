# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
File Watcher Trigger Service

Monitors local directories for file changes and triggers workflow executions.
Uses the watchdog library for cross-platform file system monitoring.

Features:
- Pattern-based file matching (glob patterns)
- Debouncing to prevent rapid re-triggers
- Configurable event types (created, modified, deleted, moved)
- Automatic cleanup on shutdown
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, Optional, Any
from threading import Thread

logger = logging.getLogger(__name__)

# Track last trigger times for debouncing
_last_trigger_times: Dict[str, datetime] = {}
_debounce_check_counter: int = 0
_DEBOUNCE_CLEANUP_INTERVAL = 100  # Clean up every N calls
_DEBOUNCE_MAX_SIZE = 1000  # Force cleanup if dict exceeds this size
_DEBOUNCE_STALE_SECONDS = 600  # Remove entries older than 10 minutes


def _cleanup_stale_debounce_entries() -> None:
    """Remove debounce entries older than 10 minutes to prevent memory leaks."""
    global _last_trigger_times
    now = datetime.now(timezone.utc)
    stale_keys = [
        key for key, last_time in _last_trigger_times.items()
        if (now - last_time).total_seconds() > _DEBOUNCE_STALE_SECONDS
    ]
    for key in stale_keys:
        del _last_trigger_times[key]
    if stale_keys:
        logger.debug(f"Cleaned up {len(stale_keys)} stale debounce entries")


class FileWatchHandler:
    """
    Handles file system events for a specific trigger.

    Filters events based on trigger config (patterns, event types)
    and triggers workflow execution with debouncing.
    """

    def __init__(self, trigger_id: int, workflow_id: int, config: dict):
        self.trigger_id = trigger_id
        self.workflow_id = workflow_id
        self.config = config
        self.patterns = config.get("patterns", ["*"])
        self.events = config.get("events", ["created"])
        self.debounce_seconds = config.get("debounce_seconds", 5)
        self.input_mapping = config.get("input_mapping", {})

    def matches_pattern(self, file_path: str) -> bool:
        """Check if file matches any configured patterns."""
        file_name = os.path.basename(file_path)
        return any(fnmatch(file_name, pattern) for pattern in self.patterns)

    def should_trigger(self, event_type: str, file_path: str) -> bool:
        """Determine if this event should trigger the workflow."""
        global _debounce_check_counter

        # Periodically clean up stale debounce entries
        _debounce_check_counter += 1
        if _debounce_check_counter >= _DEBOUNCE_CLEANUP_INTERVAL or len(_last_trigger_times) > _DEBOUNCE_MAX_SIZE:
            _debounce_check_counter = 0
            _cleanup_stale_debounce_entries()

        # Check event type
        if event_type not in self.events:
            return False

        # Check pattern match
        if not self.matches_pattern(file_path):
            return False

        # Check debounce
        debounce_key = f"{self.trigger_id}:{file_path}"
        now = datetime.now(timezone.utc)
        last_trigger = _last_trigger_times.get(debounce_key)

        if last_trigger:
            elapsed = (now - last_trigger).total_seconds()
            if elapsed < self.debounce_seconds:
                logger.debug(
                    f"Debounced trigger for {file_path} "
                    f"(elapsed: {elapsed:.1f}s < {self.debounce_seconds}s)"
                )
                return False

        _last_trigger_times[debounce_key] = now
        return True

    def build_input_data(self, event_type: str, file_path: str) -> dict:
        """Build workflow input data from the file event."""
        file_path_obj = Path(file_path)

        # Available template variables
        variables = {
            "file_path": str(file_path),
            "file_name": file_path_obj.name,
            "file_stem": file_path_obj.stem,
            "file_ext": file_path_obj.suffix,
            "dir_path": str(file_path_obj.parent),
            "event_type": event_type,
        }

        # Build input data from mapping
        input_data = {}

        if self.input_mapping:
            for key, template in self.input_mapping.items():
                # Replace template variables
                value = template
                for var_name, var_value in variables.items():
                    value = value.replace(f"{{{var_name}}}", str(var_value))

                # Handle nested keys (e.g., "context.file_path")
                parts = key.split(".")
                target = input_data
                for part in parts[:-1]:
                    if part not in target:
                        target[part] = {}
                    target = target[part]
                target[parts[-1]] = value
        else:
            # Default input structure
            input_data = {
                "task": f"Process file: {file_path_obj.name}",
                "context": variables,
            }

        return input_data


class FileWatcherService:
    """
    Manages file system watchers for all file_watch triggers.

    Loads enabled triggers from database and starts observers
    for each configured watch path.
    """

    def __init__(self):
        self.observers: Dict[int, Any] = {}  # trigger_id -> Observer
        self.handlers: Dict[int, FileWatchHandler] = {}
        self._is_running = False
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        logger.info("FileWatcherService initialized")

    async def start(self):
        """Start all file watchers for enabled triggers."""
        if self._is_running:
            logger.warning("File watcher service already running")
            return

        self._is_running = True
        self._event_loop = asyncio.get_event_loop()

        # Load and start watchers for all enabled file_watch triggers
        await self._load_and_start_watchers()

        logger.info("File watcher service started")

    async def stop(self):
        """Stop all file watchers."""
        if not self._is_running:
            return

        self._is_running = False

        # Stop all observers
        for trigger_id, observer in list(self.observers.items()):
            try:
                observer.stop()
                observer.join(timeout=5)
                logger.debug(f"Stopped file watcher for trigger {trigger_id}")
            except Exception as e:
                logger.error(f"Error stopping watcher for trigger {trigger_id}: {e}")

        self.observers.clear()
        self.handlers.clear()

        logger.info("File watcher service stopped")

    async def _load_and_start_watchers(self):
        """Load enabled file_watch triggers and start observers."""
        from db.database import SessionLocal
        from models.workflow_trigger import WorkflowTrigger, TriggerType

        db = SessionLocal()
        try:
            triggers = db.query(WorkflowTrigger).filter(
                WorkflowTrigger.trigger_type == TriggerType.FILE_WATCH.value,
                WorkflowTrigger.enabled == True
            ).all()

            logger.info(f"Found {len(triggers)} enabled file watch trigger(s)")

            for trigger in triggers:
                await self.start_watcher(trigger.id, trigger.workflow_id, trigger.config)

        except Exception as e:
            logger.error(f"Error loading file watch triggers: {e}", exc_info=True)
        finally:
            db.close()

    async def start_watcher(self, trigger_id: int, workflow_id: int, config: dict):
        """Start a file watcher for a specific trigger."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            watch_path = config.get("watch_path")
            if not watch_path:
                logger.error(f"Trigger {trigger_id}: No watch_path configured")
                return

            # Verify path exists
            if not os.path.exists(watch_path):
                logger.warning(f"Trigger {trigger_id}: Watch path does not exist: {watch_path}")
                # Try to create it
                try:
                    os.makedirs(watch_path, exist_ok=True)
                    logger.info(f"Created watch directory: {watch_path}")
                except Exception as e:
                    logger.error(f"Could not create watch directory: {e}")
                    return

            # Create handler
            handler = FileWatchHandler(trigger_id, workflow_id, config)
            self.handlers[trigger_id] = handler

            # Create watchdog event handler wrapper
            service = self

            class WatchdogHandler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory:
                        service._handle_event("created", event.src_path, handler)

                def on_modified(self, event):
                    if not event.is_directory:
                        service._handle_event("modified", event.src_path, handler)

                def on_deleted(self, event):
                    if not event.is_directory:
                        service._handle_event("deleted", event.src_path, handler)

                def on_moved(self, event):
                    if not event.is_directory:
                        service._handle_event("moved", event.dest_path, handler)

            # Create and start observer
            observer = Observer()
            observer.schedule(
                WatchdogHandler(),
                watch_path,
                recursive=config.get("recursive", False)
            )
            observer.start()

            self.observers[trigger_id] = observer

            logger.info(
                f"Started file watcher for trigger {trigger_id}: "
                f"path={watch_path}, patterns={handler.patterns}, events={handler.events}"
            )

        except ImportError:
            logger.error(
                "watchdog package not installed. "
                "Install with: pip install watchdog"
            )
        except Exception as e:
            logger.error(f"Error starting file watcher for trigger {trigger_id}: {e}", exc_info=True)

    async def stop_watcher(self, trigger_id: int):
        """Stop a specific file watcher."""
        if trigger_id in self.observers:
            try:
                observer = self.observers[trigger_id]
                observer.stop()
                observer.join(timeout=5)
                del self.observers[trigger_id]
                logger.info(f"Stopped file watcher for trigger {trigger_id}")
            except Exception as e:
                logger.error(f"Error stopping watcher for trigger {trigger_id}: {e}")

        if trigger_id in self.handlers:
            del self.handlers[trigger_id]

    def _handle_event(self, event_type: str, file_path: str, handler: FileWatchHandler):
        """Handle a file system event."""
        if not handler.should_trigger(event_type, file_path):
            return

        logger.info(
            f"File trigger {handler.trigger_id} activated: "
            f"{event_type} {file_path}"
        )

        # Build input data
        input_data = handler.build_input_data(event_type, file_path)

        # Schedule the async trigger in the event loop
        if self._event_loop and self._is_running:
            asyncio.run_coroutine_threadsafe(
                self._trigger_workflow(handler, file_path, input_data),
                self._event_loop
            )

    async def _trigger_workflow(
        self,
        handler: FileWatchHandler,
        file_path: str,
        input_data: dict
    ):
        """Trigger workflow execution via task queue."""
        from db.database import SessionLocal
        from models.workflow_trigger import WorkflowTrigger, TriggerLog, TriggerStatus
        from core.task_queue import task_queue, TaskPriority
        from datetime import datetime, timezone

        db = SessionLocal()
        try:
            # Update trigger stats
            trigger = db.query(WorkflowTrigger).filter(
                WorkflowTrigger.id == handler.trigger_id
            ).first()

            if not trigger:
                logger.warning(f"Trigger {handler.trigger_id} not found")
                return

            # Create trigger log
            trigger_log = TriggerLog(
                trigger_id=handler.trigger_id,
                triggered_at=datetime.now(timezone.utc),
                status=TriggerStatus.PENDING.value,
                trigger_source=file_path,
                trigger_payload={"file_path": file_path, "input_data": input_data}
            )
            db.add(trigger_log)
            db.flush()

            # Enqueue the workflow execution
            task_id = await task_queue.enqueue(
                "execute_triggered_workflow",
                {
                    "trigger_id": handler.trigger_id,
                    "trigger_log_id": trigger_log.id,
                    "workflow_id": handler.workflow_id,
                    "trigger_type": "file_watch",
                    "input_data": input_data,
                    "trigger_source": file_path,
                },
                priority=TaskPriority.NORMAL
            )

            # Update trigger log with task ID
            trigger_log.task_id = task_id

            # Update trigger stats
            trigger.last_triggered_at = datetime.now(timezone.utc)
            trigger.trigger_count = (trigger.trigger_count or 0) + 1

            db.commit()

            logger.info(
                f"Triggered workflow {handler.workflow_id} from file watch "
                f"(trigger: {handler.trigger_id}, task: {task_id})"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"Error triggering workflow: {e}", exc_info=True)
        finally:
            db.close()

    async def reload_trigger(self, trigger_id: int):
        """Reload a trigger (stop and restart with new config)."""
        from db.database import SessionLocal
        from models.workflow_trigger import WorkflowTrigger

        # Stop existing watcher
        await self.stop_watcher(trigger_id)

        # Load trigger from database
        db = SessionLocal()
        try:
            trigger = db.query(WorkflowTrigger).filter(
                WorkflowTrigger.id == trigger_id
            ).first()

            if trigger and trigger.enabled:
                await self.start_watcher(trigger.id, trigger.workflow_id, trigger.config)
        finally:
            db.close()

    def get_stats(self) -> dict:
        """Get file watcher statistics."""
        return {
            "is_running": self._is_running,
            "active_watchers": len(self.observers),
            "trigger_ids": list(self.observers.keys()),
        }


# Global file watcher instance
_file_watcher: Optional[FileWatcherService] = None


def get_file_watcher() -> FileWatcherService:
    """Get the global file watcher instance."""
    global _file_watcher
    if _file_watcher is None:
        _file_watcher = FileWatcherService()
    return _file_watcher


async def start_file_watchers():
    """Start the global file watcher service."""
    watcher = get_file_watcher()
    await watcher.start()


async def stop_file_watchers():
    """Stop the global file watcher service."""
    global _file_watcher
    if _file_watcher:
        await _file_watcher.stop()
        _file_watcher = None
