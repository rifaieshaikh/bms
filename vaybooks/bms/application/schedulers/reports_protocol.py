"""Scheduled report contracts, relative date ranges, and CSV serialization."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Protocol

from vaybooks.bms.domain.schedulers.time import business_today

RANGE_TODAY = "today"
RANGE_YESTERDAY = "yesterday"
RANGE_LAST_7_DAYS = "last_7_days"
RANGE_LAST_30_DAYS = "last_30_days"
RANGE_MONTH_TO_DATE = "month_to_date"
RANGE_PREVIOUS_MONTH = "previous_month"
RANGE_LAST_N_DAYS = "last_n_days"

RELATIVE_RANGES: tuple[str, ...] = (
    RANGE_TODAY,
    RANGE_YESTERDAY,
    RANGE_LAST_7_DAYS,
    RANGE_LAST_30_DAYS,
    RANGE_MONTH_TO_DATE,
    RANGE_PREVIOUS_MONTH,
    RANGE_LAST_N_DAYS,
)

RELATIVE_RANGE_LABELS: Dict[str, str] = {
    RANGE_TODAY: "Today",
    RANGE_YESTERDAY: "Yesterday",
    RANGE_LAST_7_DAYS: "Last 7 days",
    RANGE_LAST_30_DAYS: "Last 30 days",
    RANGE_MONTH_TO_DATE: "Month to date",
    RANGE_PREVIOUS_MONTH: "Previous month",
    RANGE_LAST_N_DAYS: "Last N days",
}


def resolve_relative_range(
    range_key: str, *, days: int = 7, today: Optional[date] = None
) -> tuple[date, date]:
    """Resolve a relative range against the business calendar at run time."""
    anchor = today or business_today()
    key = (range_key or RANGE_LAST_30_DAYS).strip()
    if key == RANGE_TODAY:
        return anchor, anchor
    if key == RANGE_YESTERDAY:
        previous = anchor - timedelta(days=1)
        return previous, previous
    if key == RANGE_LAST_7_DAYS:
        return anchor - timedelta(days=6), anchor
    if key == RANGE_LAST_30_DAYS:
        return anchor - timedelta(days=29), anchor
    if key == RANGE_MONTH_TO_DATE:
        return anchor.replace(day=1), anchor
    if key == RANGE_PREVIOUS_MONTH:
        first_this_month = anchor.replace(day=1)
        last_prev = first_this_month - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if key == RANGE_LAST_N_DAYS:
        span = max(1, int(days or 1))
        return anchor - timedelta(days=span - 1), anchor
    return anchor - timedelta(days=29), anchor


@dataclass
class ReportContext:
    """Resolved inputs handed to a report runner."""

    domain: str
    report_id: str
    report_title: str = ""
    start: Optional[date] = None
    end: Optional[date] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    max_rows: int = 50000
    actor_id: str = ""
    dry_run: bool = False

    def option(self, key: str, default: Any = None) -> Any:
        return (self.filters or {}).get(key, default)

    def resolved_snapshot(self) -> Dict[str, Any]:
        return {
            "range_key": self.filters.get("range_key", ""),
            "range_days": self.filters.get("range_days", 0),
            "start": self.start.isoformat() if self.start else "",
            "end": self.end.isoformat() if self.end else "",
            **{
                k: v
                for k, v in (self.filters or {}).items()
                if k not in ("range_key", "range_days")
            },
        }


@dataclass
class ReportRunResult:
    rows: List[Dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    message: str = ""


class ScheduledReportRunner(Protocol):
    def run(self, ctx: ReportContext) -> ReportRunResult: ...


@dataclass
class ReportDefinition:
    """Catalog entry shown in the report picker."""

    domain: str
    report_id: str
    title: str
    category: str = ""
    supports_date_range: bool = True


@dataclass
class CallableReportRunner:
    """Adapts a plain callable into the runner protocol."""

    fn: Callable[[ReportContext], Any]

    def run(self, ctx: ReportContext) -> ReportRunResult:
        rows = self.fn(ctx)
        if isinstance(rows, ReportRunResult):
            return rows
        return ReportRunResult(rows=list(rows or []))


def slugify_report_id(title: str) -> str:
    """Stable snake_case id for title-keyed report catalogs."""
    out: List[str] = []
    previous_underscore = False
    for ch in (title or "").strip().lower():
        if ch.isalnum():
            out.append(ch)
            previous_underscore = False
        elif not previous_underscore:
            out.append("_")
            previous_underscore = True
    return "".join(out).strip("_")


def rows_to_csv(rows: List[Dict[str, Any]]) -> bytes:
    """Serialize dict rows to CSV using the union of keys as the header."""
    if not rows:
        return b""
    columns: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                columns.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: _csv_value(row.get(c)) for c in columns})
    return buffer.getvalue().encode("utf-8")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}={v}" for k, v in value.items())
    return value
