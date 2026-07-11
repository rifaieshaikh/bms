"""India-standard customer create/edit form fields."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from vaybooks.bms.domain.customers.entities import Customer, CustomerInput
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui.components.party_form_fields import render_party_address_tax_fields


def render_customer_form(
    key_prefix: str,
    customer: Optional[Customer] = None,
) -> CustomerInput:
    st.markdown("**Basic**")
    customer_name = st.text_input(
        "Customer Name *",
        value=customer.customer_name if customer else "",
        key=f"{key_prefix}_name",
    )
    contact_person = st.text_input(
        "Contact Person",
        value=customer.contact_person if customer else "",
        key=f"{key_prefix}_contact",
    )
    col_phone, col_alt = st.columns(2)
    phone_number = col_phone.text_input(
        "Phone Number *",
        value=customer.phone_number if customer else "",
        key=f"{key_prefix}_phone",
        placeholder="10-digit mobile",
    )
    alternate_phone_number = col_alt.text_input(
        "Alternate Phone",
        value=customer.alternate_phone_number or "" if customer else "",
        key=f"{key_prefix}_alt",
    )
    email = st.text_input(
        "Email",
        value=customer.email if customer else "",
        key=f"{key_prefix}_email",
    )

    tax_fields = render_party_address_tax_fields(
        key_prefix,
        party=customer,
        registration_type_enum=PartyRegistrationType,
    )

    notes = st.text_area(
        "Notes",
        value=customer.notes if customer else "",
        key=f"{key_prefix}_notes",
    )

    return CustomerInput(
        customer_name=customer_name,
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
        notes=notes,
    )
