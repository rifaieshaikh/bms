from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import CatalogItemType
from vaybooks.bms.domain.shared.item_tax import GstBreakdown, ItemTaxProfile


@dataclass
class PurchaseBillLine:
    item_type: CatalogItemType
    item_id: str
    item_name: str
    qty: float
    rate: float
    expense_account_id: str = ""
    expense_account_name: str = ""
    hsn_sac: str = ""
    taxable_amount: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    utgst_amount: float = 0.0
    line_total: float = 0.0
    product_id: Optional[str] = None
    landed_cost_alloc: float = 0.0

    @property
    def total_tax(self) -> float:
        return round(
            self.cgst_amount + self.sgst_amount + self.igst_amount + self.utgst_amount,
            2,
        )

    def to_expense_line_dict(self) -> dict:
        return {
            "item_type": self.item_type.value,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "product_id": self.product_id,
            "qty": self.qty,
            "rate": self.rate,
            "hsn_sac": self.hsn_sac,
            "expense_account_id": self.expense_account_id,
            "expense_account_name": self.expense_account_name,
            "taxable_amount": self.taxable_amount,
            "cgst_amount": self.cgst_amount,
            "sgst_amount": self.sgst_amount,
            "igst_amount": self.igst_amount,
            "utgst_amount": self.utgst_amount,
            "amount": self.line_total,
            "line_total": self.line_total,
            "landed_cost_alloc": self.landed_cost_alloc,
        }

    def to_json_dict(self) -> dict:
        data = self.to_expense_line_dict()
        data["total_tax"] = self.total_tax
        return data

    @classmethod
    def from_raw(
        cls,
        raw: dict,
        *,
        tax_profile: ItemTaxProfile,
        gst: GstBreakdown,
        expense_account_id: str,
        expense_account_name: str,
        item_name: str,
    ) -> PurchaseBillLine:
        item_type = CatalogItemType(raw.get("item_type") or CatalogItemType.PRODUCT.value)
        product_id = raw.get("product_id")
        if item_type == CatalogItemType.PRODUCT and not product_id:
            product_id = raw.get("item_id")
        return cls(
            item_type=item_type,
            item_id=str(raw.get("item_id") or ""),
            item_name=item_name,
            qty=float(raw.get("qty") or 0),
            rate=float(raw.get("rate") or 0),
            expense_account_id=expense_account_id,
            expense_account_name=expense_account_name,
            hsn_sac=tax_profile.hsn_sac,
            taxable_amount=gst.taxable_amount,
            cgst_amount=gst.cgst_amount,
            sgst_amount=gst.sgst_amount,
            igst_amount=gst.igst_amount,
            utgst_amount=gst.utgst_amount,
            line_total=gst.line_total,
            product_id=product_id,
            landed_cost_alloc=float(raw.get("landed_cost_alloc") or 0),
        )


@dataclass
class PurchasePriceHistory:
    item_type: CatalogItemType
    item_id: str
    vendor_id: str
    purchase_date: date
    qty: float
    rate: float
    taxable_amount: float
    line_total: float
    id: str = field(default_factory=lambda: uuid4().hex)
    vendor_bill_number: str = ""
    voucher_id: Optional[str] = None
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    utgst_amount: float = 0.0
    created_at: datetime = field(default_factory=utc_now)
