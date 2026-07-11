"""India-specific validation helpers for addresses, tax IDs, and banking."""

from __future__ import annotations

import re
from typing import Optional

from vaybooks.bms.domain.shared.exceptions import ValidationError

INDIAN_STATES: list[dict[str, str]] = [
    {"code": "01", "name": "Jammu & Kashmir"},
    {"code": "02", "name": "Himachal Pradesh"},
    {"code": "03", "name": "Punjab"},
    {"code": "04", "name": "Chandigarh"},
    {"code": "05", "name": "Uttarakhand"},
    {"code": "06", "name": "Haryana"},
    {"code": "07", "name": "Delhi"},
    {"code": "08", "name": "Rajasthan"},
    {"code": "09", "name": "Uttar Pradesh"},
    {"code": "10", "name": "Bihar"},
    {"code": "11", "name": "Sikkim"},
    {"code": "12", "name": "Arunachal Pradesh"},
    {"code": "13", "name": "Nagaland"},
    {"code": "14", "name": "Manipur"},
    {"code": "15", "name": "Mizoram"},
    {"code": "16", "name": "Tripura"},
    {"code": "17", "name": "Meghalaya"},
    {"code": "18", "name": "Assam"},
    {"code": "19", "name": "West Bengal"},
    {"code": "20", "name": "Jharkhand"},
    {"code": "21", "name": "Odisha"},
    {"code": "22", "name": "Chhattisgarh"},
    {"code": "23", "name": "Madhya Pradesh"},
    {"code": "24", "name": "Gujarat"},
    {"code": "26", "name": "Dadra and Nagar Haveli and Daman and Diu"},
    {"code": "27", "name": "Maharashtra"},
    {"code": "29", "name": "Karnataka"},
    {"code": "30", "name": "Goa"},
    {"code": "31", "name": "Lakshadweep"},
    {"code": "32", "name": "Kerala"},
    {"code": "33", "name": "Tamil Nadu"},
    {"code": "34", "name": "Puducherry"},
    {"code": "35", "name": "Andaman and Nicobar Islands"},
    {"code": "36", "name": "Telangana"},
    {"code": "37", "name": "Andhra Pradesh"},
    {"code": "38", "name": "Ladakh"},
]

_STATE_BY_CODE = {s["code"]: s["name"] for s in INDIAN_STATES}

GSTIN_RE = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PINCODE_RE = re.compile(r"^[0-9]{6}$")


def state_name_for_code(state_code: str) -> str:
    return _STATE_BY_CODE.get(state_code, state_code)


def normalize_indian_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", (raw or "").strip())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise ValidationError("Enter a valid 10-digit Indian mobile number")
    return digits


def validate_pincode(pincode: str) -> str:
    pin = (pincode or "").strip()
    if not PINCODE_RE.match(pin):
        raise ValidationError("PIN code must be exactly 6 digits")
    return pin


def validate_state_code(state_code: str) -> str:
    code = (state_code or "").strip().zfill(2)
    if code not in _STATE_BY_CODE:
        raise ValidationError("Select a valid Indian state")
    return code


def validate_pan(pan: str) -> str:
    value = (pan or "").strip().upper()
    if not value:
        return ""
    if not PAN_RE.match(value):
        raise ValidationError("Invalid PAN format (e.g. ABCDE1234F)")
    return value


def validate_gstin(
    gstin: str,
    state_code: Optional[str] = None,
    pan: Optional[str] = None,
) -> str:
    value = (gstin or "").strip().upper()
    if not value:
        return ""
    if not GSTIN_RE.match(value):
        raise ValidationError("Invalid GSTIN format")
    if state_code:
        normalized_state = validate_state_code(state_code)
        if value[:2] != normalized_state:
            raise ValidationError("GSTIN state code does not match selected state")
    if pan:
        embedded_pan = value[2:12]
        if embedded_pan != pan:
            raise ValidationError("GSTIN embedded PAN does not match vendor PAN")
    return value


def validate_ifsc(ifsc: str) -> str:
    value = (ifsc or "").strip().upper()
    if not value:
        return ""
    if not IFSC_RE.match(value):
        raise ValidationError("Invalid IFSC format (e.g. HDFC0001234)")
    return value


