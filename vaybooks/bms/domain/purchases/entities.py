from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import GoodsReceiptStatus, PurchaseOrderStatus


@dataclass
class PurchaseOrderLine:
    product_id: str
    qty_ordered: float
    rate: float = 0.0
    expense_account_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    qty_received: float = 0.0

    @property
    def line_total(self) -> float:
        return round(self.qty_ordered * self.rate, 2)

    @property
    def qty_pending(self) -> float:
        return round(max(self.qty_ordered - self.qty_received, 0.0), 2)


@dataclass
class PurchaseOrder:
    po_number: str
    vendor_id: str
    order_date: date
    lines: List[PurchaseOrderLine]
    id: str = field(default_factory=lambda: uuid4().hex)
    vendor_name: str = ""
    expected_date: Optional[date] = None
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT
    notes: str = ""
    project_id: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def total_amount(self) -> float:
        return round(sum(line.line_total for line in self.lines), 2)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


@dataclass
class GoodsReceiptLine:
    product_id: str
    qty_received: float
    rate: float = 0.0
    landed_cost_extra: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    purchase_order_line_id: str = ""

    @property
    def line_total(self) -> float:
        return round(self.qty_received * self.rate + self.landed_cost_extra, 2)

    @property
    def unit_cost(self) -> float:
        if self.qty_received <= 0:
            return 0.0
        return round(self.line_total / self.qty_received, 4)


@dataclass
class GoodsReceipt:
    grn_number: str
    vendor_id: str
    receipt_date: date
    lines: List[GoodsReceiptLine]
    id: str = field(default_factory=lambda: uuid4().hex)
    purchase_order_id: Optional[str] = None
    po_number: str = ""
    vendor_name: str = ""
    status: GoodsReceiptStatus = GoodsReceiptStatus.DRAFT
    freight: float = 0.0
    duty: float = 0.0
    other: float = 0.0
    notes: str = ""
    voucher_id: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def total_landed_extras(self) -> float:
        return round(self.freight + self.duty + self.other, 2)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


@dataclass
class PurchaseReturnLine:
    product_id: str
    qty: float
    rate: float = 0.0
    expense_account_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""

    @property
    def line_total(self) -> float:
        return round(self.qty * self.rate, 2)


@dataclass
class PurchaseReturn:
    return_number: str
    vendor_id: str
    return_date: date
    lines: List[PurchaseReturnLine]
    id: str = field(default_factory=lambda: uuid4().hex)
    vendor_name: str = ""
    source_bill_id: Optional[str] = None
    source_grn_id: Optional[str] = None
    voucher_id: Optional[str] = None
    notes: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def total_amount(self) -> float:
        return round(sum(line.line_total for line in self.lines), 2)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()
