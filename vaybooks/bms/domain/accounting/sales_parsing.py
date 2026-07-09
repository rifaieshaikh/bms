"""Parse store sales invoice vouchers into display/report rows."""

from __future__ import annotations

from typing import Optional

STORE_INVOICE_PREFIX = "Store invoice "


def parse_store_invoice_number(description: str) -> str:
    if not description:
        return ""
    first_line = description.split("\n", 1)[0].strip()
    if first_line.startswith(STORE_INVOICE_PREFIX):
        return first_line[len(STORE_INVOICE_PREFIX) :].strip()
    return ""


def sales_amounts_from_lines(lines, discount_account_id: Optional[str] = None) -> dict:
    """Parse gross, discount, collected, party from cash sales voucher lines."""
    gross = 0.0
    discount = 0.0
    collected = 0.0
    party_name = ""
    customer_account_id = None
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
        if desc == "Sales invoice" and credit > 0:
            gross = credit
        elif discount_account_id and account_id == discount_account_id and debit > 0:
            discount = debit
        elif desc == "Discount allowed" and debit > 0:
            discount = debit
        elif desc == "Cash/Bank received" and debit > 0:
            collected = debit
        elif debit > 0 and desc not in (
            "Sales invoice",
            "Discount allowed",
            "Cash/Bank received",
        ):
            party_name = account_name or party_name
            customer_account_id = account_id or customer_account_id
    net = round(gross - discount, 2)
    return {
        "gross": round(gross, 2),
        "discount": round(discount, 2),
        "net": net,
        "collected": round(collected, 2),
        "outstanding": round(net - collected, 2),
        "party_name": party_name,
        "customer_account_id": customer_account_id,
    }


def sales_row_from_voucher(voucher, discount_account_id: Optional[str] = None) -> dict:
    """Build a store-sales list row (not a voucher card)."""
    amounts = sales_amounts_from_lines(voucher.lines, discount_account_id)
    description = voucher.description or ""
    store_number = parse_store_invoice_number(description)
    sale_date = voucher.voucher_date
    if hasattr(sale_date, "date"):
        sale_date = sale_date.date() if callable(getattr(sale_date, "date", None)) else sale_date
    return {
        "id": voucher.id,
        "store_invoice_number": store_number,
        "party_name": amounts["party_name"],
        "customer_account_id": amounts["customer_account_id"],
        "sale_date": sale_date,
        "gross": amounts["gross"],
        "discount": amounts["discount"],
        "net": amounts["net"],
        "collected": amounts["collected"],
        "outstanding": amounts["outstanding"],
        "voucher_number": voucher.voucher_number,
    }
