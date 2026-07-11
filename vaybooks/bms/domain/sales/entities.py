from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import DeliveryNoteStatus, SalesOrderStatus


@dataclass
class SalesOrderLine:
    product_id: str
    qty_ordered: float
    rate: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    qty_delivered: float = 0.0
    qty_invoiced: float = 0.0

    @property
    def line_total(self) -> float:
        return round(self.qty_ordered * self.rate, 2)

    @property
    def qty_pending(self) -> float:
        return round(max(self.qty_ordered - self.qty_delivered, 0.0), 2)


@dataclass
class SalesOrder:
    so_number: str
    customer_id: str
    order_date: date
    lines: List[SalesOrderLine]
    id: str = field(default_factory=lambda: uuid4().hex)
    customer_name: str = ""
    expected_date: Optional[date] = None
    status: SalesOrderStatus = SalesOrderStatus.DRAFT
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


@dataclass
class DeliveryNoteLine:
    product_id: str
    qty_delivered: float
    rate: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    sales_order_line_id: str = ""

    @property
    def line_total(self) -> float:
        return round(self.qty_delivered * self.rate, 2)


@dataclass
class DeliveryNote:
    dn_number: str
    customer_id: str
    delivery_date: date
    lines: List[DeliveryNoteLine]
    id: str = field(default_factory=lambda: uuid4().hex)
    sales_order_id: Optional[str] = None
    so_number: str = ""
    customer_name: str = ""
    status: DeliveryNoteStatus = DeliveryNoteStatus.DRAFT
    notes: str = ""
    voucher_id: Optional[str] = None
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
class SalesReturnLine:
    product_id: str
    qty: float
    rate: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""

    @property
    def line_total(self) -> float:
        return round(self.qty * self.rate, 2)


@dataclass
class SalesReturn:
    return_number: str
    customer_id: str
    return_date: date
    lines: List[SalesReturnLine]
    id: str = field(default_factory=lambda: uuid4().hex)
    customer_name: str = ""
    source_invoice_id: Optional[str] = None
    source_dn_id: Optional[str] = None
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
