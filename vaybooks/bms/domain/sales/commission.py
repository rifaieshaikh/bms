"""Sales commission calculation helpers."""

from __future__ import annotations

from typing import Any, Optional

from vaybooks.bms.domain.shared.exceptions import ValidationError

_COMMISSION_TYPES = {"percentage", "flat"}


def compute_commission_amount(
    *,
    commission_type: str,
    commission_rate: float,
    taxable_amount: float,
    commission_amount: Optional[float] = None,
) -> float:
    """Compute commission from taxable (pre-GST) base.

    If ``commission_amount`` is provided for flat (or as override), it is used
    after rounding; percentage always recomputes from taxable × rate.
    """
    ctype = (commission_type or "").strip().lower()
    if ctype not in _COMMISSION_TYPES:
        raise ValidationError("Commission type must be percentage or flat")
    taxable = round(float(taxable_amount or 0), 2)
    if taxable <= 0:
        raise ValidationError("Taxable amount must be positive to compute commission")
    rate = round(float(commission_rate or 0), 4)
    if ctype == "percentage":
        if rate < 0 or rate > 100:
            raise ValidationError("Commission percentage must be between 0 and 100")
        amount = round(taxable * rate / 100.0, 2)
    else:
        amount = round(
            float(commission_amount if commission_amount is not None else rate), 2
        )
    if amount <= 0:
        raise ValidationError("Commission amount must be positive")
    if amount >= taxable:
        raise ValidationError("Commission amount must be less than taxable amount")
    return amount


def normalize_commission_payload(
    raw: Optional[dict],
    *,
    taxable_amount: float,
) -> Optional[dict[str, Any]]:
    """Validate and normalize a commission dict for invoice JSON / posting."""
    if not raw:
        return None
    agent_id = str(raw.get("agent_id") or "").strip()
    if not agent_id:
        return None
    ctype = str(raw.get("commission_type") or "percentage").strip().lower()
    rate = float(raw.get("commission_rate") or 0)
    provided = raw.get("commission_amount")
    amount = compute_commission_amount(
        commission_type=ctype,
        commission_rate=rate,
        taxable_amount=taxable_amount,
        commission_amount=float(provided) if provided is not None else None,
    )
    paid = bool(raw.get("commission_paid"))
    pay_account_id = str(raw.get("pay_account_id") or "").strip()
    if paid and not pay_account_id:
        raise ValidationError(
            "A cash/bank account is required when commission is paid with the invoice"
        )
    return {
        "agent_id": agent_id,
        "agent_name": str(raw.get("agent_name") or "").strip(),
        "commission_type": ctype,
        "commission_rate": rate if ctype == "percentage" else amount,
        "commission_amount": amount,
        "commission_paid": paid,
        "pay_account_id": pay_account_id if paid else "",
    }


def parse_sales_commission(description: str) -> Optional[dict]:
    """Extract commission object from a sales invoice voucher description."""
    import json

    if not description or "\n" not in description:
        return None
    try:
        data = json.loads(description.split("\n", 1)[1].strip())
        commission = data.get("commission")
        return commission if isinstance(commission, dict) else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def compute_commission_reversal_for_return(
    *,
    commission_amount: float,
    invoice_taxable: float,
    invoice_items: list[dict],
    return_lines: list[Any],
    return_amount: float = 0.0,
    invoice_gross: float = 0.0,
) -> float:
    """Proportional commission clawback for quantities returned against an invoice.

    Prefers returned taxable share of invoice taxable. Falls back to return
    amount / invoice gross when taxable breakdown is unavailable.
    """
    commission_amount = round(float(commission_amount or 0), 2)
    if commission_amount <= 0:
        return 0.0

    invoiced: dict[str, dict[str, float]] = {}
    for item in invoice_items or []:
        product_id = str(item.get("product_id") or "").strip()
        if not product_id:
            continue
        bucket = invoiced.setdefault(product_id, {"qty": 0.0, "taxable": 0.0})
        bucket["qty"] = round(bucket["qty"] + float(item.get("qty") or 0), 2)
        bucket["taxable"] = round(
            bucket["taxable"] + float(item.get("taxable_amount") or 0), 2
        )

    returned_taxable = 0.0
    for raw in return_lines or []:
        if isinstance(raw, dict):
            product_id = str(raw.get("product_id") or "").strip()
            qty = float(raw.get("qty") or 0)
        else:
            product_id = str(getattr(raw, "product_id", "") or "").strip()
            qty = float(getattr(raw, "qty", 0) or 0)
        if qty <= 0 or product_id not in invoiced:
            continue
        inv = invoiced[product_id]
        if inv["qty"] <= 0:
            continue
        share = min(qty / inv["qty"], 1.0)
        returned_taxable = round(returned_taxable + inv["taxable"] * share, 2)

    invoice_taxable = round(float(invoice_taxable or 0), 2)
    if returned_taxable > 0 and invoice_taxable > 0:
        ratio = min(returned_taxable / invoice_taxable, 1.0)
        return round(min(commission_amount * ratio, commission_amount), 2)

    return_amount = round(float(return_amount or 0), 2)
    invoice_gross = round(float(invoice_gross or 0), 2)
    if return_amount > 0 and invoice_gross > 0:
        ratio = min(return_amount / invoice_gross, 1.0)
        return round(min(commission_amount * ratio, commission_amount), 2)
    return 0.0


def serialize_return_commission_note(
    description: str, commission: Optional[dict]
) -> str:
    """Append commission JSON to a sales-return voucher description."""
    import json

    base = (description or "").strip()
    if not commission:
        return base
    payload = {"commission": commission}
    return f"{base}\n{json.dumps(payload, ensure_ascii=False)}"
