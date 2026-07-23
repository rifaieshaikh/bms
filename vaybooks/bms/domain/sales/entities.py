from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.document_customization import DocumentContentSnapshot
from vaybooks.bms.domain.shared.enums import (
    DeliveryNoteStatus,
    EstimateStatus,
    QuotationStatus,
    SalesOrderStatus,
    SalesReturnStatus,
)


@dataclass
class SalesOrderLine:
    product_id: str
    qty_ordered: float
    rate: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    qty_delivered: float = 0.0
    qty_invoiced: float = 0.0
    hsn_sac: str = ""
    gst_rate: float = 0.0
    taxable_amount: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    utgst_amount: float = 0.0

    @property
    def total_tax(self) -> float:
        return round(
            self.cgst_amount + self.sgst_amount + self.igst_amount + self.utgst_amount,
            2,
        )

    @property
    def line_total(self) -> float:
        base = self.taxable_amount or round(self.qty_ordered * self.rate, 2)
        return round(base + self.total_tax, 2)

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
    supply_type: str = ""
    document_content: DocumentContentSnapshot = field(
        default_factory=DocumentContentSnapshot
    )
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def total_amount(self) -> float:
        return round(sum(line.line_total for line in self.lines), 2)

    @property
    def tax_summary(self) -> dict:
        taxable = round(sum(line.taxable_amount for line in self.lines), 2)
        cgst = round(sum(line.cgst_amount for line in self.lines), 2)
        sgst = round(sum(line.sgst_amount for line in self.lines), 2)
        igst = round(sum(line.igst_amount for line in self.lines), 2)
        utgst = round(sum(line.utgst_amount for line in self.lines), 2)
        return {
            "taxable": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "utgst": utgst,
            "total_tax": round(cgst + sgst + igst + utgst, 2),
            "grand_total": self.total_amount,
        }

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
    document_content: DocumentContentSnapshot = field(
        default_factory=DocumentContentSnapshot
    )
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
    source_invoice_number: str = ""
    source_dn_id: Optional[str] = None
    voucher_id: Optional[str] = None
    notes: str = ""
    return_reason: str = ""
    refund_option: str = "Customer credit"
    amount_refunded: float = 0.0
    refund_account_id: Optional[str] = None
    status: SalesReturnStatus = SalesReturnStatus.PENDING
    restock_items: bool = True
    attachments: List[dict] = field(default_factory=list)
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    goods_received_at: Optional[datetime] = None
    refund_processed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
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
class EstimateLine:
    product_id: str
    qty: float
    rate: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    hsn_sac: str = ""
    gst_rate: float = 0.0
    taxable_amount: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    utgst_amount: float = 0.0

    @property
    def total_tax(self) -> float:
        return round(
            self.cgst_amount + self.sgst_amount + self.igst_amount + self.utgst_amount,
            2,
        )

    @property
    def line_total(self) -> float:
        taxable = self.taxable_amount or round(self.qty * self.rate, 2)
        return round(taxable + self.total_tax, 2)


@dataclass
class Estimate:
    estimate_number: str
    customer_id: str
    estimate_date: date
    lines: List[EstimateLine]
    id: str = field(default_factory=lambda: uuid4().hex)
    customer_name: str = ""
    valid_until: Optional[date] = None
    status: EstimateStatus = EstimateStatus.DRAFT
    notes: str = ""
    supply_type: str = ""
    converted_sales_order_id: Optional[str] = None
    converted_invoice_id: Optional[str] = None
    document_content: DocumentContentSnapshot = field(
        default_factory=DocumentContentSnapshot
    )
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def total_amount(self) -> float:
        return round(sum(line.line_total for line in self.lines), 2)

    @property
    def tax_summary(self) -> dict:
        return _priced_tax_summary(self.lines)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


@dataclass
class Quotation:
    quotation_number: str
    customer_id: str
    quotation_date: date
    lines: List[EstimateLine]
    id: str = field(default_factory=lambda: uuid4().hex)
    customer_name: str = ""
    valid_until: Optional[date] = None
    status: QuotationStatus = QuotationStatus.DRAFT
    notes: str = ""
    supply_type: str = ""
    converted_sales_order_id: Optional[str] = None
    document_content: DocumentContentSnapshot = field(
        default_factory=DocumentContentSnapshot
    )
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def total_amount(self) -> float:
        return round(sum(line.line_total for line in self.lines), 2)

    @property
    def tax_summary(self) -> dict:
        return _priced_tax_summary(self.lines)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


def _priced_tax_summary(lines: List[EstimateLine]) -> dict:
    taxable = round(sum(line.taxable_amount for line in lines), 2)
    cgst = round(sum(line.cgst_amount for line in lines), 2)
    sgst = round(sum(line.sgst_amount for line in lines), 2)
    igst = round(sum(line.igst_amount for line in lines), 2)
    utgst = round(sum(line.utgst_amount for line in lines), 2)
    total_tax = round(cgst + sgst + igst + utgst, 2)
    return {
        "taxable": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "utgst": utgst,
        "total_tax": total_tax,
        "grand_total": round(taxable + total_tax, 2),
    }
