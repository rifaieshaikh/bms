from calendar import monthrange
from datetime import date

from vaybooks.bms.application.dtos import DashboardSummary
from vaybooks.bms.domain.shared.enums import OrderStatus
from vaybooks.bms.infrastructure.repositories.mongo_report_repository import MongoReportRepository


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

    def order_profitability_report(self) -> list:
        invoices = self._repo.get_all_invoices()
        return [
            {
                "order_number": inv.get("order_number"),
                "invoice_number": inv.get("invoice_number"),
                "bill_ids": ", ".join(inv.get("bill_ids", [])),
                "invoice_amount": inv.get("invoice_amount"),
                "total_expense_purchase": inv.get("total_expense_purchase_price"),
                "total_expense_selling": inv.get("total_expense_selling_price"),
                "margin_amount": inv.get("margin_amount"),
                "margin_per_hour": inv.get("margin_per_hour"),
            }
            for inv in invoices
        ]

    def activity_pending_report(self) -> list:
        orders = self._repo.get_all_orders()
        rows = []
        for order in orders:
            for act in order.get("order_activities", []):
                if act.get("is_required") and act.get("activity_status") in (
                    "Pending",
                    "In Progress",
                ):
                    bill_label = act.get("bill_id", "")[:8] if act.get("bill_id") else ""
                    rows.append(
                        {
                            "order_number": order.get("order_number"),
                            "customer_name": order.get("customer_name"),
                            "activity_name": act.get("activity_name"),
                            "bill_id": bill_label,
                            "activity_status": act.get("activity_status"),
                            "expected_delivery_date": order.get(
                                "expected_delivery_date"
                            ),
                        }
                    )
        return rows

    def time_tracking_report(self) -> list:
        entries = self._repo.get_all_time_entries()
        return [
            {
                "order_number": e.get("order_number"),
                "bill_number": e.get("bill_number"),
                "activity_name": e.get("activity_name"),
                "work_date": e.get("work_date"),
                "start_time": e.get("start_time"),
                "end_time": e.get("end_time"),
                "duration_minutes": e.get("duration_minutes"),
                "worker_name": e.get("worker_name"),
            }
            for e in entries
        ]

    def expense_report(self) -> list:
        expenses = self._repo.get_all_expenses()
        return [
            {
                "order_number": e.get("order_number"),
                "bill_number": e.get("bill_number"),
                "expense_name": e.get("expense_name"),
                "expense_source": e.get("expense_source"),
                "total_purchase_price": e.get("total_purchase_price"),
                "total_selling_price": e.get("total_selling_price"),
                "expense_date": e.get("expense_date"),
            }
            for e in expenses
        ]

    def mph_report(self) -> list:
        return self.order_profitability_report()

    def customer_order_history(self, customer_id: str) -> list:
        orders = self._repo.get_customer_orders(customer_id)
        return [
            {
                "order_number": o.get("order_number"),
                "order_date": o.get("order_date"),
                "order_status": o.get("order_status"),
                "expected_delivery_date": o.get("expected_delivery_date"),
                "advance_amount": o.get("advance_amount"),
            }
            for o in orders
        ]

    def overdue_order_report(self) -> list:
        today = date.today()
        orders = self._repo.get_overdue_orders(today)
        return [
            {
                "order_number": o.get("order_number"),
                "customer_name": o.get("customer_name"),
                "phone_number": o.get("phone_number"),
                "expected_delivery_date": o.get("expected_delivery_date"),
                "order_status": o.get("order_status"),
            }
            for o in orders
        ]

    def completed_order_report(self) -> list:
        orders = self._repo.get_orders_by_status(OrderStatus.COMPLETED.value)
        delivered = self._repo.get_orders_by_status(OrderStatus.DELIVERED.value)
        seen = set()
        rows = []
        for o in orders + delivered:
            oid = o.get("_id") or o.get("id")
            if oid in seen:
                continue
            seen.add(oid)
            rows.append(
                {
                    "order_number": o.get("order_number"),
                    "customer_name": o.get("customer_name"),
                    "order_status": o.get("order_status"),
                }
            )
        return rows

    def delivered_order_report(self) -> list:
        return self.completed_order_report()
