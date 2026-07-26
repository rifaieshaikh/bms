"""Contract every scheduler job implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol

from vaybooks.bms.domain.schedulers.entities import SchedulerJobConfig
from vaybooks.bms.domain.schedulers.time import utc_now


@dataclass
class JobContext:
    """Everything a job needs for one run, with no Streamlit dependency."""

    config: SchedulerJobConfig
    now: datetime = field(default_factory=utc_now)
    actor_id: str = ""
    dry_run: bool = False
    notify: Optional[Callable[..., Any]] = None

    @property
    def job_id(self) -> str:
        return self.config.job_id

    @property
    def domain(self) -> str:
        return self.config.domain

    def option(self, key: str, default: Any = None) -> Any:
        return self.config.option(key, default)


@dataclass
class JobResult:
    """Outcome of processing a single batch."""

    processed: int = 0
    created: int = 0
    skipped: int = 0
    errors: int = 0
    messages: List[str] = field(default_factory=list)

    def merge(self, other: "JobResult") -> None:
        self.processed += other.processed
        self.created += other.created
        self.skipped += other.skipped
        self.errors += other.errors
        self.messages.extend(other.messages)


class SchedulerJob(Protocol):
    """Identify impacted IDs cheaply, then process them one batch at a time."""

    job_id: str
    domain: str
    title: str

    def identify(self, ctx: JobContext) -> List[str]: ...

    def process_batch(self, ctx: JobContext, ids: List[str]) -> JobResult: ...


@dataclass
class JobDefinition:
    """Seed metadata used by the migration and the settings UI."""

    job_id: str
    domain: str
    title: str
    description: str = ""
    enabled: bool = True
    frequency: str = "daily"
    time_of_day: str = "06:00"
    weekday: int = 0
    interval_days: int = 1
    threshold_days: int = 0
    warning_days: int = 0
    grace_days: int = 0
    reminder_offsets_days: List[int] = field(default_factory=list)
    minimum_amount: float = 0.0
    create_activity: bool = True
    create_notification: bool = True
    options: Dict[str, Any] = field(default_factory=dict)
    # Field keys rendered as rule settings on the job editor.
    rule_fields: List[str] = field(default_factory=list)
