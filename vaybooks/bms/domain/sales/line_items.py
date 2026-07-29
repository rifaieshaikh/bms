from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from vaybooks.bms.domain.shared.item_tax import GstBreakdown, ItemTaxProfile


@dataclass
class SalesInvoiceLine:
    product_id: str
    item_name: str
    qty: float
    rate: float
    discount: float = 0.0
    discount_mode: str = "flat"
    discount_input: float = 0.0
    description: str = ""
    hsn_sac: str = ""
    taxable_amount: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    utgst_amount: float = 0.0
    line_total: float = 0.0
    gst_rate: float = 0.0

    @property
    def total_tax(self) -> float:
        return round(
            self.cgst_amount + self.sgst_amount + self.igst_amount + self.utgst_amount,
            2,
        )

    def to_line_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "description": self.description or self.item_name,
            "item_name": self.item_name,
            "qty": self.qty,
            "rate": self.rate,
            "discount": self.discount,
            "discount_mode": self.discount_mode or "flat",
            "discount_input": self.discount_input,
            "hsn_sac": self.hsn_sac,
            "taxable_amount": self.taxable_amount,
            "cgst_amount": self.cgst_amount,
            "sgst_amount": self.sgst_amount,
            "igst_amount": self.igst_amount,
            "utgst_amount": self.utgst_amount,
            "line_total": self.line_total,
            "gst_rate": self.gst_rate,
            "total_tax": self.total_tax,
        }

    def to_json_dict(self) -> dict:
        return self.to_line_dict()

    @classmethod
    def from_raw(
        cls,
        raw: dict,
        *,
        tax_profile: ItemTaxProfile,
        gst: GstBreakdown,
        item_name: str,
        gst_rate: float = 0.0,
    ) -> SalesInvoiceLine:
        product_id = str(raw.get("product_id") or raw.get("item_id") or "")
        line_discount = round(float(raw.get("discount") or 0), 2)
        discount_mode = (raw.get("discount_mode") or "flat").strip() or "flat"
        discount_input = round(
            float(
                raw.get("discount_input")
                if raw.get("discount_input") is not None
                else raw.get("discount")
                or 0
            ),
            2,
        )
        return cls(
            product_id=product_id,
            item_name=item_name,
            qty=float(raw.get("qty") or 0),
            rate=float(raw.get("rate") or 0),
            discount=line_discount,
            discount_mode=discount_mode,
            discount_input=discount_input,
            description=(raw.get("description") or item_name or "").strip(),
            hsn_sac=tax_profile.hsn_sac,
            taxable_amount=gst.taxable_amount,
            cgst_amount=gst.cgst_amount,
            sgst_amount=gst.sgst_amount,
            igst_amount=gst.igst_amount,
            utgst_amount=gst.utgst_amount,
            line_total=gst.line_total,
            gst_rate=gst_rate,
        )


def tax_summary_from_lines(lines: list[SalesInvoiceLine]) -> dict:
    taxable = round(sum(line.taxable_amount for line in lines), 2)
    cgst = round(sum(line.cgst_amount for line in lines), 2)
    sgst = round(sum(line.sgst_amount for line in lines), 2)
    igst = round(sum(line.igst_amount for line in lines), 2)
    utgst = round(sum(line.utgst_amount for line in lines), 2)
    total_tax = round(cgst + sgst + igst + utgst, 2)
    grand_total = round(sum(line.line_total for line in lines), 2)
    return {
        "taxable": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "utgst": utgst,
        "total_tax": total_tax,
        "grand_total": grand_total,
    }


