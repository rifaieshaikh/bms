"""System schedulers: database backup."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from vaybooks.bms.application.schedulers.jobs._base import BaseJob, Deps, Outcome
from vaybooks.bms.application.schedulers.protocol import (
    JobContext,
    JobDefinition,
    JobResult,
)
from vaybooks.bms.domain.schedulers.entities import DOMAIN_SYSTEM
from vaybooks.bms.domain.schedulers.schedule import FREQ_DAILY, FREQ_WEEKLY
from vaybooks.bms.infrastructure.config.runtime import is_desktop
from vaybooks.bms.infrastructure.config.settings import get_settings

logger = logging.getLogger("vaybooks.bms.schedulers")

_LAST_BACKUP_KEY = "system.db_backup.last_run"


class DbBackupJob(BaseJob):
    """Create a configured DB backup on desktop when schedule is due."""

    job_id = "system.db_backup"
    domain = DOMAIN_SYSTEM
    title = "Database backup"

    def identify(self, ctx: JobContext) -> List[str]:
        if not is_desktop():
            return []
        settings = get_settings()
        schedule = (settings.backup_schedule or "off").strip().lower()
        if schedule == "off":
            return []
        if not self._is_due(schedule):
            return []
        return ["backup"]

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        return Outcome(
            recipient_id="",
            title="Database backup",
            message="Scheduled database backup",
            ref_type="backup",
            ref_id=candidate_id,
            kind="system",
        )

    def process_batch(self, ctx: JobContext, ids: List[str]) -> JobResult:
        result = JobResult(processed=len(ids))
        if not ids:
            return result
        if ctx.dry_run:
            result.skipped = len(ids)
            result.messages.append("dry_run")
            return result
        try:
            from vaybooks.bms.infrastructure.backup.service import BackupService
            from vaybooks.bms.infrastructure.db.connection import get_database

            service = BackupService(get_database())
            # Bypass schedule_off guard — identify already decided due.
            settings = get_settings()
            path = service.save_backup_to_disk(mode=settings.backup_mode)
            if not path:
                result.errors = 1
                result.messages.append("save_failed")
                return result
            if settings.backup_google_drive_enabled:
                try:
                    from vaybooks.bms.infrastructure.backup.google_drive import (
                        upload_backup_and_prune,
                    )

                    upload_backup_and_prune(
                        path, retention=settings.backup_retention
                    )
                except Exception as exc:
                    logger.exception("Scheduled Drive upload failed")
                    result.messages.append(f"drive_error:{exc}")
            self._mark_ran()
            result.created = 1
            result.messages.append(str(path))
        except Exception as exc:
            logger.exception("Scheduled backup failed")
            result.errors = 1
            result.messages.append(str(exc))
        return result

    def _is_due(self, schedule: str) -> bool:
        last = self._last_run()
        now = datetime.now(timezone.utc)
        if last is None:
            return True
        if schedule == "daily":
            return now - last >= timedelta(hours=20)
        if schedule == "weekly":
            return now - last >= timedelta(days=6)
        return False

    def _last_run(self) -> Optional[datetime]:
        coll = self._state_collection()
        if coll is None:
            return None
        doc = coll.find_one({"_id": _LAST_BACKUP_KEY})
        if not doc:
            return None
        raw = doc.get("last_run")
        if isinstance(raw, datetime):
            if raw.tzinfo is None:
                return raw.replace(tzinfo=timezone.utc)
            return raw
        return None

    def _mark_ran(self) -> None:
        coll = self._state_collection()
        if coll is None:
            return
        coll.update_one(
            {"_id": _LAST_BACKUP_KEY},
            {"$set": {"last_run": datetime.now(timezone.utc)}},
            upsert=True,
        )

    def _state_collection(self):
        queries = self.deps.queries
        db = getattr(queries, "_db", None) if queries is not None else None
        if db is None:
            try:
                from vaybooks.bms.infrastructure.db.connection import get_database

                db = get_database()
            except Exception:
                return None
        return db["scheduler_job_state"]


def system_jobs(deps: Deps) -> List[Tuple[BaseJob, JobDefinition]]:
    job = DbBackupJob(deps)
    definition = JobDefinition(
        job_id=job.job_id,
        domain=job.domain,
        title=job.title,
        description="Create a local database backup (desktop). Optionally upload to Google Drive.",
        enabled=True,
        frequency=FREQ_DAILY,
        time_of_day="02:00",
    )
    # Seed as daily; runtime still respects BACKUP_SCHEDULE off/daily/weekly.
    _ = FREQ_WEEKLY
    return [(job, definition)]
