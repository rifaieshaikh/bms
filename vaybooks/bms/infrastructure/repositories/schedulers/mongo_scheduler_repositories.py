"""Mongo persistence for scheduler configs, runs, leases, notifications, reports."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bson.binary import Binary
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from vaybooks.bms.domain.schedulers.entities import (
    DEFAULT_BATCH_PAUSE_MS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_IDS_PER_RUN,
    DEFAULT_REPORT_MAX_ROWS,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_QUEUED,
    STATUS_RUNNING,
    SchedulerJobConfig,
    SchedulerNotification,
    SchedulerReportArtifact,
    SchedulerReportConfig,
    SchedulerReportRunLog,
    SchedulerRunLog,
)
from vaybooks.bms.domain.schedulers.time import utc_now


def _dt(value: Any) -> Optional[datetime]:
    return value if isinstance(value, datetime) else None


def job_config_to_doc(config: SchedulerJobConfig) -> Dict[str, Any]:
    return {
        "_id": config.job_id,
        "job_id": config.job_id,
        "domain": config.domain,
        "title": config.title,
        "description": config.description,
        "enabled": bool(config.enabled),
        "frequency": config.frequency,
        "time_of_day": config.time_of_day,
        "weekday": int(config.weekday),
        "interval_days": int(config.interval_days),
        "cron_expression": config.cron_expression,
        "next_run_at": config.next_run_at,
        "threshold_days": int(config.threshold_days),
        "warning_days": int(config.warning_days),
        "grace_days": int(config.grace_days),
        "reminder_offsets_days": list(config.reminder_offsets_days or []),
        "minimum_amount": float(config.minimum_amount),
        "batch_size": int(config.batch_size),
        "batch_pause_ms": int(config.batch_pause_ms),
        "max_ids_per_run": int(config.max_ids_per_run),
        "create_activity": bool(config.create_activity),
        "create_notification": bool(config.create_notification),
        "fallback_user_id": config.fallback_user_id,
        "assignee_rule": config.assignee_rule,
        "options": dict(config.options or {}),
        "last_run_at": config.last_run_at,
        "last_status": config.last_status,
        "last_error": config.last_error,
        "updated_at": config.updated_at,
        "updated_by": config.updated_by,
    }


def job_config_from_doc(doc: Dict[str, Any]) -> SchedulerJobConfig:
    return SchedulerJobConfig(
        job_id=doc.get("job_id") or doc.get("_id", ""),
        domain=doc.get("domain", ""),
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        enabled=bool(doc.get("enabled", True)),
        frequency=doc.get("frequency", "daily"),
        time_of_day=doc.get("time_of_day", "06:00"),
        weekday=int(doc.get("weekday", 0) or 0),
        interval_days=int(doc.get("interval_days", 1) or 1),
        cron_expression=doc.get("cron_expression", ""),
        next_run_at=_dt(doc.get("next_run_at")),
        threshold_days=int(doc.get("threshold_days", 0) or 0),
        warning_days=int(doc.get("warning_days", 0) or 0),
        grace_days=int(doc.get("grace_days", 0) or 0),
        reminder_offsets_days=list(doc.get("reminder_offsets_days") or []),
        minimum_amount=float(doc.get("minimum_amount", 0.0) or 0.0),
        batch_size=int(doc.get("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE),
        batch_pause_ms=int(
            doc.get("batch_pause_ms", DEFAULT_BATCH_PAUSE_MS) or DEFAULT_BATCH_PAUSE_MS
        ),
        max_ids_per_run=int(
            doc.get("max_ids_per_run", DEFAULT_MAX_IDS_PER_RUN) or DEFAULT_MAX_IDS_PER_RUN
        ),
        create_activity=bool(doc.get("create_activity", True)),
        create_notification=bool(doc.get("create_notification", True)),
        fallback_user_id=doc.get("fallback_user_id", ""),
        assignee_rule=doc.get("assignee_rule", "auto"),
        options=dict(doc.get("options") or {}),
        last_run_at=_dt(doc.get("last_run_at")),
        last_status=doc.get("last_status", ""),
        last_error=doc.get("last_error", ""),
        updated_at=_dt(doc.get("updated_at")) or utc_now(),
        updated_by=doc.get("updated_by", ""),
    )


class MongoSchedulerJobConfigRepository:
    def __init__(self, db: Database):
        self._collection = db.scheduler_job_configs

    def save(self, config: SchedulerJobConfig) -> SchedulerJobConfig:
        config.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": config.job_id}, job_config_to_doc(config), upsert=True
        )
        return config

    def find_by_id(self, job_id: str) -> Optional[SchedulerJobConfig]:
        doc = self._collection.find_one({"_id": job_id})
        return job_config_from_doc(doc) if doc else None

    def list_all(self) -> List[SchedulerJobConfig]:
        return [job_config_from_doc(d) for d in self._collection.find({})]

    def list_by_domain(self, domain: str) -> List[SchedulerJobConfig]:
        return [
            job_config_from_doc(d) for d in self._collection.find({"domain": domain})
        ]

    def list_enabled(self) -> List[SchedulerJobConfig]:
        return [
            job_config_from_doc(d) for d in self._collection.find({"enabled": True})
        ]


def run_log_to_doc(log: SchedulerRunLog) -> Dict[str, Any]:
    return {
        "_id": log.id,
        "job_id": log.job_id,
        "domain": log.domain,
        "trigger": log.trigger,
        "actor_id": log.actor_id,
        "status": log.status,
        "started_at": log.started_at,
        "finished_at": log.finished_at,
        "identified_count": int(log.identified_count),
        "processed_count": int(log.processed_count),
        "created_count": int(log.created_count),
        "skipped_count": int(log.skipped_count),
        "error_count": int(log.error_count),
        "batch_size": int(log.batch_size),
        "batch_count": int(log.batch_count),
        "error_summary": log.error_summary[:2000],
        "details": [str(d)[:500] for d in (log.details or [])][:20],
    }


def run_log_from_doc(doc: Dict[str, Any]) -> SchedulerRunLog:
    return SchedulerRunLog(
        job_id=doc.get("job_id", ""),
        domain=doc.get("domain", ""),
        trigger=doc.get("trigger", ""),
        actor_id=doc.get("actor_id", ""),
        status=doc.get("status", ""),
        started_at=_dt(doc.get("started_at")) or utc_now(),
        finished_at=_dt(doc.get("finished_at")),
        identified_count=int(doc.get("identified_count", 0) or 0),
        processed_count=int(doc.get("processed_count", 0) or 0),
        created_count=int(doc.get("created_count", 0) or 0),
        skipped_count=int(doc.get("skipped_count", 0) or 0),
        error_count=int(doc.get("error_count", 0) or 0),
        batch_size=int(doc.get("batch_size", 0) or 0),
        batch_count=int(doc.get("batch_count", 0) or 0),
        error_summary=doc.get("error_summary", ""),
        details=list(doc.get("details") or []),
        id=doc.get("_id", ""),
    )


class MongoSchedulerRunLogRepository:
    def __init__(self, db: Database):
        self._collection = db.scheduler_run_logs

    def save(self, log: SchedulerRunLog) -> SchedulerRunLog:
        self._collection.replace_one({"_id": log.id}, run_log_to_doc(log), upsert=True)
        return log

    def find_by_id(self, run_id: str) -> Optional[SchedulerRunLog]:
        doc = self._collection.find_one({"_id": run_id})
        return run_log_from_doc(doc) if doc else None

    def list_for_job(self, job_id: str, limit: int = 20) -> List[SchedulerRunLog]:
        cursor = (
            self._collection.find({"job_id": job_id})
            .sort("started_at", DESCENDING)
            .limit(int(limit))
        )
        return [run_log_from_doc(d) for d in cursor]

    def list_recent(self, limit: int = 20, domain: str = "") -> List[SchedulerRunLog]:
        query: Dict[str, Any] = {"domain": domain} if domain else {}
        cursor = (
            self._collection.find(query).sort("started_at", DESCENDING).limit(int(limit))
        )
        return [run_log_from_doc(d) for d in cursor]


class MongoSchedulerLeaseRepository:
    """Atomic single-holder leases keyed by job id or report lease key."""

    def __init__(self, db: Database):
        self._collection = db.scheduler_job_leases

    def acquire(
        self, lease_key: str, holder_id: str, *, ttl_seconds: int, now: datetime
    ) -> bool:
        expires_at = now + timedelta(seconds=int(ttl_seconds))
        # Only a missing or expired lease may be taken; the filter and the
        # unique _id together make this atomic across processes.
        result = self._collection.update_one(
            {"_id": lease_key, "expires_at": {"$lte": now}},
            {
                "$set": {
                    "lease_key": lease_key,
                    "holder_id": holder_id,
                    "acquired_at": now,
                    "expires_at": expires_at,
                    "status": STATUS_RUNNING,
                }
            },
        )
        if result.modified_count:
            return True
        try:
            self._collection.insert_one(
                {
                    "_id": lease_key,
                    "lease_key": lease_key,
                    "holder_id": holder_id,
                    "acquired_at": now,
                    "expires_at": expires_at,
                    "status": STATUS_RUNNING,
                }
            )
            return True
        except DuplicateKeyError:
            return False

    def refresh(
        self, lease_key: str, holder_id: str, *, ttl_seconds: int, now: datetime
    ) -> bool:
        result = self._collection.update_one(
            {"_id": lease_key, "holder_id": holder_id},
            {"$set": {"expires_at": now + timedelta(seconds=int(ttl_seconds))}},
        )
        return bool(result.matched_count)

    def release(self, lease_key: str, holder_id: str) -> None:
        self._collection.delete_one({"_id": lease_key, "holder_id": holder_id})

    def is_held(self, lease_key: str, *, now: datetime) -> bool:
        doc = self._collection.find_one({"_id": lease_key})
        if not doc:
            return False
        expires = _dt(doc.get("expires_at"))
        return bool(expires and expires > now)


def notification_to_doc(n: SchedulerNotification) -> Dict[str, Any]:
    return {
        "_id": n.id,
        "recipient_id": n.recipient_id,
        "domain": n.domain,
        "kind": n.kind,
        "title": n.title,
        "message": n.message,
        "ref_type": n.ref_type,
        "ref_id": n.ref_id,
        "state": n.state,
        "read_at": n.read_at,
        "dedupe_key": n.dedupe_key,
        "job_id": n.job_id,
        "metadata": dict(n.metadata or {}),
        "created_at": n.created_at,
    }


def notification_from_doc(doc: Dict[str, Any]) -> SchedulerNotification:
    return SchedulerNotification(
        recipient_id=doc.get("recipient_id", ""),
        domain=doc.get("domain", ""),
        kind=doc.get("kind", ""),
        title=doc.get("title", ""),
        message=doc.get("message", ""),
        ref_type=doc.get("ref_type", ""),
        ref_id=doc.get("ref_id", ""),
        state=doc.get("state", "open"),
        read_at=_dt(doc.get("read_at")),
        dedupe_key=doc.get("dedupe_key", ""),
        job_id=doc.get("job_id", ""),
        metadata=dict(doc.get("metadata") or {}),
        id=doc.get("_id", ""),
        created_at=_dt(doc.get("created_at")) or utc_now(),
    )


class MongoSchedulerNotificationRepository:
    def __init__(self, db: Database):
        self._collection = db.scheduler_notifications

    def save(self, notification: SchedulerNotification) -> SchedulerNotification:
        try:
            self._collection.replace_one(
                {"_id": notification.id}, notification_to_doc(notification), upsert=True
            )
        except DuplicateKeyError:
            # A concurrent run already created the same deduped notification.
            existing = self.find_by_dedupe_key(notification.dedupe_key)
            if existing:
                return existing
            raise
        return notification

    def find_by_dedupe_key(self, dedupe_key: str) -> Optional[SchedulerNotification]:
        if not dedupe_key:
            return None
        doc = self._collection.find_one({"dedupe_key": dedupe_key})
        return notification_from_doc(doc) if doc else None

    def list_for_recipient(
        self, recipient_id: str, *, state: str = "open", limit: int = 50
    ) -> List[SchedulerNotification]:
        query: Dict[str, Any] = {"recipient_id": recipient_id}
        if state:
            query["state"] = state
        cursor = (
            self._collection.find(query).sort("created_at", DESCENDING).limit(int(limit))
        )
        return [notification_from_doc(d) for d in cursor]

    def mark_read(self, notification_id: str) -> None:
        self._collection.update_one(
            {"_id": notification_id},
            {"$set": {"state": "read", "read_at": utc_now()}},
        )


def report_config_to_doc(config: SchedulerReportConfig) -> Dict[str, Any]:
    return {
        "_id": config.config_id,
        "config_id": config.config_id,
        "domain": config.domain,
        "report_id": config.report_id,
        "report_title": config.report_title,
        "enabled": bool(config.enabled),
        "frequency": config.frequency,
        "time_of_day": config.time_of_day,
        "weekday": int(config.weekday),
        "interval_days": int(config.interval_days),
        "cron_expression": config.cron_expression,
        "next_run_at": config.next_run_at,
        "filters": dict(config.filters or {}),
        "recipient_ids": list(config.recipient_ids or []),
        "create_notification": bool(config.create_notification),
        "fallback_user_id": config.fallback_user_id,
        "max_rows": int(config.max_rows),
        "last_run_at": config.last_run_at,
        "last_status": config.last_status,
        "last_error": config.last_error,
        "last_artifact_id": config.last_artifact_id,
        "updated_at": config.updated_at,
        "updated_by": config.updated_by,
    }


def report_config_from_doc(doc: Dict[str, Any]) -> SchedulerReportConfig:
    return SchedulerReportConfig(
        domain=doc.get("domain", ""),
        report_id=doc.get("report_id", ""),
        report_title=doc.get("report_title", ""),
        enabled=bool(doc.get("enabled", False)),
        frequency=doc.get("frequency", "daily"),
        time_of_day=doc.get("time_of_day", "06:00"),
        weekday=int(doc.get("weekday", 0) or 0),
        interval_days=int(doc.get("interval_days", 1) or 1),
        cron_expression=doc.get("cron_expression", ""),
        next_run_at=_dt(doc.get("next_run_at")),
        filters=dict(doc.get("filters") or {}),
        recipient_ids=list(doc.get("recipient_ids") or []),
        create_notification=bool(doc.get("create_notification", True)),
        fallback_user_id=doc.get("fallback_user_id", ""),
        max_rows=int(doc.get("max_rows", DEFAULT_REPORT_MAX_ROWS) or DEFAULT_REPORT_MAX_ROWS),
        last_run_at=_dt(doc.get("last_run_at")),
        last_status=doc.get("last_status", ""),
        last_error=doc.get("last_error", ""),
        last_artifact_id=doc.get("last_artifact_id", ""),
        updated_at=_dt(doc.get("updated_at")) or utc_now(),
        updated_by=doc.get("updated_by", ""),
        config_id=doc.get("config_id") or doc.get("_id", ""),
    )


class MongoSchedulerReportConfigRepository:
    def __init__(self, db: Database):
        self._collection = db.scheduler_report_configs

    def save(self, config: SchedulerReportConfig) -> SchedulerReportConfig:
        config.updated_at = utc_now()
        self._collection.replace_one(
            {"domain": config.domain, "report_id": config.report_id},
            report_config_to_doc(config),
            upsert=True,
        )
        return config

    def find(self, domain: str, report_id: str) -> Optional[SchedulerReportConfig]:
        doc = self._collection.find_one({"domain": domain, "report_id": report_id})
        return report_config_from_doc(doc) if doc else None

    def list_by_domain(self, domain: str) -> List[SchedulerReportConfig]:
        return [
            report_config_from_doc(d) for d in self._collection.find({"domain": domain})
        ]

    def list_enabled(self) -> List[SchedulerReportConfig]:
        return [
            report_config_from_doc(d) for d in self._collection.find({"enabled": True})
        ]


def report_run_log_to_doc(log: SchedulerReportRunLog) -> Dict[str, Any]:
    return {
        "_id": log.id,
        "run_id": log.id,
        "domain": log.domain,
        "report_id": log.report_id,
        "report_title": log.report_title,
        "config_id": log.config_id,
        "trigger": log.trigger,
        "actor_id": log.actor_id,
        "status": log.status,
        "started_at": log.started_at,
        "finished_at": log.finished_at,
        "row_count": int(log.row_count),
        "truncated": bool(log.truncated),
        "error_summary": log.error_summary[:2000],
        "resolved_filters": dict(log.resolved_filters or {}),
        "artifact_id": log.artifact_id,
    }


def report_run_log_from_doc(doc: Dict[str, Any]) -> SchedulerReportRunLog:
    return SchedulerReportRunLog(
        domain=doc.get("domain", ""),
        report_id=doc.get("report_id", ""),
        config_id=doc.get("config_id", ""),
        report_title=doc.get("report_title", ""),
        trigger=doc.get("trigger", ""),
        actor_id=doc.get("actor_id", ""),
        status=doc.get("status", ""),
        started_at=_dt(doc.get("started_at")) or utc_now(),
        finished_at=_dt(doc.get("finished_at")),
        row_count=int(doc.get("row_count", 0) or 0),
        truncated=bool(doc.get("truncated", False)),
        error_summary=doc.get("error_summary", ""),
        resolved_filters=dict(doc.get("resolved_filters") or {}),
        artifact_id=doc.get("artifact_id", ""),
        id=doc.get("_id", ""),
    )


class MongoSchedulerReportRunLogRepository:
    def __init__(self, db: Database):
        self._collection = db.scheduler_report_run_logs

    def save(self, log: SchedulerReportRunLog) -> SchedulerReportRunLog:
        self._collection.replace_one(
            {"_id": log.id}, report_run_log_to_doc(log), upsert=True
        )
        return log

    def list_for_report(
        self, domain: str, report_id: str, limit: int = 20
    ) -> List[SchedulerReportRunLog]:
        cursor = (
            self._collection.find({"domain": domain, "report_id": report_id})
            .sort("started_at", DESCENDING)
            .limit(int(limit))
        )
        return [report_run_log_from_doc(d) for d in cursor]

    def count_successful_on_day(
        self, domain: str, report_id: str, *, start: datetime, end: datetime
    ) -> int:
        return self._collection.count_documents(
            {
                "domain": domain,
                "report_id": report_id,
                "trigger": "schedule",
                "status": {"$in": [STATUS_COMPLETED, STATUS_COMPLETED_WITH_ERRORS]},
                "started_at": {"$gte": start, "$lt": end},
            }
        )


class MongoSchedulerReportArtifactRepository:
    """CSV artifacts stored inline as BSON Binary, matching attachment storage."""

    def __init__(self, db: Database):
        self._collection = db.scheduler_report_artifacts

    def save(self, artifact: SchedulerReportArtifact) -> SchedulerReportArtifact:
        self._collection.replace_one(
            {"_id": artifact.id},
            {
                "_id": artifact.id,
                "domain": artifact.domain,
                "report_id": artifact.report_id,
                "run_id": artifact.run_id,
                "filename": artifact.filename,
                "content_type": artifact.content_type,
                "data": Binary(artifact.data or b""),
                "byte_size": int(artifact.byte_size),
                "created_at": artifact.created_at,
                "expires_at": artifact.expires_at,
            },
            upsert=True,
        )
        return artifact

    def find_by_id(self, artifact_id: str) -> Optional[SchedulerReportArtifact]:
        doc = self._collection.find_one({"_id": artifact_id})
        if not doc:
            return None
        return SchedulerReportArtifact(
            domain=doc.get("domain", ""),
            report_id=doc.get("report_id", ""),
            run_id=doc.get("run_id", ""),
            filename=doc.get("filename", ""),
            content_type=doc.get("content_type", "text/csv"),
            data=bytes(doc.get("data") or b""),
            byte_size=int(doc.get("byte_size", 0) or 0),
            created_at=_dt(doc.get("created_at")) or utc_now(),
            expires_at=_dt(doc.get("expires_at")),
            id=doc.get("_id", ""),
        )

    def prune(self, domain: str, report_id: str, keep: int) -> int:
        cursor = (
            self._collection.find(
                {"domain": domain, "report_id": report_id}, {"_id": 1}
            )
            .sort("created_at", DESCENDING)
            .skip(max(0, int(keep)))
        )
        stale = [d["_id"] for d in cursor]
        if not stale:
            return 0
        self._collection.delete_many({"_id": {"$in": stale}})
        return len(stale)


__all__ = [
    "MongoSchedulerJobConfigRepository",
    "MongoSchedulerLeaseRepository",
    "MongoSchedulerNotificationRepository",
    "MongoSchedulerReportArtifactRepository",
    "MongoSchedulerReportConfigRepository",
    "MongoSchedulerReportRunLogRepository",
    "MongoSchedulerRunLogRepository",
    "job_config_from_doc",
    "job_config_to_doc",
    "ASCENDING",
    "STATUS_QUEUED",
]
