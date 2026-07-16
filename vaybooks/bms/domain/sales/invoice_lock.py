from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


def ist_today() -> date:
    return datetime.now(IST).date()


def invoice_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise ValueError("Invoice date is invalid")


def can_edit_invoice(value, today: date | None = None) -> bool:
    issued = invoice_date(value)
    current = today or ist_today()
    return (issued.year, issued.month) == (current.year, current.month)


def assert_invoice_editable(value, today: date | None = None) -> None:
    if not can_edit_invoice(value, today):
        raise ValueError("Invoice is locked because its invoice month has ended")
