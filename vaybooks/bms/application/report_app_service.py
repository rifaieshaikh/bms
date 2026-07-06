from calendar import monthrange

from datetime import date, datetime

from typing import Any



from vaybooks.bms.application.dtos import DashboardSummary

from vaybooks.bms.application.report_filters import (
    ActivityPendingFilter,
    CompletedFilter,
    CustomerHistoryFilter,
    DateRange,
    ExpenseFilter,
    ItemProfitabilityFilter,
    OrderMphFilter,
    OverdueFilter,
    TimeTrackingFilter,
)

from vaybooks.bms.domain.shared.enums import OrderStatus, VoucherType

from vaybooks.bms.infrastructure.db.bson_utils import as_date
from vaybooks.bms.infrastructure.repositories.mongo_report_repository import MongoReportRepository


def _matches_search(row: dict, query: str, *fields: str) -> bool:
    if not query:
        return True
    for field in fields:
        val = row.get(field)
        if val is not None and query in str(val).lower():
            return True
    return False


_as_date = as_date


class ReportAppService:

    def __init__(self, report_repo: MongoReportRepository):

        self._repo = report_repo



    def get_dashboard_summary(self) -> DashboardSummary:

        today = date.today()

        start = today.replace(day=1)

        _, last_day = monthrange(today.year, today.month)

        end = today.replace(day=last_day)



        active_statuses = [

            OrderStatus.IN_PROGRESS.value,

            OrderStatus.READY_FOR_DELIVERY.value,

            OrderStatus.INVOICE_GENERATED.value,

        ]

        active = self._repo.count_orders_by_statuses(

            active_statuses + [OrderStatus.COMPLETED.value]

        )

        pending_activity_orders = self._repo.count_orders_by_statuses(active_statuses)

        in_progress = self._repo.get_orders_by_statuses(active_statuses, limit=60)



        return DashboardSummary(

            active_orders=active,

            pending_activity_orders=pending_activity_orders,

            ready_for_delivery=0,

            invoice_generated=0,

            completed_orders=self._repo.count_orders_by_status(

                OrderStatus.COMPLETED.value

            ),

            delivered_this_month=self._repo.count_delivered_this_month(start, end),

            total_advance_this_month=self._repo.get_monthly_advance_total(

                start, end

            ),

            total_invoice_this_month=self._repo.get_monthly_invoice_total(

                start, end

            ),

            total_pending_activities=self._repo.get_pending_activities_count(),

            bills_pending_invoice=self._repo.get_bills_pending_invoice_count(),

            etd_today=self._repo.get_etd_today(today),

            overdue_orders=self._repo.get_overdue_orders(today),

            ready_orders=[],

            in_progress_orders=in_progress,

            recently_completed=self._repo.get_orders_by_status(

                OrderStatus.COMPLETED.value, limit=20

            ),

            recently_delivered=self._repo.get_delivered_this_month(start, end),

        )



    def get_period_summary(self, start: date, end: date) -> dict:

        """Operational + financial metrics for an arbitrary date range (MTD)."""

        item_snapshot = self._repo.item_delivery_snapshot()

        return {

            "orders_created": self._repo.count_orders_created(start, end),

            "delivered": self._repo.count_delivered_this_month(start, end),

            "pending_activities": self._repo.get_pending_activities_count(),

            "bills_pending_invoice": self._repo.get_bills_pending_invoice_count(),

            "items_created": self._repo.count_items_created(start, end),

            "items_delivered": self._repo.count_items_delivered(start, end),

            "items_pending": item_snapshot["not_delivered"],

            "items_awaiting_delivery": item_snapshot["awaiting"],

            "invoiced": self._repo.get_monthly_invoice_total(start, end),

            "receipts": self._repo.get_monthly_advance_total(start, end),

            "expenses": self._repo.sum_expenses_total(start, end),

            "gross_margin": self._repo.sum_invoice_margin(start, end),

            "vendor_payments": self._repo.sum_payment_voucher_amount(

                VoucherType.VENDOR_PAYMENT.value, start, end

            ),

            "salary_payments": self._repo.sum_payment_voucher_amount(

                VoucherType.SALARY_PAYMENT.value, start, end

            ),

        }



    def item_profitability_report(self, filters: ItemProfitabilityFilter) -> list:

        """Item-wise profitability: one row per delivered + invoiced item."""

        items = self._repo.get_item_profitability(

            filters.date_range.start, filters.date_range.end

        )

        rows = []

        for it in items:

            row = {

                "order_number": it.get("order_number"),

                "customer_name": it.get("customer_name"),

                "bill_number": it.get("bill_number"),

                "description": it.get("description"),

                "revenue_net": it.get("sell_amount"),

                "expense_selling": it.get("expense_selling_total"),

                "expense_purchase": it.get("expense_purchase_total"),

                "in_house_hours": it.get("in_house_hours"),

                "margin_amount": it.get("margin_amount"),

                "margin_per_hour": it.get("margin_per_hour"),

                "delivered_on": _as_date(it.get("delivered_on")),

            }

            if not _matches_search(

                row, filters.customer_query, "customer_name"

            ):

                continue

            if not _matches_search(

                row, filters.bill_query, "bill_number", "order_number"

            ):

                continue

            mph = row.get("margin_per_hour")

            if filters.min_mph is not None and (mph is None or mph < filters.min_mph):

                continue

            margin = row.get("margin_amount") or 0

            if filters.min_margin is not None and margin < filters.min_margin:

                continue

            rows.append(row)

        return rows



    def mph_report(self, filters: OrderMphFilter) -> list:

        """Order-level MPH: sum margin and hours across items, then divide."""

        items = self._repo.get_item_profitability(

            filters.date_range.start, filters.date_range.end

        )

        by_order: dict[str, dict] = {}

        for it in items:

            order_no = it.get("order_number") or ""

            if filters.customer_query:

                customer = (it.get("customer_name") or "").lower()

                if filters.customer_query not in customer:

                    continue

            bucket = by_order.setdefault(

                order_no,

                {

                    "order_number": order_no,

                    "customer_name": it.get("customer_name"),

                    "item_count": 0,

                    "total_margin": 0.0,

                    "total_hours": 0.0,

                    "delivered_through": None,

                },

            )

            bucket["item_count"] += 1

            bucket["total_margin"] += float(it.get("margin_amount") or 0)

            bucket["total_hours"] += float(it.get("in_house_hours") or 0)

            snap = _as_date(it.get("delivered_on"))

            if snap and (

                bucket["delivered_through"] is None

                or snap > bucket["delivered_through"]

            ):

                bucket["delivered_through"] = snap



        rows = []

        for bucket in by_order.values():

            hours = bucket["total_hours"]

            mph = round(bucket["total_margin"] / hours, 2) if hours > 0 else None

            if filters.min_mph is not None and (mph is None or mph < filters.min_mph):

                continue

            rows.append(

                {

                    **bucket,

                    "total_margin": round(bucket["total_margin"], 2),

                    "total_hours": round(hours, 2),

                    "margin_per_hour": mph,

                }

            )

        rows.sort(key=lambda r: r.get("margin_per_hour") or 0, reverse=True)

        return rows



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

            if filters.customer_query:

                if not _matches_search(

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



    def time_tracking_report(self, filters: TimeTrackingFilter) -> list:

        entries = self._repo.get_time_entries(

            filters.date_range.start,

            filters.date_range.end,

            worker=filters.worker or None,

            activity_name=filters.activity_name or None,

        )

        rows = []

        for e in entries:

            row = {

                "order_number": e.get("order_number"),

                "bill_number": e.get("bill_number"),

                "activity_name": e.get("activity_name"),

                "work_date": _as_date(e.get("work_date")),

                "start_time": e.get("start_time"),

                "end_time": e.get("end_time"),

                "duration_minutes": e.get("duration_minutes"),

                "worker_name": e.get("worker_name"),

            }

            if not _matches_search(

                row, filters.search, "order_number", "bill_number"

            ):

                continue

            rows.append(row)

        return rows



    def expense_report(self, filters: ExpenseFilter) -> list:

        expenses = self._repo.get_expenses(

            filters.date_range.start,

            filters.date_range.end,

            expense_source=filters.expense_source or None,

        )

        rows = []

        for e in expenses:

            amount = float(e.get("total_purchase_price") or 0)

            if filters.min_amount is not None and amount < filters.min_amount:

                continue

            row = {

                "order_number": e.get("order_number"),

                "bill_number": e.get("bill_number"),

                "expense_name": e.get("expense_name"),

                "expense_source": e.get("expense_source"),

                "total_purchase_price": amount,

                "total_selling_price": e.get("total_selling_price"),

                "expense_date": _as_date(e.get("expense_date")),

            }

            if not _matches_search(

                row, filters.search, "order_number", "bill_number", "expense_name"

            ):

                continue

            rows.append(row)

        return rows



    def customer_order_history(self, filters: CustomerHistoryFilter) -> list:

        orders = self._repo.get_customer_orders(

            filters.customer_id,

            filters.date_range.start,

            filters.date_range.end,

        )

        rows = []

        for o in orders:

            status = o.get("order_status")

            if filters.statuses and status not in filters.statuses:

                continue

            rows.append(

                {

                    "order_number": o.get("order_number"),

                    "order_date": _as_date(o.get("order_date")),

                    "order_status": status,

                    "expected_delivery_date": _as_date(

                        o.get("expected_delivery_date")

                    ),

                    "advance_amount": o.get("advance_amount"),

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

            if filters.customer_query and not _matches_search(

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

            if filters.customer_query and not _matches_search(

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



    def delivered_order_report(self, filters: CompletedFilter) -> list:

        return self.completed_order_report(filters)



    # Backward-compatible aliases for callers without filters

    def order_profitability_report(self) -> list:
        today = date.today()
        return self.item_profitability_report(
            ItemProfitabilityFilter(date_range=DateRange(today.replace(day=1), today))
        )


