"""Parse store sales invoice vouchers into display/report rows."""

from __future__ import annotations

from typing import Optional

from vaybooks.bms.domain.finance.accounting.settlement import (
    credit_applied_from_description,
    enrich_amounts_with_settlements,
    payment_status,
    payment_status_label,
)

STORE_INVOICE_PREFIX = "Store invoice "


def parse_store_invoice_number(description: str) -> str:
    if not description:
        return ""
    first_line = description.split("\n", 1)[0].strip()
    if first_line.startswith(STORE_INVOICE_PREFIX):
        return first_line[len(STORE_INVOICE_PREFIX) :].strip()
    return ""


def sales_amounts_from_lines(lines, discount_account_id: Optional[str] = None) -> dict:
    """Parse gross, discount, collected, party from cash sales voucher lines.

    ``gross`` / ``net`` are the invoice total the customer owes (taxable + tax).
    For GST vouchers the Sales credit is taxable only; CGST/SGST/IGST/UTGST
    output credits are added so outstanding is against grand total.
    """
    taxable = 0.0
    tax_total = 0.0
    discount = 0.0
    collected = 0.0
    advance_applied = 0.0
    party_name = ""
    customer_account_id = None
    _GST_OUTPUT_DESCS = {
        "CGST output",
        "SGST output",
        "IGST output",
        "UTGST output",
    }
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
            taxable = credit
        elif desc in _GST_OUTPUT_DESCS and credit > 0:
            tax_total = round(tax_total + credit, 2)
        elif discount_account_id and account_id == discount_account_id and debit > 0:
            discount = debit
        elif desc == "Discount allowed" and debit > 0:
            discount = debit
        elif desc == "Cash/Bank received" and debit > 0:
            collected = debit
        elif desc == "Advance applied" and debit > 0:
            advance_applied += debit
        elif debit > 0 and desc not in (
            "Sales invoice",
            "Discount allowed",
            "Cash/Bank received",
            "Advance applied",
        ):
            party_name = account_name or party_name
            customer_account_id = account_id or customer_account_id
    cash_received = round(collected, 2)
    collected = round(collected + advance_applied, 2)
    # Invoice total including tax (GST output credits); equals taxable when no GST.
    gross = round(taxable + tax_total, 2)
    net = round(gross - discount, 2)
    outstanding = round(max(0.0, net - collected), 2)
    status = payment_status(net, collected)
    return {
        "gross": gross,
        "taxable": round(taxable, 2),
        "tax": round(tax_total, 2),
        "discount": round(discount, 2),
        "net": net,
        "collected": collected,
        "cash_received": cash_received,
        "advance_applied": round(advance_applied, 2),
        "outstanding": outstanding,
        "payment_status": status,
        "party_name": party_name,
        "customer_account_id": customer_account_id,
    }


def sales_row_from_voucher(
    voucher,
    discount_account_id: Optional[str] = None,
    *,
    receipt_allocated: float = 0.0,
    credit_note_allocated: float = 0.0,
    settlement_allocated: float = 0.0,
) -> dict:
    """Build a store-sales list row (not a voucher card)."""
    amounts = sales_amounts_from_lines(voucher.lines, discount_account_id)
    description = voucher.description or ""
    credit_applied = credit_applied_from_description(description)
    amounts = enrich_amounts_with_settlements(
        amounts,
        receipt_allocated=receipt_allocated,
        credit_note_allocated=credit_note_allocated,
        credit_applied=credit_applied,
        settlement_allocated=settlement_allocated,
    )
    store_number = parse_store_invoice_number(description)
    sale_date = voucher.voucher_date
    if hasattr(sale_date, "date"):
        sale_date = sale_date.date() if callable(getattr(sale_date, "date", None)) else sale_date
    financial_year = (getattr(voucher, "financial_year", None) or "").strip()
    if not financial_year and sale_date:
        from vaybooks.bms.domain.shared.financial_year import resolve_financial_year

        financial_year = resolve_financial_year(sale_date)
    return {
        "id": voucher.id,
        "store_invoice_number": store_number,
        "party_name": amounts["party_name"],
        "customer_account_id": amounts["customer_account_id"],
        "sale_date": sale_date,
        "financial_year": financial_year,
        "gross": amounts["gross"],
        "discount": amounts["discount"],
        "net": amounts["net"],
        "collected": amounts["collected"],
        "outstanding": amounts["outstanding"],
        "payment_status": amounts["payment_status"],
        "payment_status_label": payment_status_label(amounts["payment_status"]),
        "reference_project_id": getattr(voucher, "reference_project_id", None),
        "project_name": getattr(voucher, "project_name", None) or "",
    }
