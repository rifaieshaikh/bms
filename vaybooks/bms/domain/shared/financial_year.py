"""Financial year helpers for invoice numbering and voucher tagging."""

from __future__ import annotations

from datetime import date, datetime
from typing import Union


def resolve_financial_year(
    d: Union[date, datetime, None],
    start_month: int = 4,
) -> str:
    """Return FY label like ``2026-27`` for an India-style Apr–Mar year by default.

    If ``start_month`` is 1 (calendar year), returns ``YYYY-YY`` for that year
    (e.g. 2026 → ``2026-27`` still uses start/end year pair for consistency:
    calendar year 2026 → ``2026-27`` meaning Jan–Dec 2026 is unusual;
    for start_month=1 we use ``YYYY`` as start and ``YYYY+1`` last two digits
    only when spanning two years. For calendar year (start_month=1):
    FY is the calendar year labeled ``YYYY-(YY+1)`` for that calendar year.
    Actually for start_month=1, the year of the date IS the FY start year.
    For start_month=4, if month < 4, FY started previous calendar year.
    """
    if d is None:
        d = date.today()
    if isinstance(d, datetime):
        d = d.date()
    start_month = int(start_month or 4)
    if start_month < 1 or start_month > 12:
        start_month = 4
    if d.month >= start_month:
        start_year = d.year
    else:
        start_year = d.year - 1
    end_year = start_year + 1
    return f"{start_year}-{str(end_year)[-2:]}"


def format_invoice_number(prefix_template: str, fy: str, seq: int) -> str:
    """Build invoice number from prefix template, FY token, and sequence.

    Example: ``INV/{FY}/`` + ``2026-27`` + ``1`` → ``INV/2026-27/0001``
    """
    template = (prefix_template or "INV/{FY}/").strip() or "INV/{FY}/"
    prefix = template.replace("{FY}", fy or "")
    return f"{prefix}{int(seq):04d}"


def peek_invoice_number(prefix_template: str, fy: str, next_seq: int) -> str:
    """Preview the next invoice number without consuming a counter."""
    return format_invoice_number(prefix_template, fy, next_seq)
