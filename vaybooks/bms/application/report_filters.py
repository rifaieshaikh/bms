"""Filter parameter objects for report queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    def token_part(self) -> str:
        return f"{self.start.isoformat()}_{self.end.isoformat()}"


@dataclass
class ItemProfitabilityFilter:
    date_range: DateRange
    customer_query: str = ""
    bill_query: str = ""
    min_mph: Optional[float] = None
    min_margin: Optional[float] = None


@dataclass
class OrderMphFilter:
    date_range: DateRange
    customer_query: str = ""
    min_mph: Optional[float] = None


@dataclass
class ActivityPendingFilter:
    etd_start: date
    etd_end: date
    statuses: list[str] = field(default_factory=lambda: ["Pending", "In Progress"])
    activity_names: list[str] = field(default_factory=list)
    customer_query: str = ""
    overdue_only: bool = False


@dataclass
class TimeTrackingFilter:
    date_range: DateRange
    worker: str = ""
    activity_name: str = ""
    search: str = ""


@dataclass
class ExpenseFilter:
    date_range: DateRange
    expense_source: str = ""
    search: str = ""
    min_amount: Optional[float] = None


@dataclass
class CustomerHistoryFilter:
    customer_id: str
    date_range: DateRange
    statuses: list[str] = field(default_factory=list)


@dataclass
class OverdueFilter:
    as_of_date: date
    min_days_overdue: int = 0
    statuses: list[str] = field(default_factory=list)
    customer_query: str = ""


@dataclass
class CompletedFilter:
    date_range: DateRange
    statuses: list[str] = field(
        default_factory=lambda: ["Completed", "Delivered"]
    )
    customer_query: str = ""
