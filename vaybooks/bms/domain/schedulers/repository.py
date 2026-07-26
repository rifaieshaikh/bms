"""Repository protocols for the shared scheduler."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Protocol

from vaybooks.bms.domain.schedulers.entities import (
    SchedulerJobConfig,
    SchedulerNotification,
    SchedulerReportArtifact,
    SchedulerReportConfig,
    SchedulerReportRunLog,
    SchedulerRunLog,
)


class SchedulerJobConfigRepository(Protocol):
    def save(self, config: SchedulerJobConfig) -> SchedulerJobConfig: ...

    def find_by_id(self, job_id: str) -> Optional[SchedulerJobConfig]: ...

    def list_all(self) -> List[SchedulerJobConfig]: ...

    def list_by_domain(self, domain: str) -> List[SchedulerJobConfig]: ...

    def list_enabled(self) -> List[SchedulerJobConfig]: ...


class SchedulerRunLogRepository(Protocol):
    def save(self, log: SchedulerRunLog) -> SchedulerRunLog: ...

    def find_by_id(self, run_id: str) -> Optional[SchedulerRunLog]: ...

    def list_for_job(self, job_id: str, limit: int = 20) -> List[SchedulerRunLog]: ...

    def list_recent(
        self, limit: int = 20, domain: str = ""
    ) -> List[SchedulerRunLog]: ...


class SchedulerLeaseRepository(Protocol):
    def acquire(
        self, lease_key: str, holder_id: str, *, ttl_seconds: int, now: datetime
    ) -> bool: ...

    def refresh(
        self, lease_key: str, holder_id: str, *, ttl_seconds: int, now: datetime
    ) -> bool: ...

    def release(self, lease_key: str, holder_id: str) -> None: ...

    def is_held(self, lease_key: str, *, now: datetime) -> bool: ...


class SchedulerNotificationRepository(Protocol):
    def save(self, notification: SchedulerNotification) -> SchedulerNotification: ...

    def find_by_dedupe_key(self, dedupe_key: str) -> Optional[SchedulerNotification]: ...

    def list_for_recipient(
        self, recipient_id: str, *, state: str = "open", limit: int = 50
    ) -> List[SchedulerNotification]: ...

    def mark_read(self, notification_id: str) -> None: ...


class SchedulerReportConfigRepository(Protocol):
    def save(self, config: SchedulerReportConfig) -> SchedulerReportConfig: ...

    def find(self, domain: str, report_id: str) -> Optional[SchedulerReportConfig]: ...

    def list_by_domain(self, domain: str) -> List[SchedulerReportConfig]: ...

    def list_enabled(self) -> List[SchedulerReportConfig]: ...


class SchedulerReportRunLogRepository(Protocol):
    def save(self, log: SchedulerReportRunLog) -> SchedulerReportRunLog: ...

    def list_for_report(
        self, domain: str, report_id: str, limit: int = 20
    ) -> List[SchedulerReportRunLog]: ...

    def count_successful_on_day(
        self, domain: str, report_id: str, *, start: datetime, end: datetime
    ) -> int: ...


class SchedulerReportArtifactRepository(Protocol):
    def save(self, artifact: SchedulerReportArtifact) -> SchedulerReportArtifact: ...

    def find_by_id(self, artifact_id: str) -> Optional[SchedulerReportArtifact]: ...

    def prune(self, domain: str, report_id: str, keep: int) -> int: ...
