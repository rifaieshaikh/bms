from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ExpenseSource


@dataclass
class Expense:
    order_id: str
    order_number: str
    expense_date: date
    expense_name: str
    expense_source: ExpenseSource
    purchase_price: float
    selling_price: float
    quantity: float = 1.0
    id: str = field(default_factory=lambda: uuid4().hex)
    bill_id: Optional[str] = None
    bill_number: Optional[str] = None
    activity_id: Optional[str] = None
    activity_name: Optional[str] = None
    total_purchase_price: float = 0.0
    total_selling_price: float = 0.0
    linked_time_minutes: int = 0
    linked_time_hours: float = 0.0
    vendor_or_worker_name: str = ""
    account_id: Optional[str] = None
    notes: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def calculate_totals(self) -> None:
        self.total_purchase_price = round(self.purchase_price * self.quantity, 2)
        self.total_selling_price = round(self.selling_price * self.quantity, 2)
