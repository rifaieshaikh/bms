"""Helpers for purchase bill line items."""

from __future__ import annotations

from vaybooks.bms.ui.components.purchases.purchase_line_ui import default_purchase_line


def expense_lines_from_items(line_items: list[dict]) -> list[dict]:
    """Legacy helper — prefer PurchaseAppService.create_purchase_bill_from_lines."""
    rows = []
    for row in line_items:
        qty = float(row.get("qty") or 0)
        rate = float(row.get("rate") or 0)
        amount = round(qty * rate, 2)
        if amount <= 0:
            continue
        rows.append(
            {
                "item_type": row.get("item_type"),
                "item_id": row.get("item_id"),
                "item_name": row.get("item_name") or "",
                "product_id": row.get("product_id") or row.get("item_id"),
                "product_name": row.get("item_name") or "",
                "qty": qty,
                "rate": rate,
                "amount": amount,
                "line_total": amount,
                "taxable_amount": amount,
                "landed_cost_alloc": float(row.get("landed_cost_alloc") or 0),
            }
        )
    return rows


def vendor_option_map(vendor_list) -> dict[str, str]:
    """Unique selectbox labels mapped to vendor ids."""
    options: dict[str, str] = {}
    for vendor in vendor_list:
        label = (getattr(vendor, "vendor_name", None) or "Vendor").strip()
        phone = (getattr(vendor, "phone_number", None) or "").strip()
        gstin = (getattr(vendor, "gstin", None) or "").strip()
        if phone:
            label = f"{label} ({phone})"
        if gstin:
            label = f"{label} · {gstin}"
        if label in options:
            label = f"{label} [{vendor.id[:8]}]"
        options[label] = vendor.id
    return options


def vendor_select_index(
    vendor_opts: dict[str, str], vendor_id: str | None, default: int = 0
) -> int:
    if not vendor_id or not vendor_opts:
        return default
    for i, name in enumerate(vendor_opts.keys()):
        if vendor_opts[name] == vendor_id:
            return i
    return default


__all__ = [
    "default_purchase_line",
    "expense_lines_from_items",
    "vendor_option_map",
    "vendor_select_index",
]
