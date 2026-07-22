"""Shared helpers for report category services."""

from __future__ import annotations

from vaybooks.bms.infrastructure.db.bson_utils import as_date

_as_date = as_date


def matches_search(row: dict, query: str, *fields: str) -> bool:
    if not query:
        return True
    for field in fields:
        val = row.get(field)
        if val is not None and query in str(val).lower():
            return True
    return False


def passes_min_mph(mph: float | None, min_mph: float) -> bool:
    if mph is None:
        return False
    return round(mph, 2) >= min_mph


def flatten_period_summary(summary: dict) -> list[dict]:
    """Turn period summary dict into sortable metric rows."""
    labels = {
        "orders_created": "Orders created",
        "delivered": "Orders delivered",
        "completed_orders": "Orders completed",
        "customers_created": "New customers",
        "customers_with_orders": "Customers with orders",
        "repeat_customers": "Repeat customers",
        "customers_invoiced": "Customers invoiced",
        "items_created": "Items created",
        "items_delivered": "Items delivered",
        "items_pending": "Items pending",
        "items_awaiting_delivery": "Items awaiting delivery",
        "invoiced": "Invoiced",
        "receipts": "Receipts",
        "expenses": "Expenses",
        "gross_margin": "Gross margin",
        "vendor_payments": "Vendor payments",
        "salary_payments": "Salary payments",
        "pending_activities": "Pending activities",
        "bills_pending_invoice": "Bills pending invoice",
        "active_orders": "Active orders",
        "in_progress_orders": "In progress orders",
        "overdue_orders": "Overdue orders",
        "etd_today": "ETD today",
        "stitching_hours": "Stitching hours",
        "hand_work_hours": "Hand work hours",
        "total_time_hours": "Total time hours",
        "time_entry_count": "Time entries",
    }
    rows = []
    for key, label in labels.items():
        if key not in summary:
            continue
        val = summary[key]
        if isinstance(val, float):
            display = f"₹{val:,.0f}" if key in {
                "invoiced", "receipts", "expenses", "gross_margin",
                "vendor_payments", "salary_payments",
            } else f"{val:,.2f}"
        else:
            display = val
        rows.append({"metric": label, "value": display, "_sort_key": key})
    return rows
