"""Build period summary dict from report repository."""

from __future__ import annotations

from datetime import date
from typing import Any

from vaybooks.bms.domain.shared.date_utils import minutes_to_hours
from vaybooks.bms.domain.shared.enums import OrderStatus, VoucherType
from vaybooks.bms.infrastructure.repositories.mongo_report_repository import (
    MongoReportRepository,
)


def build_period_summary(
    repo: MongoReportRepository, start: date, end: date
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "order_count": 0,
        "revenue": 0,
        "total_revenue": 0,
        "expenses": 0,
        "mph": None,
    }
    item_snapshot = repo.item_delivery_snapshot()
    order_count = repo.count_orders_created(start, end)
    total_revenue = repo.get_monthly_invoice_total(start, end)
    expenses = repo.sum_expenses_total(start, end)
    today = date.today()
    active_statuses = [
        OrderStatus.IN_PROGRESS.value,
        OrderStatus.READY_FOR_DELIVERY.value,
        OrderStatus.INVOICE_GENERATED.value,
    ]
    completed_statuses = [
        OrderStatus.COMPLETED.value,
        OrderStatus.DELIVERED.value,
    ]
    time_entries = repo.get_time_entries(start, end)
    stitching_mins = sum(
        int(e.get("duration_minutes") or 0)
        for e in time_entries
        if e.get("activity_name") == "Stitching"
    )
    hand_mins = sum(
        int(e.get("duration_minutes") or 0)
        for e in time_entries
        if e.get("activity_name") == "Hand Work"
    )
    summary.update(
        {
            "orders_created": order_count,
            "order_count": order_count,
            "customers_created": repo.count_customers_created(start, end),
            "customers_with_orders": repo.count_distinct_customers_with_orders(
                start, end
            ),
            "repeat_customers": repo.count_repeat_customers_with_orders(start, end),
            "customers_invoiced": repo.count_distinct_customers_invoiced(start, end),
            "delivered": repo.count_delivered_this_month(start, end),
            "completed_orders": len(
                repo.get_completed_orders(start, end, completed_statuses)
            ),
            "pending_activities": repo.get_pending_activities_count(),
            "bills_pending_invoice": repo.get_bills_pending_invoice_count(),
            "items_created": repo.count_items_created(start, end),
            "items_delivered": repo.count_items_delivered(start, end),
            "items_pending": item_snapshot["not_delivered"],
            "items_awaiting_delivery": item_snapshot["awaiting"],
            "invoiced": total_revenue,
            "revenue": total_revenue,
            "total_revenue": total_revenue,
            "receipts": repo.get_monthly_advance_total(start, end),
            "expenses": expenses,
            "gross_margin": repo.sum_invoice_margin(start, end),
            "vendor_payments": repo.sum_payment_voucher_amount(
                VoucherType.VENDOR_PAYMENT.value, start, end
            ),
            "salary_payments": repo.sum_payment_voucher_amount(
                VoucherType.SALARY_PAYMENT.value, start, end
            ),
            "active_orders": repo.count_orders_by_statuses(
                active_statuses + [OrderStatus.COMPLETED.value]
            ),
            "in_progress_orders": repo.count_orders_by_statuses(active_statuses),
            "overdue_orders": len(repo.get_overdue_orders(today)),
            "etd_today": len(repo.get_etd_today(today)),
            "stitching_hours": minutes_to_hours(stitching_mins),
            "hand_work_hours": minutes_to_hours(hand_mins),
            "total_time_hours": minutes_to_hours(stitching_mins + hand_mins),
            "time_entry_count": len(time_entries),
        }
    )
    return summary
