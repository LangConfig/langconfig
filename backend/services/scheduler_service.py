# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Scheduler Service

Polling-based cron scheduler that checks for due workflow schedules
and enqueues them for execution via the background task queue.

Features:
- 30-second polling interval for schedule checks
- PostgreSQL-based locking (FOR UPDATE SKIP LOCKED) for distributed safety
- Idempotency key support to prevent duplicate executions
- Max concurrent runs enforcement
- Automatic next_run_at calculation using croniter
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text, and_

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Polling-based workflow scheduler.

    Periodically checks for due schedules and enqueues workflow executions
    via the background task queue.

    Features:
    - 30-second polling interval
    - Row-level locking for concurrency safety
    - Idempotency support
    - Concurrent run limiting
    """

    def __init__(self, poll_interval: int = 30):
        """
        Initialize scheduler service.

        Args:
            poll_interval: Seconds between schedule checks (default: 30)
        """
        self.poll_interval = poll_interval
        self._is_running = False
        self._poll_task: Optional[asyncio.Task] = None

        logger.info(f"SchedulerService initialized (poll interval: {poll_interval}s)")

    async def start(self):
        """Start the scheduler polling loop."""
        if self._is_running:
            logger.warning("Scheduler already running")
            return

        self._is_running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Scheduler service started")

    async def stop(self):
        """Stop the scheduler polling loop."""
        if not self._is_running:
            return

        self._is_running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        logger.info("Scheduler service stopped")

    async def _poll_loop(self):
        """Main polling loop that checks for due schedules."""
        logger.info(f"Starting scheduler poll loop (interval: {self.poll_interval}s)")

        while self._is_running:
            try:
                await self._process_due_schedules()
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("Scheduler poll loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler poll loop: {e}", exc_info=True)
                # Continue running even if processing fails
                await asyncio.sleep(self.poll_interval)

    async def _process_due_schedules(self):
        """Find and process all due schedules."""
        from db.database import SessionLocal
        from models.workflow_schedule import WorkflowSchedule, ScheduledRunLog, ScheduleRunStatus
        from core.task_queue import task_queue, TaskPriority

        db: Session = SessionLocal()
        try:
            # Find due schedules using FOR UPDATE SKIP LOCKED
            # This prevents race conditions in distributed setups
            result = db.execute(text("""
                SELECT id
                FROM workflow_schedules
                WHERE enabled = true
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= NOW()
                FOR UPDATE SKIP LOCKED
            """))

            schedule_ids = [row[0] for row in result.fetchall()]

            if not schedule_ids:
                return

            logger.info(f"Found {len(schedule_ids)} due schedule(s)")

            for schedule_id in schedule_ids:
                await self._process_schedule(db, schedule_id)

            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing due schedules: {e}", exc_info=True)
        finally:
            db.close()

    async def _process_schedule(self, db: Session, schedule_id: int):
        """
        Process a single due schedule.

        Args:
            db: Database session
            schedule_id: ID of the schedule to process
        """
        from models.workflow_schedule import WorkflowSchedule, ScheduledRunLog, ScheduleRunStatus
        from core.task_queue import task_queue, TaskPriority

        schedule = db.query(WorkflowSchedule).filter(
            WorkflowSchedule.id == schedule_id
        ).first()

        if not schedule:
            logger.warning(f"Schedule {schedule_id} not found during processing")
            return

        try:
            # Check concurrent run limit
            if not await self._can_run(db, schedule):
                logger.info(
                    f"Schedule {schedule_id} skipped: max concurrent runs reached "
                    f"({schedule.max_concurrent_runs})"
                )
                return

            # Generate idempotency key if template is set
            idempotency_key = None
            if schedule.idempotency_key_template:
                idempotency_key = self._generate_idempotency_key(
                    schedule.idempotency_key_template,
                    schedule.next_run_at
                )

                # Check if already run with this key
                existing = db.query(ScheduledRunLog).filter(
                    ScheduledRunLog.idempotency_key == idempotency_key
                ).first()

                if existing:
                    logger.info(
                        f"Schedule {schedule_id} skipped: idempotency key already exists "
                        f"(key: {idempotency_key})"
                    )
                    # Still update next_run_at
                    schedule.next_run_at = self._calculate_next_run(
                        schedule.cron_expression,
                        schedule.timezone
                    )
                    return

            # Create run log entry
            run_log = ScheduledRunLog(
                schedule_id=schedule.id,
                scheduled_for=schedule.next_run_at,
                status=ScheduleRunStatus.PENDING.value,
                idempotency_key=idempotency_key
            )
            db.add(run_log)
            db.flush()  # Get the run_log.id

            # Enqueue the task
            task_id = await task_queue.enqueue(
                "execute_scheduled_workflow",
                {
                    "schedule_id": schedule.id,
                    "run_log_id": run_log.id,
                    "workflow_id": schedule.workflow_id,
                    "input_data": schedule.default_input_data,
                    "timeout_minutes": schedule.timeout_minutes
                },
                priority=TaskPriority.NORMAL
            )

            # Update run log with task ID
            run_log.task_id = task_id

            # Update schedule tracking
            schedule.last_run_at = datetime.now(timezone.utc)
            schedule.next_run_at = self._calculate_next_run(
                schedule.cron_expression,
                schedule.timezone
            )

            logger.info(
                f"Scheduled workflow {schedule.workflow_id} enqueued "
                f"(schedule: {schedule_id}, task: {task_id}, next: {schedule.next_run_at})"
            )

        except Exception as e:
            logger.error(
                f"Error processing schedule {schedule_id}: {e}",
                exc_info=True
            )
            # Don't re-raise - let other schedules process

    async def _can_run(self, db: Session, schedule) -> bool:
        """
        Check if schedule can run based on max_concurrent_runs.

        Args:
            db: Database session
            schedule: WorkflowSchedule instance

        Returns:
            True if schedule can run, False if at limit
        """
        from models.workflow_schedule import ScheduledRunLog, ScheduleRunStatus

        # Count active runs for this schedule
        active_count = db.query(ScheduledRunLog).filter(
            and_(
                ScheduledRunLog.schedule_id == schedule.id,
                ScheduledRunLog.status.in_([
                    ScheduleRunStatus.PENDING.value,
                    ScheduleRunStatus.RUNNING.value
                ])
            )
        ).count()

        return active_count < schedule.max_concurrent_runs

    def _generate_idempotency_key(
        self,
        template: str,
        scheduled_for: datetime
    ) -> str:
        """
        Generate idempotency key from template.

        Supports placeholders:
        - {date}: YYYY-MM-DD
        - {datetime}: YYYY-MM-DD_HH-MM
        - {week}: YYYY-WNN
        - {month}: YYYY-MM

        Args:
            template: Key template with placeholders
            scheduled_for: Scheduled execution time

        Returns:
            Generated idempotency key
        """
        key = template

        # Date-based placeholders
        key = key.replace("{date}", scheduled_for.strftime("%Y-%m-%d"))
        key = key.replace("{datetime}", scheduled_for.strftime("%Y-%m-%d_%H-%M"))
        key = key.replace("{week}", scheduled_for.strftime("%Y-W%W"))
        key = key.replace("{month}", scheduled_for.strftime("%Y-%m"))

        return key

    def _calculate_next_run(self, cron_expression: str, tz: str) -> datetime:
        """
        Calculate next run time from cron expression.

        Args:
            cron_expression: Standard cron expression
            tz: Timezone name

        Returns:
            Next run datetime in UTC
        """
        try:
            from croniter import croniter
            import pytz

            # Get timezone
            timezone_obj = pytz.timezone(tz)

            # Get current time in the schedule's timezone
            now = datetime.now(timezone_obj)

            # Calculate next run
            cron = croniter(cron_expression, now)
            next_run_local = cron.get_next(datetime)

            # Convert to UTC for storage
            if next_run_local.tzinfo is None:
                next_run_local = timezone_obj.localize(next_run_local)

            next_run_utc = next_run_local.astimezone(pytz.UTC)

            return next_run_utc

        except Exception as e:
            logger.error(f"Error calculating next run: {e}", exc_info=True)
            # Default to 1 hour from now if calculation fails
            return datetime.now(timezone.utc).replace(
                minute=0, second=0, microsecond=0
            ) + timedelta(hours=1)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get scheduler statistics.

        Returns:
            Dictionary with scheduler stats
        """
        return {
            "is_running": self._is_running,
            "poll_interval": self.poll_interval
        }


# Avoid circular import for timedelta
from datetime import timedelta


# Global scheduler instance
_scheduler: Optional[SchedulerService] = None


def get_scheduler() -> SchedulerService:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService(poll_interval=30)
    return _scheduler


async def start_scheduler():
    """Start the global scheduler service."""
    scheduler = get_scheduler()
    await scheduler.start()


async def stop_scheduler():
    """Stop the global scheduler service."""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
