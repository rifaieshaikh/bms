"""Helpers for store cash sales invoice dialog (line items + voucher parse/serialize)."""

from __future__ import annotations

from typing import Any, Optional

from vaybooks.bms.domain.finance.accounting.sales_parsing import (
    STORE_INVOICE_PREFIX,
    parse_store_invoice_number,
    sales_amounts_from_lines,
    sales_row_from_voucher,
)
from vaybooks.bms.domain.sales.line_items import (
    parse_sales_line_items_note,
    serialize_sales_line_items,
)

__all__ = [
    "STORE_INVOICE_PREFIX",
    "parse_store_invoice_number",
    "sales_amounts_from_lines",
    "sales_row_from_voucher",
    "serialize_line_items",
    "parse_line_items_note",
    "line_items_gross",
    "line_items_discount",
    "line_items_taxable",
    "line_items_tax_total",
    "line_items_grand_total",
    "default_line_item",
    "parse_cash_sales_voucher",
    "format_line_items_summary",
]


def serialize_line_items(
    line_items: list[dict],
    invoice_discount: float,
    tax_summary: dict | None = None,
) -> str:
    return serialize_sales_line_items(line_items, invoice_discount, tax_summary)


def parse_line_items_note(description: str) -> tuple[list[dict], float]:
    items, invoice_discount, _ = parse_sales_line_items_note(description)
    return items, invoice_discount


def parse_line_items_with_tax(description: str) -> tuple[list[dict], float, dict | None]:
    return parse_sales_line_items_note(description)


def line_items_gross(line_items: list[dict]) -> float:
    total = 0.0
    for row in line_items:
        qty = float(row.get("qty") or 1.0)
        rate = float(row.get("rate") or 0.0)
        line_discount = float(row.get("discount") or 0.0)
        line_gross = round(qty * rate, 2)
        line_discount = round(min(max(line_discount, 0.0), line_gross), 2)
        total += line_gross
    return round(total, 2)


def line_items_discount(line_items: list[dict]) -> float:
    total = 0.0
    for row in line_items:
        qty = float(row.get("qty") or 1.0)
        rate = float(row.get("rate") or 0.0)
        line_discount = float(row.get("discount") or 0.0)
        line_gross = round(qty * rate, 2)
        total += round(min(max(line_discount, 0.0), line_gross), 2)
    return round(total, 2)


def line_items_taxable(line_items: list[dict], tax_summary: dict | None = None) -> float:
    if tax_summary:
        return float(tax_summary.get("taxable") or 0.0)
    total = 0.0
    for row in line_items:
        if "taxable_amount" in row:
            total += float(row.get("taxable_amount") or 0.0)
        else:
            qty = float(row.get("qty") or 1.0)
            rate = float(row.get("rate") or 0.0)
            line_discount = float(row.get("discount") or 0.0)
            line_gross = round(qty * rate, 2)
            line_discount = round(min(max(line_discount, 0.0), line_gross), 2)
            total += round(line_gross - line_discount, 2)
    return round(total, 2)


def line_items_tax_total(line_items: list[dict], tax_summary: dict | None = None) -> float:
    if tax_summary:
        return float(tax_summary.get("total_tax") or 0.0)
    total = 0.0
    for row in line_items:
        if "total_tax" in row:
            total += float(row.get("total_tax") or 0.0)
        else:
            total += round(
                float(row.get("cgst_amount") or 0)
                + float(row.get("sgst_amount") or 0)
                + float(row.get("igst_amount") or 0)
                + float(row.get("utgst_amount") or 0),
                2,
            )
    return round(total, 2)


def line_items_grand_total(line_items: list[dict], tax_summary: dict | None = None) -> float:
    if tax_summary:
        return float(tax_summary.get("grand_total") or 0.0)
    if any("line_total" in row for row in line_items):
        return round(sum(float(row.get("line_total") or 0) for row in line_items), 2)
    return round(line_items_taxable(line_items) + line_items_tax_total(line_items), 2)


def default_line_item() -> dict[str, Any]:
    return {
        "description": "",
        "qty": 1.0,
        "rate": 0.0,
        "discount": 0.0,
        "product_id": None,
    }


def parse_cash_sales_voucher(voucher, discount_account_id: Optional[str] = None) -> dict:
    """Extract fields from a cash sales invoice voucher for editing."""
    amounts = sales_amounts_from_lines(voucher.lines, discount_account_id)
    gross = amounts["gross"]
    discount = amounts["discount"]
    received = amounts["collected"]
    customer_id = amounts["customer_account_id"]
    store_id = None
    for line in voucher.lines:
        if line.description == "Cash/Bank received" and line.debit_amount > 0:
            store_id = line.account_id
            break

    items, invoice_discount, tax_summary = parse_sales_line_items_note(
        voucher.description or ""
    )
    if not items and gross > 0:
        line_disc = round(max(discount - invoice_discount, 0.0), 2)
        items = [
            {
                "description": "Invoice total",
                "qty": 1.0,
                "rate": gross,
                "discount": line_disc,
            }
        ]

    store_number = parse_store_invoice_number(voucher.description or "")
    return {
        "store_invoice_number": store_number,
        "customer_id": customer_id,
        "store_id": store_id,
        "gross": gross,
        "discount": discount,
        "invoice_discount": invoice_discount,
        "tax_summary": tax_summary,
        "received": received,
        "line_items": items or [default_line_item()],
    }


def format_line_items_summary(line_items: list[dict]) -> str:
    rows = []
    for row in line_items:
        desc = (row.get("description") or "").strip()
        if not desc:
            continue
        qty = float(row.get("qty") or 1.0)
        rate = float(row.get("rate") or 0.0)
        disc = float(row.get("discount") or 0.0)
        rows.append(f"{desc} x{qty:g} @ ₹{rate:,.0f} (disc ₹{disc:,.0f})")
    return "; ".join(rows)
