"""CRM domain helpers: normalization, WhatsApp links, fingerprints."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.india import normalize_indian_phone, validate_gstin


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def normalize_gstin_optional(gstin: str) -> str:
    raw = (gstin or "").strip().upper()
    if not raw:
        return ""
    return validate_gstin(raw)


def normalize_phone_optional(phone: str) -> str:
    raw = (phone or "").strip()
    if not raw:
        return ""
    return normalize_indian_phone(raw)


def normalize_phone_for_whatsapp(phone: str, *, default_country: str = "91") -> str:
    """Return international digits suitable for wa.me (no +)."""
    digits = re.sub(r"\D", "", (phone or "").strip())
    if not digits:
        raise ValidationError("Mobile number is required for WhatsApp")
    if len(digits) == 10 and digits[0] in "6789":
        return f"{default_country}{digits}"
    if len(digits) == 12 and digits.startswith(default_country):
        return digits
    if len(digits) == 11 and digits.startswith("0"):
        local = digits[1:]
        if len(local) == 10 and local[0] in "6789":
            return f"{default_country}{local}"
    if len(digits) >= 11:
        return digits
    raise ValidationError("Enter a valid mobile number for WhatsApp")


def format_invoice_refs(invoices: List[Dict[str, Any]], *, limit: int = 3) -> str:
    """Compact multi-invoice summary, e.g. ``INV-12 (Rs.1,200.00) +2 more``.

    ``invoices`` are dicts with ``reference`` and ``outstanding`` keys. The
    list is capped so the click-to-chat URL stays a reasonable length.
    """
    parts: List[str] = []
    for invoice in (invoices or [])[: max(int(limit), 1)]:
        ref = str(invoice.get("reference") or "").strip()
        if not ref:
            continue
        outstanding = float(invoice.get("outstanding") or 0)
        parts.append(f"{ref} (Rs.{outstanding:,.2f})" if outstanding > 0 else ref)
    summary = ", ".join(parts)
    extra = len(invoices or []) - max(int(limit), 1)
    if summary and extra > 0:
        summary += f" +{extra} more"
    return summary


def render_payment_reminder_message(
    template: str,
    *,
    customer_name: str,
    business_name: str,
    outstanding_amount: float,
    invoice_refs: str = "",
    invoice_count: int = 0,
    oldest_due_date: str = "",
) -> str:
    amount = f"{float(outstanding_amount):,.2f}"
    mapping = {
        "customer_name": customer_name or "Customer",
        "business_name": business_name or "our business",
        "outstanding_amount": amount,
        "invoice_refs": invoice_refs or "",
        "invoice_count": str(int(invoice_count)) if invoice_count else "",
        "oldest_due_date": oldest_due_date or "",
        # Legacy placeholder kept working; the oldest open invoice date is
        # the closest thing to a due date for aggregate dues.
        "due_date": oldest_due_date or "",
    }
    message = template or (
        "Hello {customer_name}, payment reminder from {business_name}. "
        "Total outstanding across your pending invoices: Rs.{outstanding_amount}."
    )
    try:
        return message.format(**mapping)
    except (KeyError, ValueError, IndexError):
        for key, value in mapping.items():
            message = message.replace("{" + key + "}", str(value))
        return message


def build_whatsapp_click_to_chat_url(phone: str, message: str) -> str:
    intl = normalize_phone_for_whatsapp(phone)
    text = quote(message or "", safe="")
    return f"https://wa.me/{intl}?text={text}"


def activity_type_key(label: str) -> str:
    return (
        (label or "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
    )


def lead_row_fingerprint(row: Dict[str, Any]) -> str:
    """Stable fingerprint for import idempotency (row content, not row number)."""
    parts = [
        str(row.get("name") or row.get("lead_name") or "").strip().lower(),
        str(row.get("phone") or row.get("phone_number") or "").strip(),
        str(row.get("email") or "").strip().lower(),
        str(row.get("gstin") or "").strip().upper(),
        str(row.get("source") or "").strip().lower(),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_bytes_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes or b"").hexdigest()


def optional_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
