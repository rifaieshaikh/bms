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


@dataclass
class PeriodSummaryFilter:
    date_range: DateRange


@dataclass
class TopCustomersFilter:
    date_range: DateRange
    min_revenue: Optional[float] = None
    min_margin: Optional[float] = None


@dataclass
class OutstandingFilter:
    min_balance: Optional[float] = None
    search: str = ""


@dataclass
class CashMovementFilter:
    date_range: DateRange


@dataclass
class ExpenseBySourceFilter:
    date_range: DateRange


@dataclass
class CustomerSegmentsFilter:
    date_range: DateRange


@dataclass
class OrderPipelineFilter:
    statuses: list[str] = field(default_factory=list)


@dataclass
class BillsPendingFilter:
    customer_query: str = ""


@dataclass
class DeliveryPerformanceFilter:
    date_range: DateRange
    customer_query: str = ""
    on_time_only: bool = False
    late_only: bool = False


@dataclass
class WorkerProductivityFilter:
    date_range: DateRange
    worker: str = ""
    min_hours: Optional[float] = None


@dataclass
class LaborMphFilter:
    date_range: DateRange
    min_hours: Optional[float] = None


@dataclass
class StockOnHandFilter:
    category_id: str = ""
    active_only: bool = True
    min_qty: Optional[float] = None
    search: str = ""


@dataclass
class LowStockFilter:
    threshold: float = 2.0
    category_id: str = ""
    include_out_of_stock: bool = True


@dataclass
class StockMovementsFilter:
    date_range: DateRange
    product_id: str = ""
    category_id: str = ""
    movement_type: str = ""


@dataclass
class DeadStockFilter:
    date_range: DateRange
    category_id: str = ""
    min_qty: float = 0.0
    max_qty_out: float = 0.0


@dataclass
class OpeningClosingStockFilter:
    date_range: DateRange
    category_id: str = ""
    product_id: str = ""
    active_only: bool = True


@dataclass
class FastMovingStockFilter:
    date_range: DateRange
    category_id: str = ""
    min_qty_out: float = 0.0


@dataclass
class CustomerLatestPricesFilter:
    customer_id: str = ""
    search: str = ""
    date_range: DateRange | None = None


@dataclass
class PurchasesByVendorFilter:
    date_range: DateRange | None = None
