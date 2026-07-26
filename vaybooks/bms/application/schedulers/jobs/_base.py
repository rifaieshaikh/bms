"""Shared plumbing for scheduler jobs.

Most jobs share the same shape: identify candidate ids cheaply, then for each id
re-read the source, confirm the trigger still holds, and emit a deduplicated
notification plus an optional review activity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from vaybooks.bms.application.schedulers.protocol import JobContext, JobResult
from vaybooks.bms.domain.schedulers.time import (
    business_date_of,
    business_day_bounds,
    business_today,
)

logger = logging.getLogger("vaybooks.bms.schedulers")


@dataclass
class Deps:
    """Repositories and services jobs may use, all optional."""

    queries: Any = None
    services: Dict[str, Any] = field(default_factory=dict)
    repos: Dict[str, Any] = field(default_factory=dict)

    def service(self, key: str) -> Any:
        return (self.services or {}).get(key)

    def repo(self, key: str) -> Any:
        return (self.repos or {}).get(key)


@dataclass
class Outcome:
    """What a job wants to emit for one candidate."""

    recipient_id: str = ""
    title: str = ""
    message: str = ""
    ref_type: str = ""
    ref_id: str = ""
    kind: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Optional CRM review activity.
    activity_label: str = ""
    activity_customer_id: str = ""
    activity_lead_id: str = ""
    activity_enquiry_id: str = ""
    activity_notes: str = ""
    activity_source_id: str = ""


class BaseJob:
    """Identify ids, describe an outcome per id, and write it idempotently."""

    job_id: str = ""
    domain: str = ""
    title: str = ""

    def __init__(self, deps: Deps):
        self.deps = deps

    # --- hooks subclasses implement ---

    def identify(self, ctx: JobContext) -> List[str]:  # pragma: no cover - abstract
        raise NotImplementedError

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        raise NotImplementedError

    # --- shared write path ---

    def process_batch(self, ctx: JobContext, ids: List[str]) -> JobResult:
        result = JobResult()
        for candidate_id in ids:
            result.processed += 1
            try:
                outcome = self.describe(ctx, candidate_id)
            except Exception as exc:
                result.errors += 1
                result.messages.append(f"{candidate_id}: {exc}")
                continue
            if outcome is None:
                result.skipped += 1
                continue
            created = self._emit(ctx, outcome)
            if created:
                result.created += created
            else:
                result.skipped += 1
        return result

    def _emit(self, ctx: JobContext, outcome: Outcome) -> int:
        created = 0
        config = ctx.config
        if config.create_notification and outcome.recipient_id and ctx.notify:
            notification = ctx.notify(
                recipient_id=outcome.recipient_id,
                domain=self.domain,
                job_id=self.job_id,
                kind=outcome.kind or self.job_id,
                title=outcome.title,
                message=outcome.message,
                ref_type=outcome.ref_type,
                ref_id=outcome.ref_id,
                metadata=outcome.metadata,
            )
            if notification is not None:
                created += 1
        if config.create_activity and outcome.activity_label:
            if self._create_activity(ctx, outcome):
                created += 1
        return created

    def _create_activity(self, ctx: JobContext, outcome: Outcome) -> bool:
        auto = self.deps.service("crm_auto_activities")
        if auto is None:
            return False
        activity_repo = self.deps.repo("crm_activities")
        source_id = outcome.activity_source_id or outcome.ref_id
        if activity_repo is not None:
            try:
                existing = activity_repo.find_by_source(
                    self.domain,
                    self.job_id,
                    source_id,
                    _activity_key(outcome.activity_label),
                )
            except Exception:
                existing = None
            if existing is not None:
                return False
        try:
            auto.record_event(
                type_key=self.job_id,
                source_module=self.domain,
                source_txn_type=self.job_id,
                source_txn_id=source_id,
                customer_id=outcome.activity_customer_id,
                lead_id=outcome.activity_lead_id,
                enquiry_id=outcome.activity_enquiry_id,
                assigned_user_id=outcome.recipient_id,
                notes=outcome.activity_notes or outcome.message,
                actor_id="system",
                actor_name="Scheduler",
                activity_label=outcome.activity_label,
            )
            return True
        except Exception:
            logger.exception("Scheduler %s could not create activity", self.job_id)
            return False


def _activity_key(label: str) -> str:
    from vaybooks.bms.domain.crm.services import activity_type_key

    return activity_type_key(label)


# --- shared helpers ----------------------------------------------------------


def cap(ctx: JobContext) -> int:
    return max(1, int(ctx.config.max_ids_per_run))


def today_bounds(ctx: JobContext) -> tuple[datetime, datetime]:
    return business_day_bounds(business_date_of(ctx.now) or business_today())


def days_before(ctx: JobContext, days: int) -> datetime:
    return ctx.now - timedelta(days=max(0, int(days)))


def business_date(ctx: JobContext) -> date:
    return business_date_of(ctx.now) or business_today()


def day_bucket(value: Optional[datetime | date]) -> str:
    if value is None:
        return "none"
    if isinstance(value, datetime):
        value = value.date()
    return value.isoformat()


def week_bucket(value: date) -> str:
    iso = value.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def month_bucket(value: date) -> str:
    return f"{value.year}-{value.month:02d}"


def aging_bucket(days: int) -> str:
    for edge in (90, 60, 30, 7):
        if days >= edge:
            return f"{edge}+"
    return "0"


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def resolve_recipient(ctx: JobContext, *candidates: Any) -> str:
    return first_non_empty(*candidates, ctx.config.fallback_user_id)


def split_ref(candidate_id: str) -> Sequence[str]:
    return candidate_id.split("|")


def money(value: Any) -> float:
    try:
        return round(float(value or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def fmt_money(value: Any) -> str:
    return f"Rs {money(value):,.2f}"
