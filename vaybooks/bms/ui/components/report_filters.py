"""Map committed filter-bar state to report service filter dataclasses."""

from __future__ import annotations

from datetime import date
from typing import Any

from vaybooks.bms.application.report_filters import (
    ActivityPendingFilter,
    BillsPendingFilter,
    CashMovementFilter,
    CompletedFilter,
    CustomerHistoryFilter,
    CustomerSegmentsFilter,
    DateRange,
    DeliveryPerformanceFilter,
    ExpenseBySourceFilter,
    ExpenseFilter,
    ItemProfitabilityFilter,
    LaborMphFilter,
    OrderMphFilter,
    OrderPipelineFilter,
    OutstandingFilter,
    OverdueFilter,
    PeriodSummaryFilter,
    TimeTrackingFilter,
    TopCustomersFilter,
    WorkerProductivityFilter,
)
from vaybooks.bms.domain.shared.enums import OrderStatus
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.report_schemas import SCHEMA_BY_REPORT_TYPE


def _text(value: Any) -> str:
    return (value or "").strip().lower()


def _optional_min(value: Any) -> float | None:
    try:
        val = float(value or 0)
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def _date_range(filters: dict, key: str = "date_range") -> DateRange:
    raw = filters.get(key)
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        start, end = raw
        if start and end and start > end:
            start, end = end, start
        return DateRange(start, end)
    today = date.today()
    return DateRange(today.replace(day=1), today)


def build_item_profitability_filter(filters: dict) -> ItemProfitabilityFilter:
    return ItemProfitabilityFilter(
        date_range=_date_range(filters),
        customer_query=_text(filters.get("customer_query")),
        bill_query=_text(filters.get("bill_query")),
        min_mph=_optional_min(filters.get("min_mph")),
        min_margin=_optional_min(filters.get("min_margin")),
    )


def build_order_mph_filter(filters: dict) -> OrderMphFilter:
    return OrderMphFilter(
        date_range=_date_range(filters),
        customer_query=_text(filters.get("customer_query")),
        min_mph=_optional_min(filters.get("min_mph")),
    )


def build_activity_pending_filter(filters: dict) -> ActivityPendingFilter:
    etd = _date_range(filters, "etd_range")
    statuses = filters.get("statuses") or ["Pending", "In Progress"]
    return ActivityPendingFilter(
        etd_start=etd.start,
        etd_end=etd.end,
        statuses=list(statuses),
        activity_names=list(filters.get("activity_names") or []),
        customer_query=_text(filters.get("customer_query")),
        overdue_only=bool(filters.get("overdue_only")),
    )


def build_time_tracking_filter(filters: dict) -> TimeTrackingFilter:
    return TimeTrackingFilter(
        date_range=_date_range(filters),
        worker=_text(filters.get("worker")),
        activity_name=(filters.get("activity_name") or "").strip(),
        search=_text(filters.get("search")),
    )


def build_expense_filter(filters: dict) -> ExpenseFilter:
    source = filters.get("expense_source") or ""
    return ExpenseFilter(
        date_range=_date_range(filters),
        expense_source=source if source else "",
        search=_text(filters.get("search")),
        min_amount=_optional_min(filters.get("min_amount")),
    )


def build_customer_history_filter(
    customer_id: str, filters: dict
) -> CustomerHistoryFilter:
    return CustomerHistoryFilter(
        customer_id=customer_id,
        date_range=_date_range(filters),
        statuses=list(filters.get("statuses") or []),
    )


def build_overdue_filter(filters: dict) -> OverdueFilter:
    as_of = filters.get("as_of_date") or date.today()
    try:
        min_days = int(filters.get("min_days_overdue") or 0)
    except (TypeError, ValueError):
        min_days = 0
    return OverdueFilter(
        as_of_date=as_of,
        min_days_overdue=max(0, min_days),
        statuses=list(filters.get("statuses") or []),
        customer_query=_text(filters.get("customer_query")),
    )


def build_completed_filter(filters: dict) -> CompletedFilter:
    statuses = filters.get("statuses") or [
        OrderStatus.COMPLETED.value,
        OrderStatus.DELIVERED.value,
    ]
    return CompletedFilter(
        date_range=_date_range(filters),
        statuses=list(statuses),
        customer_query=_text(filters.get("customer_query")),
    )


