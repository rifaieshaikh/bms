"""India-standard customer create/edit form fields."""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st

from vaybooks.bms.domain.parties.customers.entities import Customer, CustomerInput
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui.components.common.location_fields import (
    render_party_location_multiselect,
)
from vaybooks.bms.ui.components.common.party_form_fields import render_party_address_tax_fields


def render_customer_form(
    key_prefix: str,
    customer: Optional[Customer] = None,
    segment_options: Optional[Dict[str, str]] = None,
    *,
    require_name: bool = True,
    require_phone: bool = True,
    services: dict | None = None,
) -> CustomerInput:
    """Render customer fields.

    ``segment_options`` maps display name -> segment id (active customer segments).
    """
    col_name, col_contact = st.columns(2)
    name_label = "Customer Name *" if require_name else "Customer Name"
    customer_name = col_name.text_input(
        name_label,
        value=customer.customer_name if customer else "",
        key=f"{key_prefix}_name",
    )
    contact_person = col_contact.text_input(
        "Contact Person",
        value=customer.contact_person if customer else "",
        key=f"{key_prefix}_contact",
    )
    col_phone, col_alt, col_email = st.columns(3)
    phone_label = "Phone Number *" if require_phone else "Phone Number"
    phone_number = col_phone.text_input(
        phone_label,
        value=customer.phone_number if customer else "",
        key=f"{key_prefix}_phone",
        placeholder="10-digit mobile",
    )
    alternate_phone_number = col_alt.text_input(
        "Alternate Phone",
        value=customer.alternate_phone_number or "" if customer else "",
        key=f"{key_prefix}_alt",
    )
    email = col_email.text_input(
        "Email",
        value=customer.email if customer else "",
        key=f"{key_prefix}_email",
    )

    tax_fields = render_party_address_tax_fields(
        key_prefix,
        party=customer,
        registration_type_enum=PartyRegistrationType,
    )

    segment_ids: List[str] = list(customer.segment_ids or []) if customer else []
    opts = segment_options or {}
    if opts:
        id_to_name = {sid: name for name, sid in opts.items()}
        current_names = []
        if customer:
            for sid in customer.segment_ids or []:
                name = id_to_name.get(sid)
                if name:
                    current_names.append(name)
        selected = st.multiselect(
            "Segments",
            list(opts.keys()),
            default=current_names,
            key=f"{key_prefix}_segments",
            placeholder="Select segments…",
        )
        segment_ids = [opts[n] for n in selected if n in opts]
    else:
        st.caption("No party segments defined yet. Add them under Parties → Segments.")

    is_commission_agent = st.checkbox(
        "Is commission agent",
        value=bool(customer.is_commission_agent) if customer else False,
        key=f"{key_prefix}_is_commission_agent",
        help="Creates / links a Commission Agent party with a payable ledger account.",
    )
    if customer and customer.commission_agent_id:
        st.caption(f"Linked commission agent id: `{customer.commission_agent_id}`")

    with st.expander("Notes", expanded=bool(customer and customer.notes)):
        notes = st.text_area(
            "Notes",
            value=customer.notes if customer else "",
            key=f"{key_prefix}_notes",
            height=68,
        )

    if services is not None:
        location_ids = render_party_location_multiselect(
            key_prefix,
            services,
            customer.location_ids if customer else None,
        )
    elif customer:
        location_ids = list(customer.location_ids or [])
    else:
        location_ids = []

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
        segment_ids=segment_ids,
        location_ids=location_ids,
        is_commission_agent=is_commission_agent,
    )
