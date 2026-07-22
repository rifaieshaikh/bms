"""UI-layer display helpers for purchase documents (not domain parsing)."""

from __future__ import annotations

from typing import Any, Optional

from vaybooks.bms.domain.finance.accounting.purchase_parsing import (
    parse_purchase_lines_from_description,
)
from vaybooks.bms.domain.shared.enums import CatalogItemType


def product_lines_from_bill_row(row: dict, description: str = "") -> tuple[list[dict], int]:
    """Extract returnable product lines from a bill row; return (lines, skipped_services)."""
    raw_lines = row.get("line_items") or parse_purchase_lines_from_description(
        description or ""
    )
    product_lines: list[dict] = []
    skipped = 0
    for item in raw_lines:
        item_type = str(item.get("item_type") or CatalogItemType.PRODUCT.value)
        if item_type == CatalogItemType.SERVICE.value:
            skipped += 1
            continue
        product_id = str(item.get("product_id") or item.get("item_id") or "")
        if not product_id:
            continue
        product_lines.append(
            {
                "item_type": CatalogItemType.PRODUCT.value,
                "item_id": product_id,
                "product_id": product_id,
                "item_name": item.get("item_name") or item.get("product_name") or "",
                "qty": float(item.get("qty") or 0) or 1.0,
                "rate": float(item.get("rate") or 0),
            }
        )
    return product_lines, skipped


def display_item_name(
    item: dict,
    *,
    product_by_id: Optional[dict[str, Any]] = None,
    service_by_id: Optional[dict[str, Any]] = None,
) -> str:
    """Prefer item_name → product_name → catalog lookup → em dash."""
    name = (item.get("item_name") or item.get("product_name") or "").strip()
    if name:
        return name
    item_id = str(item.get("item_id") or item.get("product_id") or "")
    if item_id and product_by_id and item_id in product_by_id:
        product = product_by_id[item_id]
        return getattr(product, "name", None) or str(product)
    if item_id and service_by_id and item_id in service_by_id:
        service = service_by_id[item_id]
        return getattr(service, "service_name", None) or str(service)
    return "—"


def purchase_line_table_row(
    item: dict,
    *,
    product_by_id: Optional[dict[str, Any]] = None,
    service_by_id: Optional[dict[str, Any]] = None,
) -> dict:
    """Map a stored purchase line dict into document_detail line_items_table shape."""
    name = display_item_name(
        item, product_by_id=product_by_id, service_by_id=service_by_id
    )
    qty = float(item.get("qty") or item.get("qty_ordered") or 0)
    rate = float(item.get("rate") or 0)
    line_total = float(
        item.get("line_total") or item.get("amount") or round(qty * rate, 2)
    )
    return {
        "item_name": name,
        "product": name,
        "description": name,
        "qty": qty,
        "rate": rate,
        "total": line_total,
        "line_total": line_total,
        "hsn_sac": item.get("hsn_sac") or "",
        "taxable": float(item.get("taxable_amount") or item.get("taxable") or 0),
        "taxable_amount": float(item.get("taxable_amount") or item.get("taxable") or 0),
        "gst_rate": float(item.get("gst_rate") or 0),
        "cgst_amount": float(item.get("cgst_amount") or 0),
        "sgst_amount": float(item.get("sgst_amount") or 0),
        "utgst_amount": float(item.get("utgst_amount") or 0),
        "igst_amount": float(item.get("igst_amount") or 0),
        "qty_ordered": item.get("qty_ordered"),
        "qty_received": item.get("qty_received"),
    }
