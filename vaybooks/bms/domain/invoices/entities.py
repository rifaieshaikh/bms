from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class Invoice:
    order_id: str
    order_number: str
    invoice_number: str
    invoice_date: date
    invoice_amount: float
    total_amount: float = 0.0
    bill_ids: List[str] = field(default_factory=list)
    # Gross price entered per item (bill_id -> amount). Enables per-item MPH.
    item_amounts: Dict[str, float] = field(default_factory=dict)
    discount_amount: float = 0.0
    total_expense_purchase_price: float = 0.0
    total_expense_selling_price: float = 0.0
    total_in_house_hours: float = 0.0
    margin_amount: float = 0.0
    margin_per_hour: Optional[float] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def net_amount(self) -> float:
        """Amount the customer owes: gross invoice amount minus discount."""
        return round(self.invoice_amount - self.discount_amount, 2)
