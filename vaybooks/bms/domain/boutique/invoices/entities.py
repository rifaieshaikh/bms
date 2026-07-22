from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now

INVOICE_SOURCE_RECORDED = "recorded"
INVOICE_SOURCE_GENERATED = "generated"

INVOICE_KIND_STANDARD = "standard"
INVOICE_KIND_CANCELLATION = "cancellation"

# Default SAC for tailoring / customization services (GST).
DEFAULT_CUSTOMIZATION_SAC = "9983"
DEFAULT_CUSTOMIZATION_GST_RATE = 5.0


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
    # Discount applied per item (bill_id -> amount). Order-level discount is the
    # sum of these and is distributed proportionally to item gross amounts.
    item_discounts: Dict[str, float] = field(default_factory=dict)
    discount_amount: float = 0.0
    total_expense_purchase_price: float = 0.0
    total_expense_selling_price: float = 0.0
    total_in_house_hours: float = 0.0
    margin_amount: float = 0.0
    margin_per_hour: Optional[float] = None
    # "recorded" = paper bill logged manually; "generated" = system tax invoice.
    invoice_source: str = INVOICE_SOURCE_RECORDED
    gst_rate: float = 0.0
    hsn_sac: str = ""
    place_of_supply_state: str = ""
    supply_type: str = ""
    taxable_amount: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    utgst_amount: float = 0.0
    invoice_kind: str = INVOICE_KIND_STANDARD
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def is_cancellation(self) -> bool:
        return self.invoice_kind == INVOICE_KIND_CANCELLATION

    @property
    def is_generated(self) -> bool:
        return self.invoice_source == INVOICE_SOURCE_GENERATED

    @property
    def net_amount(self) -> float:
        """Taxable revenue after discount (pre-GST). MPH is computed on this."""
        return round(self.invoice_amount - self.discount_amount, 2)

    @property
    def total_tax(self) -> float:
        return round(
            self.cgst_amount + self.sgst_amount + self.igst_amount + self.utgst_amount,
            2,
        )

    @property
    def grand_total(self) -> float:
        """Amount due from customer including GST when applicable."""
        if self.is_generated and self.total_tax > 0:
            return round(self.net_amount + self.total_tax, 2)
        return self.net_amount