def validate_bank_account(account_number: str) -> str:
    digits = re.sub(r"\D", "", (account_number or "").strip())
    if not digits:
        return ""
    if len(digits) < 9 or len(digits) > 18:
        raise ValidationError("Bank account number must be 9 to 18 digits")
    return digits


def format_address(
    *,
    address_line1: str = "",
    address_line2: str = "",
    city: str = "",
    state_code: str = "",
    pincode: str = "",
    country: str = "India",
) -> str:
    state_label = state_name_for_code(state_code) if state_code else ""
    parts = [
        (address_line1 or "").strip(),
        (address_line2 or "").strip(),
        (city or "").strip(),
        state_label,
        (pincode or "").strip(),
        (country or "").strip(),
    ]
    return ", ".join(p for p in parts if p)


def mask_bank_account(account_number: str) -> str:
    digits = re.sub(r"\D", "", account_number or "")
    if len(digits) <= 4:
        return digits or "—"
    return f"{'X' * (len(digits) - 4)}{digits[-4:]}"


# Union territories that use UTGST (not SGST) on intra-UT supply.
UTGST_STATE_CODES = frozenset({"04", "26", "31", "35", "38"})

MATERIAL_PURCHASE_EXPENSE_NAME = "Material Purchase Expense"
CGST_INPUT_ACCOUNT_NAME = "CGST Input"
SGST_INPUT_ACCOUNT_NAME = "SGST Input"
IGST_INPUT_ACCOUNT_NAME = "IGST Input"
UTGST_INPUT_ACCOUNT_NAME = "UTGST Input"
CGST_OUTPUT_ACCOUNT_NAME = "CGST Output"
SGST_OUTPUT_ACCOUNT_NAME = "SGST Output"
IGST_OUTPUT_ACCOUNT_NAME = "IGST Output"
UTGST_OUTPUT_ACCOUNT_NAME = "UTGST Output"


def _compute_supply_gst(
    taxable_amount: float,
    gst_rate: float,
    *,
    charge_gst: bool,
    business_state_code: str = "",
    party_state_code: str = "",
) -> "GstBreakdown":
    from vaybooks.bms.domain.shared.item_tax import GstBreakdown

    taxable = round(max(float(taxable_amount or 0), 0.0), 2)
    if taxable <= 0:
        return GstBreakdown()

    if not charge_gst or not gst_rate:
        return GstBreakdown(taxable_amount=taxable)

    rate = float(gst_rate)
    biz = (business_state_code or "").strip().zfill(2)
    party = (party_state_code or "").strip().zfill(2)
    total_tax = round(taxable * rate / 100.0, 2)

    if biz and party and biz == party:
        half = round(total_tax / 2.0, 2)
        remainder = round(total_tax - half, 2)
        if biz in UTGST_STATE_CODES:
            return GstBreakdown(
                taxable_amount=taxable,
                cgst_amount=half,
                utgst_amount=remainder,
            )
        return GstBreakdown(
            taxable_amount=taxable,
            cgst_amount=half,
            sgst_amount=remainder,
        )

    return GstBreakdown(
        taxable_amount=taxable,
        igst_amount=total_tax,
    )


def compute_purchase_gst(
    taxable_amount: float,
    gst_rate: float,
    *,
    vendor_registered: bool,
    business_state_code: str = "",
    vendor_state_code: str = "",
) -> "GstBreakdown":
    return _compute_supply_gst(
        taxable_amount,
        gst_rate,
        charge_gst=vendor_registered,
        business_state_code=business_state_code,
        party_state_code=vendor_state_code,
    )


def compute_sales_gst(
    taxable_amount: float,
    gst_rate: float,
    *,
    business_registered: bool,
    business_state_code: str = "",
    customer_state_code: str = "",
) -> "GstBreakdown":
    return _compute_supply_gst(
        taxable_amount,
        gst_rate,
        charge_gst=business_registered,
        business_state_code=business_state_code,
        party_state_code=customer_state_code,
    )
