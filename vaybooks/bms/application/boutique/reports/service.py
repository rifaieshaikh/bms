"""Boutique module report queries for the Boutique Overview and Reports pages.

Thin facade over the shared operations and labor report services so the Boutique
menu gets its own Overview + Reports surface without duplicating query logic.
Overview KPIs additionally read boutique orders, invoices, and deliveries for
pending-delivery and period-revenue metrics.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from vaybooks.bms.application.finance.reports.services.labor_report_service import (
    LaborReportService,
)
from vaybooks.bms.application.finance.reports.services.operations_report_service import (
    OperationsReportService,
)
from vaybooks.bms.application.report_filters import (
    BillsPendingFilter,
    DateRange,
    DeliveryPerformanceFilter,
    OrderPipelineFilter,
    OverdueFilter,
    TimeTrackingFilter,
    WorkerProductivityFilter,
)
from vaybooks.bms.domain.boutique.orders.bill_status import (
    count_bills_pending_delivery,
    count_bills_pending_invoice,
)
from vaybooks.bms.domain.shared.date_utils import minutes_to_hours
from vaybooks.bms.domain.shared.enums import OrderStatus

_OPEN_EXCLUDED = {
    OrderStatus.DELIVERED.value,
    OrderStatus.COMPLETED.value,
    OrderStatus.CANCELLED.value,
}


def _status_value(status) -> str:
    return getattr(status, "value", status)


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def _period_key(d: date, grain: str) -> str:
    if grain == "week":
        monday = d - timedelta(days=d.weekday())
        return monday.isoformat()
    if grain == "month":
        return f"{d.year:04d}-{d.month:02d}"
    return d.isoformat()


class BoutiqueModuleReportService:
    """Report facade for the Boutique module Overview and Reports pages."""

    def __init__(
        self,
        operations: OperationsReportService,
        labor: LaborReportService,
        order_repo,
        invoice_repo,
        delivery_repo,
    ):
        self._ops = operations
        self._labor = labor
        self._order_repo = order_repo
        self._invoice_repo = invoice_repo
        self._delivery_repo = delivery_repo

    # --- Report loaders (accept schema-built filter objects) ---

    def order_pipeline_report(self, filters=None) -> list:
        return self._ops.order_pipeline_report(filters or OrderPipelineFilter())

    def overdue_order_report(self, filters=None) -> list:
        return self._ops.overdue_order_report(
            filters or OverdueFilter(as_of_date=date.today())
        )

    def bills_pending_invoice_report(self, filters=None) -> list:
        return self._ops.bills_pending_invoice_report(
            filters or BillsPendingFilter()
        )

    def activity_pending_report(self, filters) -> list:
        return self._ops.activity_pending_report(filters)

    def activity_bottleneck_report(self, filters) -> list:
        return self._ops.activity_bottleneck_report(filters)

    def delivery_performance_report(self, filters) -> list:
        return self._ops.delivery_performance_report(filters)

    def completed_order_report(self, filters) -> list:
        return self._ops.completed_order_report(filters)

    def time_tracking_report(self, filters) -> list:
        return self._labor.time_tracking_report(filters)

    def worker_productivity_report(self, filters) -> list:
        return self._labor.worker_productivity_report(filters)

    def labor_vs_mph_report(self, filters) -> list:
        return self._labor.labor_vs_mph_report(filters)

    # --- Overview helpers ---

    def status_breakdown(self) -> list[dict]:
        rows = self._ops.order_pipeline_report(OrderPipelineFilter())
        return [
            {
                "status": _status_value(r.get("order_status")),
                "count": int(r.get("order_count") or 0),
            }
            for r in rows
        ]

    def overdue_count(self) -> int:
        return len(self.overdue_order_report())

    def overdue_queue(self, limit: int = 8) -> list[dict]:
        """Active overdue orders (ETD past, not delivered/completed), with id."""
        today = date.today()
        rows = []
        for order in self._order_repo.list_all():
            if _status_value(order.order_status) in _OPEN_EXCLUDED:
                continue
            etd = _as_date(order.expected_delivery_date)
            if not etd or etd >= today:
                continue
            rows.append(
                {
                    "id": order.id,
                    "order_number": order.order_number,
                    "customer_name": order.customer_name,
                    "expected_delivery_date": etd,
                    "days_overdue": (today - etd).days,
                }
            )
        rows.sort(key=lambda r: r["days_overdue"], reverse=True)
        return rows[:limit] if limit else rows

    def bills_pending_invoice_queue(self, limit: int = 8) -> list[dict]:
        """Orders with bills not yet invoiced, with id for deep-linking."""
        by_order: dict[str, list] = {}
        for inv in self._invoice_repo.list_all():
            by_order.setdefault(inv.order_id, []).append(inv)
        rows = []
        for order in self._order_repo.list_all():
            if _status_value(order.order_status) == OrderStatus.CANCELLED.value:
                continue
            pending = count_bills_pending_invoice(
                order, by_order.get(order.id, [])
            )
            if pending <= 0:
                continue
            rows.append(
                {
                    "id": order.id,
                    "order_number": order.order_number,
                    "customer_name": order.customer_name,
                    "pending_bills": pending,
                }
            )
        rows.sort(key=lambda r: r["pending_bills"], reverse=True)
        return rows[:limit] if limit else rows

    def _bills_pending_delivery(self) -> int:
        deliveries = self._delivery_repo.list_all()
        by_order: dict[str, list] = {}
        for d in deliveries:
            by_order.setdefault(d.order_id, []).append(d)
        total = 0
        for order in self._order_repo.list_all():
            if _status_value(order.order_status) == OrderStatus.CANCELLED.value:
                continue
            total += count_bills_pending_delivery(
                order, by_order.get(order.id, [])
            )
        return total

    def _invoiced_revenue(self, start: date, end: date) -> float:
        total = 0.0
        for inv in self._invoice_repo.list_all():
            if inv.is_cancellation:
                continue
            idate = _as_date(inv.invoice_date)
            if idate and start <= idate <= end:
                total += float(inv.net_amount or 0)
        return round(total, 2)

    def dashboard_summary(self, start: date, end: date) -> dict:
        pipeline = self._ops.order_pipeline_report(OrderPipelineFilter())
        open_orders = sum(
            int(r.get("order_count") or 0)
            for r in pipeline
            if _status_value(r.get("order_status")) not in _OPEN_EXCLUDED
        )
        hours = self._labor.labor_hours_by_order(start, end)
        return {
            "open_orders": open_orders,
            "overdue_orders": self.overdue_count(),
            "bills_pending_invoice": len(self.bills_pending_invoice_report()),
            "bills_pending_delivery": self._bills_pending_delivery(),
            "invoiced_revenue": self._invoiced_revenue(start, end),
            "hours_logged": round(sum(hours.values()), 2),
        }

    def _order_customer_map(self) -> dict[str, str]:
        return {
            order.id: order.customer_name or "Unknown"
            for order in self._order_repo.list_all()
        }

    def invoiced_revenue_series(
        self, start: date, end: date, grain: str = "day"
    ) -> list[dict]:
        if grain not in ("day", "week", "month"):
            grain = "day"
        totals: dict[str, float] = defaultdict(float)
        for inv in self._invoice_repo.list_all():
            if inv.is_cancellation:
                continue
            idate = _as_date(inv.invoice_date)
            if not idate or idate < start or idate > end:
                continue
            totals[_period_key(idate, grain)] += float(inv.net_amount or 0)
        return [
            {"period": period, "amount": round(amount, 2)}
            for period, amount in sorted(totals.items())
        ]

    def hours_logged_series(
        self, start: date, end: date, grain: str = "day"
    ) -> list[dict]:
        if grain not in ("day", "week", "month"):
            grain = "day"
        entries = self._labor.time_tracking_report(
            TimeTrackingFilter(date_range=DateRange(start=start, end=end))
        )
        totals: dict[str, float] = defaultdict(float)
        for row in entries:
            wd = _as_date(row.get("work_date"))
            if not wd or wd < start or wd > end:
                continue
            totals[_period_key(wd, grain)] += minutes_to_hours(
                int(row.get("duration_minutes") or 0)
            )
        return [
            {"period": period, "hours": round(hours, 2)}
            for period, hours in sorted(totals.items())
        ]

    def top_customers_by_revenue(
        self, start: date, end: date, limit: int = 10
    ) -> list[dict]:
        customers = self._order_customer_map()
        totals: dict[str, float] = defaultdict(float)
        for inv in self._invoice_repo.list_all():
            if inv.is_cancellation:
                continue
            idate = _as_date(inv.invoice_date)
            if not idate or idate < start or idate > end:
                continue
            name = customers.get(inv.order_id) or "Unknown"
            totals[name] += float(inv.net_amount or 0)
        ranked = sorted(totals.items(), key=lambda r: r[1], reverse=True)
        if limit > 0:
            ranked = ranked[:limit]
        return [
            {"customer_name": name, "total_revenue": round(amount, 2)}
            for name, amount in ranked
        ]

    def hours_by_worker(
        self, start: date, end: date, limit: int = 10
    ) -> list[dict]:
        rows = self._labor.worker_productivity_report(
            WorkerProductivityFilter(date_range=DateRange(start=start, end=end))
        )
        ranked = sorted(
            rows, key=lambda r: float(r.get("total_hours") or 0), reverse=True
        )
        if limit > 0:
            ranked = ranked[:limit]
        return [
            {
                "worker_name": r.get("worker_name") or "Unknown",
                "total_hours": float(r.get("total_hours") or 0),
            }
            for r in ranked
        ]

    def delivery_on_time_breakdown(
        self, start: date, end: date
    ) -> list[dict]:
        rows = self._ops.delivery_performance_report(
            DeliveryPerformanceFilter(
                date_range=DateRange(start=start, end=end)
            )
        )
        on_time = sum(1 for r in rows if r.get("on_time") == "Yes")
        late = sum(1 for r in rows if r.get("on_time") != "Yes")
        result = []
        if on_time:
            result.append({"outcome": "On time", "count": on_time})
        if late:
            result.append({"outcome": "Late", "count": late})
        return result
