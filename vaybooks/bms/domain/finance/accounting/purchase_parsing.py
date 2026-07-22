"""Parse purchase bill vouchers into display/report rows."""

from __future__ import annotations

import json
from typing import Optional

PURCHASE_BILL_PREFIX = "Purchase bill "
LINES_MARKER = "LINES_JSON:"


def parse_vendor_bill_number(description: str) -> str:
    if not description:
        return ""
    first_line = description.split("\n", 1)[0].strip()
    if first_line.startswith(PURCHASE_BILL_PREFIX):
        return first_line[len(PURCHASE_BILL_PREFIX) :].strip()
    return ""


def parse_purchase_lines_from_description(description: str) -> list[dict]:
    if not description:
        return []
    for line in description.splitlines():
        stripped = line.strip()
        if stripped.startswith(LINES_MARKER):
            payload = stripped[len(LINES_MARKER) :].strip()
            if not payload:
                return []
            try:
                data = json.loads(payload)
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                return []
    return []


def serialize_purchase_lines(lines: list[dict]) -> str:
    return f"{LINES_MARKER}{json.dumps(lines, separators=(',', ':'))}"


def build_purchase_description(vendor_bill_number: str, lines: list[dict]) -> str:
    number = (vendor_bill_number or "").strip()
    parts = [f"{PURCHASE_BILL_PREFIX}{number}" if number else PURCHASE_BILL_PREFIX.strip()]
    if lines:
        parts.append(serialize_purchase_lines(lines))
    return "\n".join(parts)


def purchase_amounts_from_lines(lines) -> dict:
    total = 0.0
    paid = 0.0
    vendor_name = ""
    vendor_account_id = None
    for line in lines:
        desc = getattr(line, "description", None) or (
            line.get("description") if isinstance(line, dict) else ""
        )
        desc = (desc or "").strip()
        debit = float(
            getattr(line, "debit_amount", 0)
            if not isinstance(line, dict)
            else (line.get("debit_amount") or 0)
        )
        credit = float(
            getattr(line, "credit_amount", 0)
            if not isinstance(line, dict)
            else (line.get("credit_amount") or 0)
        )
        account_id = (
            getattr(line, "account_id", None)
            if not isinstance(line, dict)
            else line.get("account_id")
        )
        account_name = (
            getattr(line, "account_name", "")
            if not isinstance(line, dict)
            else (line.get("account_name") or "")
        )
        if desc == "Payable to vendor" and credit > 0:
            total = credit
            vendor_name = account_name or vendor_name
            vendor_account_id = account_id or vendor_account_id
        elif desc == "Payment made" and credit > 0:
            paid = credit
    total = round(total, 2)
    paid = round(paid, 2)
    return {
        "total": total,
        "paid": paid,
        "outstanding": round(total - paid, 2),
        "vendor_name": vendor_name,
        "vendor_account_id": vendor_account_id,
    }


def purchase_row_from_voucher(voucher) -> dict:
    amounts = purchase_amounts_from_lines(voucher.lines)
    description = voucher.description or ""
    bill_number = parse_vendor_bill_number(description)
    line_items = parse_purchase_lines_from_description(description)
    bill_date = voucher.voucher_date
    if hasattr(bill_date, "date"):
        bill_date = bill_date.date() if callable(getattr(bill_date, "date", None)) else bill_date
    voucher_type = getattr(voucher, "voucher_type", None)
    type_value = voucher_type.value if hasattr(voucher_type, "value") else str(voucher_type or "")
    return {
        "id": voucher.id,
        "vendor_bill_number": bill_number,
        "vendor_name": amounts["vendor_name"],
        "vendor_account_id": amounts["vendor_account_id"],
        "bill_date": bill_date,
        "total": amounts["total"],
        "paid": amounts["paid"],
        "outstanding": amounts["outstanding"],
        "voucher_number": voucher.voucher_number,
        "voucher_type": type_value,
        "line_items": line_items,
        "reference_order_id": getattr(voucher, "reference_order_id", None),
        "reference_po_id": getattr(voucher, "reference_po_id", None),
        "reference_grn_id": getattr(voucher, "reference_grn_id", None),
        "reference_service_id": getattr(voucher, "reference_service_id", None),
    }


def vendor_payment_row_from_voucher(voucher) -> dict:
    """Compat row for legacy VENDOR_PAYMENT vouchers."""
    amount = 0.0
    vendor_name = ""
    vendor_account_id = None
    for line in voucher.lines:
        desc = (line.description or "").strip()
        if desc == "Purchase from vendor" and line.debit_amount > 0:
            amount = line.debit_amount
        elif desc == "Payable to vendor" and line.credit_amount > 0:
            vendor_name = line.account_name
            vendor_account_id = line.account_id
    bill_date = voucher.voucher_date
    if hasattr(bill_date, "date"):
        bill_date = bill_date.date() if callable(getattr(bill_date, "date", None)) else bill_date
    return {
        "id": voucher.id,
        "vendor_bill_number": (voucher.description or "").strip()[:80],
        "vendor_name": vendor_name,
        "vendor_account_id": vendor_account_id,
        "bill_date": bill_date,
        "total": round(amount, 2),
        "paid": round(amount, 2),
        "outstanding": 0.0,
        "voucher_number": voucher.voucher_number,
        "voucher_type": "Vendor Payment",
        "line_items": [],
        "reference_order_id": getattr(voucher, "reference_order_id", None),
        "reference_po_id": None,
        "reference_grn_id": None,
        "reference_service_id": getattr(voucher, "reference_service_id", None),
    }