def build_period_summary_filter(filters: dict) -> PeriodSummaryFilter:
    return PeriodSummaryFilter(date_range=_date_range(filters))


def build_top_customers_filter(filters: dict) -> TopCustomersFilter:
    return TopCustomersFilter(
        date_range=_date_range(filters),
        min_revenue=_optional_min(filters.get("min_revenue")),
        min_margin=_optional_min(filters.get("min_margin")),
    )


def build_outstanding_filter(filters: dict) -> OutstandingFilter:
    return OutstandingFilter(
        min_balance=_optional_min(filters.get("min_balance")),
        search=_text(filters.get("search")),
    )


def build_cash_movement_filter(filters: dict) -> CashMovementFilter:
    return CashMovementFilter(date_range=_date_range(filters))


def build_expense_by_source_filter(filters: dict) -> ExpenseBySourceFilter:
    return ExpenseBySourceFilter(date_range=_date_range(filters))


def build_customer_segments_filter(filters: dict) -> CustomerSegmentsFilter:
    return CustomerSegmentsFilter(date_range=_date_range(filters))


def build_order_pipeline_filter(filters: dict) -> OrderPipelineFilter:
    return OrderPipelineFilter(statuses=list(filters.get("statuses") or []))


def build_bills_pending_filter(filters: dict) -> BillsPendingFilter:
    return BillsPendingFilter(customer_query=_text(filters.get("customer_query")))


def build_delivery_performance_filter(filters: dict) -> DeliveryPerformanceFilter:
    return DeliveryPerformanceFilter(
        date_range=_date_range(filters),
        customer_query=_text(filters.get("customer_query")),
        on_time_only=bool(filters.get("on_time_only")),
        late_only=bool(filters.get("late_only")),
    )


def build_worker_productivity_filter(filters: dict) -> WorkerProductivityFilter:
    return WorkerProductivityFilter(
        date_range=_date_range(filters),
        worker=_text(filters.get("worker")),
        min_hours=_optional_min(filters.get("min_hours")),
    )


def build_labor_mph_filter(filters: dict) -> LaborMphFilter:
    return LaborMphFilter(
        date_range=_date_range(filters),
        min_hours=_optional_min(filters.get("min_hours")),
    )


_BUILDERS = {
    "report_item_profitability": build_item_profitability_filter,
    "report_order_mph": build_order_mph_filter,
    "report_activity_pending": build_activity_pending_filter,
    "report_activity_bottleneck": build_activity_pending_filter,
    "report_time_tracking": build_time_tracking_filter,
    "report_expense_detail": build_expense_filter,
    "report_overdue": build_overdue_filter,
    "report_completed": build_completed_filter,
    "report_period_financial": build_period_summary_filter,
    "report_top_customers_revenue": build_top_customers_filter,
    "report_top_customers_margin": build_top_customers_filter,
    "report_customer_outstanding": build_outstanding_filter,
    "report_vendor_payables": build_outstanding_filter,
    "report_cash_movement": build_cash_movement_filter,
    "report_expense_by_source": build_expense_by_source_filter,
    "report_customer_segments": build_customer_segments_filter,
    "report_order_pipeline": build_order_pipeline_filter,
    "report_bills_pending": build_bills_pending_filter,
    "report_delivery_performance": build_delivery_performance_filter,
    "report_worker_productivity": build_worker_productivity_filter,
    "report_labor_vs_mph": build_labor_mph_filter,
}


def build_report_filter(report_type: str, filters: dict, **kwargs):
    """Build a service-layer filter object from committed bar state."""
    schema = SCHEMA_BY_REPORT_TYPE[report_type]
    if schema.entity_key == "report_customer_history":
        return build_customer_history_filter(kwargs["customer_id"], filters)
    builder = _BUILDERS[schema.entity_key]
    return builder(filters)


def report_filter_token(report_type: str, filters: dict, sort: dict, **kwargs) -> str:
    schema = SCHEMA_BY_REPORT_TYPE[report_type]
    token = F.filter_token(schema, filters, sort)
    if kwargs.get("customer_id"):
        token = f"{token}|customer={kwargs['customer_id']}"
    return token