def apply_invoice_discount_to_lines(
    lines: list[SalesInvoiceLine],
    invoice_discount: float,
    *,
    business_registered: bool,
    business_state_code: str,
    customer_state_code: str,
) -> list[SalesInvoiceLine]:
    """Apply invoice discount only to lines without item discount, by qty×rate weight."""
    from vaybooks.bms.domain.shared.india import compute_sales_gst

    if not lines or invoice_discount <= 0:
        return lines

    eligible = [line for line in lines if float(line.discount or 0) <= 0.01]
    if not eligible:
        return lines

    weights = {
        id(line): round(max(float(line.qty or 0), 0.0) * max(float(line.rate or 0), 0.0), 2)
        for line in eligible
    }
    total_weight = round(sum(weights.values()), 2)
    eligible_taxable = round(sum(float(line.taxable_amount or 0) for line in eligible), 2)
    if total_weight <= 0 or eligible_taxable <= 0:
        return lines

    invoice_discount = round(min(float(invoice_discount), eligible_taxable), 2)
    if invoice_discount <= 0:
        return lines

    # Distribute discount; last eligible line absorbs rounding remainder.
    allocated = 0.0
    share_by_id: dict[int, float] = {}
    for index, line in enumerate(eligible):
        if index == len(eligible) - 1:
            share = round(invoice_discount - allocated, 2)
        else:
            share = round(invoice_discount * (weights[id(line)] / total_weight), 2)
            allocated = round(allocated + share, 2)
        share_by_id[id(line)] = min(share, float(line.taxable_amount or 0))

    adjusted: list[SalesInvoiceLine] = []
    for line in lines:
        share = share_by_id.get(id(line), 0.0)
        if share <= 0:
            adjusted.append(line)
            continue
        new_taxable = round(max(float(line.taxable_amount or 0) - share, 0.0), 2)
        gst = compute_sales_gst(
            new_taxable,
            line.gst_rate,
            business_registered=business_registered,
            business_state_code=business_state_code,
            customer_state_code=customer_state_code,
        )
        adjusted.append(
            SalesInvoiceLine(
                product_id=line.product_id,
                item_name=line.item_name,
                qty=line.qty,
                rate=line.rate,
                discount=line.discount,
                discount_mode=line.discount_mode,
                discount_input=line.discount_input,
                description=line.description,
                hsn_sac=line.hsn_sac,
                taxable_amount=gst.taxable_amount,
                cgst_amount=gst.cgst_amount,
                sgst_amount=gst.sgst_amount,
                igst_amount=gst.igst_amount,
                utgst_amount=gst.utgst_amount,
                line_total=gst.line_total,
                gst_rate=line.gst_rate,
            )
        )
    return adjusted


def serialize_sales_line_items(
    line_items: list[dict],
    invoice_discount: float = 0.0,
    tax_summary: dict | None = None,
    document_content: dict | None = None,
    commission: dict | None = None,
) -> str:
    payload: dict = {
        "items": line_items,
        "invoice_discount": round(invoice_discount, 2),
    }
    if tax_summary:
        payload["tax_summary"] = tax_summary
    if document_content:
        payload["document_content"] = document_content
    if commission:
        payload["commission"] = commission
    return json.dumps(payload, ensure_ascii=False)


def parse_sales_line_items_note(
    description: str,
) -> tuple[list[dict], float, dict | None]:
    if not description or "\n" not in description:
        return [], 0.0, None
    _, rest = description.split("\n", 1)
    rest = rest.strip()
    if not rest:
        return [], 0.0, None
    try:
        data = json.loads(rest)
        items = data.get("items") or []
        invoice_discount = float(data.get("invoice_discount") or 0.0)
        tax_summary = data.get("tax_summary")
        return items, round(invoice_discount, 2), tax_summary
    except (json.JSONDecodeError, TypeError, ValueError):
        return [], 0.0, None


def parse_sales_document_content(description: str) -> dict:
    if not description or "\n" not in description:
        return {}
    try:
        data = json.loads(description.split("\n", 1)[1].strip())
        content = data.get("document_content")
        return content if isinstance(content, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def parse_sales_commission_from_note(description: str) -> dict | None:
    from vaybooks.bms.domain.sales.commission import parse_sales_commission

    return parse_sales_commission(description)
