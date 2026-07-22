"""India-standard vendor create/edit form fields."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.parties.vendors.entities import Vendor, VendorInput
from vaybooks.bms.ui.components.party_form_fields import render_party_address_tax_fields


def _vendor_has_banking(vendor: Optional[Vendor]) -> bool:
    if not vendor:
        return False
    return bool(
        vendor.bank_account_holder
        or vendor.bank_account_number
        or vendor.bank_ifsc
        or vendor.bank_name
    )


def render_vendor_form(
    key_prefix: str,
    vendor: Optional[Vendor] = None,
) -> VendorInput:
    col_name, col_contact = st.columns(2)
    vendor_name = col_name.text_input(
        "Vendor Name *",
        value=vendor.vendor_name if vendor else "",
        key=f"{key_prefix}_name",
    )
    contact_person = col_contact.text_input(
        "Contact Person",
        value=vendor.contact_person if vendor else "",
        key=f"{key_prefix}_contact",
    )
    col_phone, col_alt, col_email = st.columns(3)
    phone_number = col_phone.text_input(
        "Phone Number *",
        value=vendor.phone_number if vendor else "",
        key=f"{key_prefix}_phone",
        placeholder="10-digit mobile",
    )
    alternate_phone_number = col_alt.text_input(
        "Alternate Phone",
        value=vendor.alternate_phone_number or "" if vendor else "",
        key=f"{key_prefix}_alt",
    )
    email = col_email.text_input(
        "Email",
        value=vendor.email if vendor else "",
        key=f"{key_prefix}_email",
    )

    tax_fields = render_party_address_tax_fields(
        key_prefix,
        party=vendor,
        registration_type_enum=PartyRegistrationType,
    )

    with st.expander("Banking", expanded=_vendor_has_banking(vendor)):
        col_holder, col_bank = st.columns(2)
        bank_account_holder = col_holder.text_input(
            "Account Holder Name",
            value=vendor.bank_account_holder if vendor else "",
            key=f"{key_prefix}_bank_holder",
        )
        bank_name = col_bank.text_input(
            "Bank Name",
            value=vendor.bank_name if vendor else "",
            key=f"{key_prefix}_bank_name",
        )
        col_acct, col_ifsc = st.columns(2)
        bank_account_number = col_acct.text_input(
            "Account Number",
            value=vendor.bank_account_number if vendor else "",
            key=f"{key_prefix}_bank_acct",
        )
        bank_ifsc = col_ifsc.text_input(
            "IFSC",
            value=vendor.bank_ifsc if vendor else "",
            key=f"{key_prefix}_bank_ifsc",
            placeholder="HDFC0001234",
        )

    with st.expander("Notes", expanded=bool(vendor and vendor.notes)):
        notes = st.text_area(
            "Notes",
            value=vendor.notes if vendor else "",
            key=f"{key_prefix}_notes",
            height=68,
        )

    return VendorInput(
        vendor_name=vendor_name,
        phone_number=phone_number,
        alternate_phone_number=alternate_phone_number or None,
        email=email,
        contact_person=contact_person,
        address_line1=tax_fields["address_line1"],
        address_line2=tax_fields["address_line2"],
        city=tax_fields["city"],
        state_code=tax_fields["state_code"],
        pincode=tax_fields["pincode"],
        country=tax_fields["country"],
        gstin=tax_fields["gstin"],
        pan=tax_fields["pan"],
        registration_type=tax_fields["registration_type"],
        msme_number=tax_fields["msme_number"],
        bank_account_holder=bank_account_holder,
        bank_account_number=bank_account_number,
        bank_ifsc=bank_ifsc,
        bank_name=bank_name,
        notes=notes,
    )
