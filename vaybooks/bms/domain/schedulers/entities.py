"""Scheduler configuration, run log, notification, and report entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.schedulers.schedule import (
    FREQ_DAILY,
    ScheduleSpec,
    format_schedule,
    schedule_to_cron,
)
from vaybooks.bms.domain.schedulers.time import utc_now

DOMAIN_CRM = "crm"
DOMAIN_SALES = "sales"
DOMAIN_PURCHASES = "purchases"
DOMAIN_INVENTORY = "inventory"
DOMAIN_PRODUCTION = "production"
DOMAIN_BOUTIQUE = "boutique"
DOMAIN_PROJECTS = "projects"
DOMAIN_SYSTEM = "system"

# Execution order is fixed so a wave always runs upstream domains first.
DOMAIN_ORDER: tuple[str, ...] = (
    DOMAIN_CRM,
    DOMAIN_SALES,
    DOMAIN_PURCHASES,
    DOMAIN_INVENTORY,
    DOMAIN_PRODUCTION,
    DOMAIN_BOUTIQUE,
    DOMAIN_PROJECTS,
    DOMAIN_SYSTEM,
)

DOMAIN_LABELS: Dict[str, str] = {
    DOMAIN_CRM: "CRM",
    DOMAIN_SALES: "Sales",
    DOMAIN_PURCHASES: "Purchases",
    DOMAIN_INVENTORY: "Inventory",
    DOMAIN_PRODUCTION: "Production",
    DOMAIN_BOUTIQUE: "Boutique",
    DOMAIN_PROJECTS: "Projects",
    DOMAIN_SYSTEM: "System",
}

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_COMPLETED_WITH_ERRORS = "completed_with_errors"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_DRY_RUN = "dry_run"

RUN_STATUSES: tuple[str, ...] = (
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_DRY_RUN,
)

TRIGGER_SCHEDULE = "schedule"
TRIGGER_RUN_NOW = "run_now"
TRIGGER_RUN_DOMAIN = "run_domain"
TRIGGER_RUN_ALL = "run_all"
TRIGGER_DRY_RUN = "dry_run"

TRIGGERS: tuple[str, ...] = (
    TRIGGER_SCHEDULE,
    TRIGGER_RUN_NOW,
    TRIGGER_RUN_DOMAIN,
    TRIGGER_RUN_ALL,
    TRIGGER_DRY_RUN,
)

MANUAL_TRIGGERS: frozenset[str] = frozenset(
    {TRIGGER_RUN_NOW, TRIGGER_RUN_DOMAIN, TRIGGER_RUN_ALL, TRIGGER_DRY_RUN}
)

DEFAULT_BATCH_SIZE = 50
DEFAULT_BATCH_PAUSE_MS = 200
DEFAULT_MAX_IDS_PER_RUN = 10000
DEFAULT_REPORT_MAX_ROWS = 50000
REPORT_ARTIFACT_RETENTION = 30


@dataclass
class SchedulerJobConfig:
    job_id: str
    domain: str
    title: str = ""
    description: str = ""
    enabled: bool = True

    # Plain-language schedule.
    frequency: str = FREQ_DAILY
    time_of_day: str = "06:00"
    weekday: int = 0
    interval_days: int = 1

    # Derived cache fields kept in sync on save.
    cron_expression: str = ""
    next_run_at: Optional[datetime] = None

    # Common rule fields; individual jobs use the subset they need.
    threshold_days: int = 0
    warning_days: int = 0
    grace_days: int = 0
    reminder_offsets_days: List[int] = field(default_factory=list)
    minimum_amount: float = 0.0

    # Processing controls.
    batch_size: int = DEFAULT_BATCH_SIZE
    batch_pause_ms: int = DEFAULT_BATCH_PAUSE_MS
    max_ids_per_run: int = DEFAULT_MAX_IDS_PER_RUN

    # Delivery controls.
    create_activity: bool = True
    create_notification: bool = True
    fallback_user_id: str = ""
    assignee_rule: str = "auto"

    options: Dict[str, Any] = field(default_factory=dict)

    last_run_at: Optional[datetime] = None
    last_status: str = ""
    last_error: str = ""
    updated_at: datetime = field(default_factory=utc_now)
    updated_by: str = ""

    @property
    def schedule(self) -> ScheduleSpec:
        return ScheduleSpec(
            frequency=self.frequency,
            time_of_day=self.time_of_day,
            weekday=self.weekday,
            interval_days=self.interval_days,
        )

    @property
    def schedule_summary(self) -> str:
        return format_schedule(self.schedule)

    def apply_schedule(self, spec: ScheduleSpec) -> None:
        self.frequency = spec.frequency
        self.time_of_day = spec.time_of_day
        self.weekday = spec.weekday
        self.interval_days = spec.interval_days
        self.cron_expression = schedule_to_cron(spec)

    def option(self, key: str, default: Any = None) -> Any:
        return (self.options or {}).get(key, default)


@dataclass
class SchedulerRunLog:
    job_id: str
    domain: str = ""
    trigger: str = TRIGGER_SCHEDULE
    actor_id: str = ""
    status: str = STATUS_QUEUED
    started_at: datetime = field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    identified_count: int = 0
    processed_count: int = 0
    created_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    batch_size: int = DEFAULT_BATCH_SIZE
    batch_count: int = 0
    error_summary: str = ""
    details: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def duration_seconds(self) -> float:
        if not self.finished_at:
            return 0.0
        return max(0.0, (self.finished_at - self.started_at).total_seconds())


@dataclass
class SchedulerNotification:
    recipient_id: str
    domain: str = ""
    kind: str = ""
    title: str = ""
    message: str = ""
    ref_type: str = ""
    ref_id: str = ""
    state: str = "open"
    read_at: Optional[datetime] = None
    dedupe_key: str = ""
    job_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)

    @staticmethod
    def build_dedupe_key(
        recipient_id: str,
        job_id: str,
        ref_type: str,
        ref_id: str,
        state: str = "open",
    ) -> str:
        return f"{recipient_id}|{job_id}|{ref_type}|{ref_id}|{state}"


@dataclass
class SchedulerLease:
    lease_key: str
    holder_id: str = ""
    acquired_at: datetime = field(default_factory=utc_now)
    expires_at: Optional[datetime] = None
    status: str = STATUS_RUNNING


@dataclass
class SchedulerReportConfig:
    domain: str
    report_id: str
    report_title: str = ""
    enabled: bool = False

    frequency: str = FREQ_DAILY
    time_of_day: str = "06:00"
    weekday: int = 0
    interval_days: int = 1
    cron_expression: str = ""
    next_run_at: Optional[datetime] = None

    filters: Dict[str, Any] = field(default_factory=dict)

    recipient_ids: List[str] = field(default_factory=list)
    create_notification: bool = True
    fallback_user_id: str = ""
    max_rows: int = DEFAULT_REPORT_MAX_ROWS

    last_run_at: Optional[datetime] = None
    last_status: str = ""
    last_error: str = ""
    last_artifact_id: str = ""
    updated_at: datetime = field(default_factory=utc_now)
    updated_by: str = ""
    config_id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def schedule(self) -> ScheduleSpec:
        return ScheduleSpec(
            frequency=self.frequency,
            time_of_day=self.time_of_day,
            weekday=self.weekday,
            interval_days=self.interval_days,
        )

    @property
    def schedule_summary(self) -> str:
        return format_schedule(self.schedule)

    @property
    def lease_key(self) -> str:
        return report_lease_key(self.domain, self.report_id)

    def apply_schedule(self, spec: ScheduleSpec) -> None:
        self.frequency = spec.frequency
        self.time_of_day = spec.time_of_day
        self.weekday = spec.weekday
        self.interval_days = spec.interval_days
        self.cron_expression = schedule_to_cron(spec)


@dataclass
class SchedulerReportRunLog:
    domain: str
    report_id: str
    config_id: str = ""
    report_title: str = ""
    trigger: str = TRIGGER_SCHEDULE
    actor_id: str = ""
    status: str = STATUS_QUEUED
    started_at: datetime = field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    row_count: int = 0
    truncated: bool = False
    error_summary: str = ""
    resolved_filters: Dict[str, Any] = field(default_factory=dict)
    artifact_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def duration_seconds(self) -> float:
        if not self.finished_at:
            return 0.0
        return max(0.0, (self.finished_at - self.started_at).total_seconds())


@dataclass
class SchedulerReportArtifact:
    domain: str
    report_id: str
    run_id: str = ""
    filename: str = ""
    content_type: str = "text/csv"
    data: bytes = b""
    byte_size: int = 0
    created_at: datetime = field(default_factory=utc_now)
    expires_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: uuid4().hex)


def report_lease_key(domain: str, report_id: str) -> str:
    return f"report:{domain}:{report_id}"
