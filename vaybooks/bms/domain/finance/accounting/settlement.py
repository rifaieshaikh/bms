"""Invoice settlement helpers: ALLOC_INVOICE meta, FIFO, payment status."""

from __future__ import annotations

import json
import re
from typing import Optional

ALLOC_INVOICE_TAG = "ALLOC_INVOICE"
CREDIT_APPLIED_TAG = "CREDIT_APPLIED"
CUSTOMER_SETTLEMENT_TAG = "CUSTOMER_SETTLEMENT"
PAYMENT_TOLERANCE = 0.01

_META_PATTERN = re.compile(r"\n<!--([A-Z_]+):(\{.*?\})-->", re.DOTALL)


def append_meta(description: str, tag: str, payload: dict) -> str:
    base = (description or "").strip()
    # Strip existing tag block so updates replace rather than stack.
    base = strip_meta(base, tag)
    return f"{base}\n<!--{tag}:{json.dumps(payload, separators=(',', ':'))}-->"


def strip_meta(description: str, tag: str) -> str:
    pattern = re.compile(rf"\n<!--{re.escape(tag)}:(\{{.*?\}})-->", re.DOTALL)
    return pattern.sub("", description or "").rstrip()


def parse_meta(description: str, tag: str) -> dict:
    pattern = re.compile(rf"\n<!--{re.escape(tag)}:(\{{.*?\}})-->", re.DOTALL)
    match = pattern.search(description or "")
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def parse_all_meta(description: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for match in _META_PATTERN.finditer(description or ""):
        tag = match.group(1)
        try:
            data = json.loads(match.group(2))
            if isinstance(data, dict):
                result[tag] = data
        except json.JSONDecodeError:
            continue
    return result


def fifo_allocations(
    amount: float,
    open_invoices: list[dict],
) -> list[dict]:
    """Allocate amount across open invoices oldest-first.

    Each open invoice dict needs ``id`` and ``outstanding``.
    Returns ``[{invoice_id, amount}, ...]``.
    """
    remaining = round(max(float(amount or 0), 0.0), 2)
    if remaining <= 0:
        return []
    rows: list[dict] = []
    for inv in open_invoices:
        if remaining <= PAYMENT_TOLERANCE:
            break
        invoice_id = (inv.get("id") or inv.get("invoice_id") or "").strip()
        outstanding = round(float(inv.get("outstanding") or 0), 2)
        if not invoice_id or outstanding <= PAYMENT_TOLERANCE:
            continue
        applied = round(min(remaining, outstanding), 2)
        if applied <= 0:
            continue
        rows.append({"invoice_id": invoice_id, "amount": applied})
        remaining = round(remaining - applied, 2)
    return rows


def single_invoice_allocation(
    amount: float,
    invoice_id: str,
    outstanding: float,
) -> list[dict]:
    """Allocate to one invoice, capped at outstanding."""
    invoice_id = (invoice_id or "").strip()
    if not invoice_id:
        return []
    applied = round(min(max(float(amount or 0), 0.0), max(float(outstanding or 0), 0.0)), 2)
    if applied <= PAYMENT_TOLERANCE:
        return []
    return [{"invoice_id": invoice_id, "amount": applied}]


def allocation_rows_from_meta(description: str) -> list[dict]:
    meta = parse_meta(description or "", ALLOC_INVOICE_TAG)
    raw = meta.get("allocations") or []
    rows: list[dict] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        invoice_id = (
            row.get("invoice_id") or row.get("invoice_voucher_id") or ""
        ).strip()
        amt = round(float(row.get("amount") or 0), 2)
        if invoice_id and amt > PAYMENT_TOLERANCE:
            rows.append({"invoice_id": invoice_id, "amount": amt})
    return rows


def allocated_total(allocations: list[dict]) -> float:
    return round(sum(float(r.get("amount") or 0) for r in allocations), 2)


def credit_applied_from_description(description: str) -> float:
    meta = parse_meta(description or "", CREDIT_APPLIED_TAG)
    return round(float(meta.get("amount") or 0), 2)


def payment_status(net: float, collected: float) -> str:
    net = round(float(net or 0), 2)
    collected = round(float(collected or 0), 2)
    outstanding = round(max(0.0, net - collected), 2)
    if outstanding <= PAYMENT_TOLERANCE:
        return "paid"
    if collected > PAYMENT_TOLERANCE:
        return "partially_paid"
    return "unpaid"


def payment_status_label(status: str) -> str:
    return {
        "paid": "Paid",
        "partially_paid": "Partially paid",
        "unpaid": "Unpaid",
    }.get(status, "Unpaid")


def enrich_amounts_with_settlements(
    amounts: dict,
    *,
    receipt_allocated: float = 0.0,
    credit_note_allocated: float = 0.0,
    credit_applied: float = 0.0,
    settlement_allocated: float = 0.0,
) -> dict:
    """Merge cash-on-invoice amounts with external settlements."""
    cash_collected = round(float(amounts.get("collected") or 0), 2)
    # Advance applied on the voucher is already folded into cash_collected by
    # sales_amounts_from_lines when present; credit_applied is invoice meta.
    collected = round(
        cash_collected
        + float(receipt_allocated or 0)
        + float(credit_note_allocated or 0)
        + float(credit_applied or 0)
        + float(settlement_allocated or 0),
        2,
    )
    net = round(float(amounts.get("net") or 0), 2)
    outstanding = round(max(0.0, net - collected), 2)
    status = payment_status(net, collected)
    enriched = dict(amounts)
    enriched["collected"] = collected
    enriched["outstanding"] = outstanding
    enriched["payment_status"] = status
    enriched["cash_collected"] = cash_collected
    enriched["receipt_allocated"] = round(float(receipt_allocated or 0), 2)
    enriched["credit_note_allocated"] = round(float(credit_note_allocated or 0), 2)
    enriched["credit_applied"] = round(float(credit_applied or 0), 2)
    enriched["settlement_allocated"] = round(float(settlement_allocated or 0), 2)
    return enriched


def resolve_receipt_allocations(
    receipt_amount: float,
    *,
    allocation_invoice_id: Optional[str] = None,
    allocations: Optional[list[dict]] = None,
    open_invoices: Optional[list[dict]] = None,
    selected_outstanding: Optional[float] = None,
) -> tuple[list[dict], float]:
    """Resolve allocations for a receipt.

    - Explicit ``allocations`` win when provided (validated/capped by caller).
    - Else if ``allocation_invoice_id`` set → single-invoice allocation.
    - Else → FIFO across ``open_invoices``.

    Returns ``(allocation_rows, unallocated)``.
    """
    receipt_amount = round(max(float(receipt_amount or 0), 0.0), 2)
    if receipt_amount <= 0:
        return [], 0.0

    if allocations:
        rows: list[dict] = []
        for row in allocations:
            invoice_id = (
                (row.get("invoice_id") or row.get("invoice_voucher_id") or "")
            ).strip()
            amt = round(float(row.get("amount") or 0), 2)
            if invoice_id and amt > PAYMENT_TOLERANCE:
                rows.append({"invoice_id": invoice_id, "amount": amt})
        total = allocated_total(rows)
        if total > receipt_amount + PAYMENT_TOLERANCE:
            raise ValueError("Allocation total cannot exceed receipt amount")
        unallocated = round(max(0.0, receipt_amount - total), 2)
        return rows, unallocated

    invoice_id = (allocation_invoice_id or "").strip()
    if invoice_id:
        outstanding = (
            float(selected_outstanding)
            if selected_outstanding is not None
            else next(
                (
                    float(inv.get("outstanding") or 0)
                    for inv in (open_invoices or [])
                    if (inv.get("id") or "") == invoice_id
                ),
                receipt_amount,
            )
        )
        rows = single_invoice_allocation(receipt_amount, invoice_id, outstanding)
        unallocated = round(max(0.0, receipt_amount - allocated_total(rows)), 2)
        return rows, unallocated

    rows = fifo_allocations(receipt_amount, open_invoices or [])
    unallocated = round(max(0.0, receipt_amount - allocated_total(rows)), 2)
    return rows, unallocated
