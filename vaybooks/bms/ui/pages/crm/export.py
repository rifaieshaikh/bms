"""CSV export helpers shared by the CRM list and report pages."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any, Iterable, Sequence

from vaybooks.bms.ui.crm_adapters import enum_value, field

LEAD_EXPORT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("lead_number", "Lead Number"),
    ("name", "Name"),
    ("contact_person", "Contact Person"),
    ("phone", "Phone"),
    ("alternate_phone", "Alternate Phone"),
    ("email", "Email"),
    ("source", "Source"),
    ("status", "Status"),
    ("priority", "Priority"),
    ("estimated_value", "Estimated Value"),
    ("interested_products", "Interested Products"),
    ("assigned_user_name", "Owner"),
    ("area", "Area"),
    ("city", "City"),
    ("pincode", "Pincode"),
    ("gstin", "GSTIN"),
    ("next_follow_up_at", "Next Follow-up"),
    ("last_activity_at", "Last Activity"),
    ("customer_name", "Converted Customer"),
    ("lost_reason", "Lost Reason"),
    ("created_at", "Created"),
)

ENQUIRY_EXPORT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("enquiry_number", "Enquiry Number"),
    ("party_name", "Party"),
    ("product_interest", "Product Interest"),
    ("source", "Source"),
    ("status", "Status"),
    ("priority", "Priority"),
    ("expected_quantity", "Expected Quantity"),
    ("estimated_value", "Estimated Value"),
    ("assigned_user_name", "Owner"),
    ("enquiry_date", "Enquiry Date"),
    ("expected_decision_at", "Expected Decision"),
    ("next_follow_up_at", "Next Follow-up"),
    ("lost_reason", "Lost Reason"),
)

ACTIVITY_EXPORT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("activity_type", "Activity Type"),
    ("party_name", "Party"),
    ("status", "Status"),
    ("origin", "Origin"),
    ("priority", "Priority"),
    ("assigned_user_name", "Owner"),
    ("scheduled_at", "Scheduled"),
    ("activity_at", "Activity Date"),
    ("completed_at", "Completed"),
    ("outcome", "Outcome"),
    ("next_action", "Next Action"),
    ("next_follow_up_at", "Next Follow-up"),
    ("promised_amount", "Promised Amount"),
    ("promised_date", "Promised Date"),
    ("location", "Location"),
    ("notes", "Notes"),
)


def cell(value: Any) -> str:
    value = enum_value(value)
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def records_to_csv(
    records: Iterable[Any], columns: Sequence[tuple[str, str]]
) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([label for _, label in columns])
    for record in records:
        writer.writerow([cell(field(record, key)) for key, _ in columns])
    return buffer.getvalue().encode("utf-8")


def rows_to_csv(rows: Iterable[dict], columns: Sequence[str]) -> bytes:
    """Report rows (list of dicts) with an explicit column order."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(columns))
    for row in rows:
        writer.writerow([cell(row.get(column)) for column in columns])
    return buffer.getvalue().encode("utf-8")


def export_filename(prefix: str) -> str:
    return f"{prefix}_{date.today().isoformat()}.csv"
