"""UI helpers for sales invoice line GST preview."""

from __future__ import annotations

from vaybooks.bms.domain.shared.india import compute_sales_gst
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile
from vaybooks.bms.domain.sales.sales_line_resolver import effective_sales_gst_rate


def line_tax_profile(item) -> ItemTaxProfile:
    if item is None:
        return ItemTaxProfile()
    if hasattr(item, "active_tax_profile"):
        return item.active_tax_profile()
    return getattr(item, "tax_profile", ItemTaxProfile())


def preview_sales_line_gst(
    qty: float,
    rate: float,
    line_discount: float,
    tax_profile: ItemTaxProfile,
    *,
    business_registered: bool,
    business=None,
    business_state_code: str = "",
    customer_state_code: str = "",
) -> dict:
    line_gross = round(float(qty or 0) * float(rate or 0), 2)
    discount = round(min(max(float(line_discount or 0), 0.0), line_gross), 2)
    taxable = round(max(line_gross - discount, 0.0), 2)
    gst_rate = (
        effective_sales_gst_rate(business, tax_profile.gst_rate)
        if business is not None
        else (tax_profile.gst_rate if business_registered else 0.0)
    )
    gst = compute_sales_gst(
        taxable,
        gst_rate,
        business_registered=business_registered,
        business_state_code=business_state_code,
        customer_state_code=customer_state_code,
    )
    return {
        "hsn_sac": tax_profile.hsn_sac,
        "taxable_amount": gst.taxable_amount,
        "cgst_amount": gst.cgst_amount,
        "sgst_amount": gst.sgst_amount,
        "igst_amount": gst.igst_amount,
        "utgst_amount": gst.utgst_amount,
        "line_total": gst.line_total,
        "gst_rate": gst_rate,
    }


def line_items_total(line_items: list[dict], gst_previews: list[dict] | None = None) -> float:
    if gst_previews:
        return round(sum(float(p.get("line_total") or 0) for p in gst_previews), 2)
    total = 0.0
    for row in line_items:
        qty = float(row.get("qty") or 0)
        rate = float(row.get("rate") or 0)
        line_gross = round(qty * rate, 2)
        line_discount = round(min(float(row.get("discount") or 0), line_gross), 2)
        total += round(line_gross - line_discount, 2)
    return round(total, 2)


def tax_summary_from_previews(previews: list[dict]) -> dict:
    taxable = round(sum(float(p.get("taxable_amount") or 0) for p in previews), 2)
    cgst = round(sum(float(p.get("cgst_amount") or 0) for p in previews), 2)
    sgst = round(sum(float(p.get("sgst_amount") or 0) for p in previews), 2)
    igst = round(sum(float(p.get("igst_amount") or 0) for p in previews), 2)
    utgst = round(sum(float(p.get("utgst_amount") or 0) for p in previews), 2)
    total_tax = round(cgst + sgst + igst + utgst, 2)
    grand_total = round(sum(float(p.get("line_total") or 0) for p in previews), 2)
    return {
        "taxable": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "utgst": utgst,
        "total_tax": total_tax,
        "grand_total": grand_total,
    }
