"""UI helpers for purchase bill line GST preview."""

from __future__ import annotations

from vaybooks.bms.domain.shared.enums import CatalogItemType, VendorRegistrationType
from vaybooks.bms.domain.shared.india import compute_purchase_gst
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile


def default_purchase_line() -> dict:
    return {
        "item_type": CatalogItemType.PRODUCT.value,
        "item_id": None,
        "item_name": "",
        "product_id": None,
        "qty": 1.0,
        "rate": 0.0,
        "landed_cost_alloc": 0.0,
    }


def line_tax_profile(item) -> ItemTaxProfile:
    if item is None:
        return ItemTaxProfile()
    if hasattr(item, "active_tax_profile"):
        return item.active_tax_profile()
    return getattr(item, "tax_profile", ItemTaxProfile())


def preview_line_gst(
    qty: float,
    rate: float,
    tax_profile: ItemTaxProfile,
    *,
    vendor_registered: bool,
    business_state_code: str = "",
    vendor_state_code: str = "",
) -> dict:
    taxable = round(float(qty or 0) * float(rate or 0), 2)
    gst_rate = float(tax_profile.gst_rate or 0) if vendor_registered else 0.0
    gst = compute_purchase_gst(
        taxable,
        gst_rate,
        vendor_registered=vendor_registered,
        business_state_code=business_state_code,
        vendor_state_code=vendor_state_code,
    )
    return {
        "hsn_sac": tax_profile.hsn_sac or "",
        "gst_rate": gst_rate,
        "taxable_amount": gst.taxable_amount,
        "cgst_amount": gst.cgst_amount,
        "sgst_amount": gst.sgst_amount,
        "igst_amount": gst.igst_amount,
        "utgst_amount": gst.utgst_amount,
        "line_total": gst.line_total,
    }


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


def line_items_total(line_items: list[dict], gst_previews: list[dict] | None = None) -> float:
    if gst_previews:
        return round(sum(float(p.get("line_total") or 0) for p in gst_previews), 2)
    total = 0.0
    for row in line_items:
        qty = float(row.get("qty") or 0)
        rate = float(row.get("rate") or 0)
        total += round(qty * rate, 2)
    return round(total, 2)


def vendor_is_registered(vendor) -> bool:
    if not vendor:
        return False
    return getattr(vendor, "registration_type", None) == VendorRegistrationType.REGISTERED


def item_option_map(items, label_fn) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in items:
        label = label_fn(item)
        if label in options:
            label = f"{label} [{item.id[:8]}]"
        options[label] = item.id
    return options
