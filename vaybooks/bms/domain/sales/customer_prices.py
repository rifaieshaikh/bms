"""Customer-specific sales price entries (change-log, invoice-driven)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class CustomerPriceEntry:
    customer_id: str
    product_id: str
    rate: float
    effective_date: date
    id: str = field(default_factory=lambda: uuid4().hex)
    customer_name: str = ""
    sku: str = ""
    product_name: str = ""
    voucher_id: str = ""
    store_invoice_number: str = ""
    created_at: datetime = field(default_factory=utc_now)
