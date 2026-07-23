"""Purchase order PDF — same visual system as sales documents."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from vaybooks.bms.domain.shared.document_customization import (
    DocumentContentSnapshot,
    SalesPrintSettings,
)
from vaybooks.bms.domain.shared.enums import VendorRegistrationType
from vaybooks.bms.domain.shared.india import compute_purchase_gst
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import generate_sales_document_pdf


def _val(source: Any, name: str, default: Any = ""):
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _fmt_date(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return str(value or "")


def _tax_profile(item: Any) -> ItemTaxProfile:
    if item is None:
        return ItemTaxProfile()
    if hasattr(item, "active_tax_profile"):
        return item.active_tax_profile()
    return getattr(item, "tax_profile", None) or ItemTaxProfile()


def _vendor_registered(vendor: Any) -> bool:
    if not vendor:
        return False
    return _val(vendor, "registration_type", None) == VendorRegistrationType.REGISTERED


def _party_address(vendor: Any) -> str:
    if not vendor:
        return ""
    if getattr(vendor, "formatted_address", ""):
        return str(vendor.formatted_address)
    return ", ".join(
        str(part)
        for part in (
            _val(vendor, "address_line1", ""),
            _val(vendor, "address_line2", ""),
            _val(vendor, "city", ""),
            _val(vendor, "state_code", ""),
            _val(vendor, "pincode", ""),
        )
        if part
    )


def _line_payload(
    line: Any,
    *,
    catalog_by_id: dict[str, Any],
    vendor_registered: bool,
    business_state_code: str,
    vendor_state_code: str,
    include_gst: bool,
) -> dict:
    qty = float(_val(line, "qty_ordered", 0) or 0)
    rate = float(_val(line, "rate", 0) or 0)
    taxable = round(qty * rate, 2)
    name = str(
        _val(line, "product_name", "")
        or _val(line, "item_name", "")
        or _val(line, "product_id", "")
        or "—"
    )
    row = {
        "product_name": name,
        "item_name": name,
        "qty": qty,
        "qty_ordered": qty,
        "rate": rate,
        "discount": 0.0,
        "taxable_amount": taxable,
        "gst_rate": 0.0,
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "utgst_amount": 0.0,
        "igst_amount": 0.0,
        "line_total": taxable,
    }
    if not include_gst or not vendor_registered:
        return row

    product = catalog_by_id.get(str(_val(line, "product_id", "") or ""))
    profile = _tax_profile(product)
    gst_rate = float(profile.gst_rate or 0)
    gst = compute_purchase_gst(
        taxable,
        gst_rate,
        vendor_registered=True,
        business_state_code=business_state_code,
        vendor_state_code=vendor_state_code,
    )
    row.update(
        {
            "hsn_sac": profile.hsn_sac or "",
            "gst_rate": gst_rate,
            "taxable_amount": gst.taxable_amount,
            "cgst_amount": gst.cgst_amount,
            "sgst_amount": gst.sgst_amount,
            "utgst_amount": gst.utgst_amount,
            "igst_amount": gst.igst_amount,
            "line_total": gst.line_total,
        }
    )
    return row


def purchase_order_document(
    order: Any,
    *,
    vendor: Any = None,
    business: Any = None,
    settings: SalesPrintSettings | None = None,
    catalog_items: Iterable[Any] | None = None,
    document_content: DocumentContentSnapshot | None = None,
) -> dict:
    """Build a sales-doc-compatible payload for a purchase order."""
    settings = settings or SalesPrintSettings()
    catalog_by_id = {
        str(_val(item, "id", "") or ""): item
        for item in (catalog_items or [])
        if _val(item, "id", "")
    }
    vendor_registered = _vendor_registered(vendor)
    include_gst = bool(settings.show_gst_columns and vendor_registered)
    lines = [
        _line_payload(
            line,
            catalog_by_id=catalog_by_id,
            vendor_registered=vendor_registered,
            business_state_code=str(_val(business, "state_code", "") or ""),
            vendor_state_code=str(_val(vendor, "state_code", "") or ""),
            include_gst=include_gst,
        )
        for line in list(_val(order, "lines", []) or [])
    ]
    total = round(sum(float(line["line_total"] or 0) for line in lines), 2)
    if not lines:
        total = float(_val(order, "total_amount", 0) or 0)
    vendor_name = (
        _val(order, "vendor_name", "")
        or _val(vendor, "vendor_name", "")
        or _val(vendor, "name", "")
    )
    return {
        "po_number": _val(order, "po_number", ""),
        "order_date": _fmt_date(_val(order, "order_date")),
        "expected_date": _fmt_date(_val(order, "expected_date")),
        "customer_name": vendor_name,
        "party_name": vendor_name,
        "party_address": _party_address(vendor),
        "notes": _val(order, "notes", ""),
        "items": lines,
        "total_amount": total,
        "document_content": document_content or DocumentContentSnapshot(),
    }


def generate_purchase_order_pdf(
    order: Any,
    business: Any = None,
    settings: SalesPrintSettings | None = None,
    *,
    vendor: Any = None,
    catalog_items: Iterable[Any] | None = None,
    document_content: DocumentContentSnapshot | None = None,
) -> bytes:
    """Render a purchase order with the same layout engine as sales documents."""
    settings = settings or SalesPrintSettings()
    document = purchase_order_document(
        order,
        vendor=vendor,
        business=business,
        settings=settings,
        catalog_items=catalog_items,
        document_content=document_content,
    )
    return generate_sales_document_pdf(
        "purchase_order",
        document,
        business,
        settings,
    )
