"""Shared India-standard validation for customers and vendors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.india import (
    normalize_indian_phone,
    validate_bank_account,
    validate_gstin,
    validate_ifsc,
    validate_pan,
    validate_pincode,
    validate_state_code,
)


def _optional_pincode(pincode: str) -> str:
    pin = (pincode or "").strip()
    if not pin:
        return ""
    return validate_pincode(pin)


def _optional_state_code(state_code: str) -> str:
    code = (state_code or "").strip()
    if not code:
        return ""
    return validate_state_code(code)


@dataclass
class NormalizedPartyFields:
    name: str
    phone_number: str
    alternate_phone_number: Optional[str]
    email: str
    contact_person: str
    address_line1: str
    address_line2: str
    city: str
    state_code: str
    pincode: str
    country: str
    gstin: str
    pan: str
    registration_type: PartyRegistrationType
    msme_number: str


def normalize_party_fields(
    *,
    name: str,
    phone_number: str,
    alternate_phone_number: Optional[str] = None,
    email: str = "",
    contact_person: str = "",
    address_line1: str = "",
    address_line2: str = "",
    city: str = "",
    state_code: str = "",
    pincode: str = "",
    country: str = "India",
    gstin: str = "",
    pan: str = "",
    registration_type: PartyRegistrationType = PartyRegistrationType.UNREGISTERED,
    msme_number: str = "",
) -> NormalizedPartyFields:
    if not (name or "").strip():
        raise ValidationError("Name is required")
    if not (phone_number or "").strip():
        raise ValidationError("Phone number is required")

    phone = normalize_indian_phone(phone_number)
    alt_phone = None
    if alternate_phone_number and alternate_phone_number.strip():
        alt_phone = normalize_indian_phone(alternate_phone_number)

    state = _optional_state_code(state_code)
    pin = _optional_pincode(pincode)
    pan_norm = validate_pan(pan)
    gstin_norm = validate_gstin(gstin, state_code=state or None, pan=pan_norm or None)

    if registration_type == PartyRegistrationType.REGISTERED and not gstin_norm:
        raise ValidationError("GSTIN is required for registered parties")

    return NormalizedPartyFields(
        name=name.strip(),
        phone_number=phone,
        alternate_phone_number=alt_phone,
        email=(email or "").strip(),
        contact_person=(contact_person or "").strip(),
        address_line1=(address_line1 or "").strip(),
        address_line2=(address_line2 or "").strip(),
        city=(city or "").strip(),
        state_code=state,
        pincode=pin,
        country=(country or "").strip() or "India",
        gstin=gstin_norm,
        pan=pan_norm,
        registration_type=registration_type,
        msme_number=(msme_number or "").strip(),
    )


@dataclass
class NormalizedBankingFields:
    bank_account_holder: str
    bank_account_number: str
    bank_ifsc: str
    bank_name: str


def normalize_banking_fields(
    *,
    bank_account_holder: str = "",
    bank_account_number: str = "",
    bank_ifsc: str = "",
    bank_name: str = "",
) -> NormalizedBankingFields:
    account_number = validate_bank_account(bank_account_number)
    ifsc = validate_ifsc(bank_ifsc)

    if account_number and not ifsc:
        raise ValidationError("IFSC is required when bank account number is provided")
    if ifsc and not account_number:
        raise ValidationError("Bank account number is required when IFSC is provided")

    return NormalizedBankingFields(
        bank_account_holder=(bank_account_holder or "").strip(),
        bank_account_number=account_number,
        bank_ifsc=ifsc,
        bank_name=(bank_name or "").strip(),
    )
