from __future__ import annotations

from datetime import date

from vaybooks.bms.application.report_filters import (
    ActivityPendingFilter,
    BillsPendingFilter,
    CompletedFilter,
    DeliveryPerformanceFilter,
    OrderPipelineFilter,
    OverdueFilter,
)
from vaybooks.bms.application.finance.reports.services._helpers import _as_date, matches_search
from vaybooks.bms.domain.shared.enums import OrderStatus
from vaybooks.bms.infrastructure.db.bson_utils import as_date
from vaybooks.bms.infrastructure.repositories.finance.mongo_report_repository import (
    MongoReportRepository,
)


class OperationsReportService:
    def __init__(self, report_repo: MongoReportRepository):
        self._repo = report_repo

    def activity_pending_report(self, filters: ActivityPendingFilter) -> list:
        today = date.today()
        etd_start = as_date(filters.etd_start)
        etd_end = as_date(filters.etd_end)
        orders = self._repo.get_orders_for_activity_pending()
        rows = []
        for order in orders:
            etd = as_date(order.get("expected_delivery_date"))
            if etd is not None and etd_start is not None and etd_end is not None:
                if etd < etd_start or etd > etd_end:
                    continue
            if filters.overdue_only and (etd is None or etd >= today):
                continue
            if filters.customer_query and not matches_search(
                order,
                filters.customer_query,
                "customer_name",
                "order_number",
            ):
                continue
            for act in order.get("order_activities", []):
                if not act.get("is_required"):
                    continue
                status = act.get("activity_status")
                if status not in filters.statuses:
                    continue
                name = act.get("activity_name") or ""
                if filters.activity_names and name not in filters.activity_names:
                    continue
                bill_label = act.get("bill_id", "")[:8] if act.get("bill_id") else ""
                rows.append(
                    {
                        "order_number": order.get("order_number"),
                        "customer_name": order.get("customer_name"),
                        "activity_name": name,
                        "bill_id": bill_label,
                        "activity_status": status,
                        "expected_delivery_date": etd,
                    }
                )
        return rows

    def overdue_order_report(self, filters: OverdueFilter) -> list:
        orders = self._repo.get_overdue_orders(filters.as_of_date)
        rows = []
        for o in orders:
            status = o.get("order_status")
            if filters.statuses and status not in filters.statuses:
                continue
            if filters.customer_query and not matches_search(
                o,
                filters.customer_query,
                "customer_name",
                "phone_number",
                "order_number",
            ):
                continue
            etd = _as_date(o.get("expected_delivery_date"))
            days_overdue = (filters.as_of_date - etd).days if etd else 0
            if days_overdue < filters.min_days_overdue:
                continue
            rows.append(
                {
                    "order_number": o.get("order_number"),
                    "customer_name": o.get("customer_name"),
                    "phone_number": o.get("phone_number"),
                    "expected_delivery_date": etd,
                    "days_overdue": days_overdue,
                    "order_status": status,
                }
            )
        return rows

    def completed_order_report(self, filters: CompletedFilter) -> list:
        orders = self._repo.get_completed_orders(
            filters.date_range.start,
            filters.date_range.end,
            filters.statuses,
        )
        rows = []
        for o in orders:
            if filters.customer_query and not matches_search(
                o, filters.customer_query, "customer_name"
            ):
                continue
            rows.append(
                {
                    "order_number": o.get("order_number"),
                    "customer_name": o.get("customer_name"),
                    "order_status": o.get("order_status"),
                    "order_date": _as_date(o.get("order_date")),
                    "delivery_date": _as_date(o.get("delivery_date")),
                    "expected_delivery_date": _as_date(
                        o.get("expected_delivery_date")
                    ),
                }
            )
        return rows

    def order_pipeline_report(self, filters: OrderPipelineFilter) -> list:
        rows = self._repo.get_orders_pipeline_snapshot()
        if filters.statuses:
            rows = [r for r in rows if r.get("order_status") in filters.statuses]
        return rows

    def bills_pending_invoice_report(self, filters: BillsPendingFilter) -> list:
        rows = self._repo.get_bills_pending_invoice_rows()
        if filters.customer_query:
            rows = [
                r
                for r in rows
                if matches_search(
                    r, filters.customer_query, "customer_name", "order_number"
                )
            ]
        return rows

    def activity_bottleneck_report(self, filters: ActivityPendingFilter) -> list:
        pending = self.activity_pending_report(filters)
        today = date.today()
        by_activity: dict[str, dict] = {}
        for row in pending:
            name = row.get("activity_name") or "Unknown"
            bucket = by_activity.setdefault(
                name,
                {"activity_name": name, "pending_count": 0, "overdue_count": 0},
            )
            bucket["pending_count"] += 1
            etd = row.get("expected_delivery_date")
            if etd and etd < today:
                bucket["overdue_count"] += 1
        return list(by_activity.values())

    def delivery_performance_report(
        self, filters: DeliveryPerformanceFilter
    ) -> list:
        completed = self.completed_order_report(
            CompletedFilter(
                date_range=filters.date_range,
                statuses=[
                    OrderStatus.COMPLETED.value,
                    OrderStatus.DELIVERED.value,
                ],
                customer_query=filters.customer_query,
            )
        )
        rows = []
        for o in completed:
            etd = o.get("expected_delivery_date")
            delivered = o.get("delivery_date")
            if not delivered:
                continue
            days_variance = (delivered - etd).days if etd else None
            on_time = days_variance is not None and days_variance <= 0
            if filters.on_time_only and not on_time:
                continue
            if filters.late_only and on_time:
                continue
            rows.append(
                {
                    **o,
                    "days_variance": days_variance,
                    "on_time": "Yes" if on_time else "No",
                }
            )
        return rows
