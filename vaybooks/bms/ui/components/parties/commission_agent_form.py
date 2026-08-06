"""India-standard commission agent create/edit form fields."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from vaybooks.bms.domain.parties.commission_agents.entities import (
    CommissionAgent,
    CommissionAgentInput,
)
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui.components.common.location_fields import (
    render_party_location_multiselect,
)
from vaybooks.bms.ui.components.common.party_form_fields import render_party_address_tax_fields


def _agent_has_banking(agent: Optional[CommissionAgent]) -> bool:
    if not agent:
        return False
    return bool(
        agent.bank_account_holder
        or agent.bank_account_number
        or agent.bank_ifsc
        or agent.bank_name
    )


def render_commission_agent_form(
    key_prefix: str,
    agent: Optional[CommissionAgent] = None,
    *,
    services: dict | None = None,
) -> CommissionAgentInput:
    col_name, col_contact = st.columns(2)
    agent_name = col_name.text_input(
        "Agent Name *",
        value=agent.agent_name if agent else "",
        key=f"{key_prefix}_name",
    )
    contact_person = col_contact.text_input(
        "Contact Person",
        value=agent.contact_person if agent else "",
        key=f"{key_prefix}_contact",
    )
    col_phone, col_alt, col_email = st.columns(3)
    phone_number = col_phone.text_input(
        "Phone Number *",
        value=agent.phone_number if agent else "",
        key=f"{key_prefix}_phone",
        placeholder="10-digit mobile",
    )
    alternate_phone_number = col_alt.text_input(
        "Alternate Phone",
        value=agent.alternate_phone_number or "" if agent else "",
        key=f"{key_prefix}_alt",
    )
    email = col_email.text_input(
        "Email",
        value=agent.email if agent else "",
        key=f"{key_prefix}_email",
    )

    tax_fields = render_party_address_tax_fields(
        key_prefix,
        party=agent,
        registration_type_enum=PartyRegistrationType,
    )

    from vaybooks.bms.ui.components.sales.commission_profile_editor import (
        render_commission_profile_editor,
    )

    with st.expander("Commission settings", expanded=True):
        commission_profile = render_commission_profile_editor(
            f"{key_prefix}_profile",
            agent.commission_profile if agent else None,
        )

    with st.expander("Banking", expanded=_agent_has_banking(agent)):
        col_holder, col_bank = st.columns(2)
        bank_account_holder = col_holder.text_input(
            "Account Holder Name",
            value=agent.bank_account_holder if agent else "",
            key=f"{key_prefix}_bank_holder",
        )
        bank_name = col_bank.text_input(
            "Bank Name",
            value=agent.bank_name if agent else "",
            key=f"{key_prefix}_bank_name",
        )
        col_acct, col_ifsc = st.columns(2)
        bank_account_number = col_acct.text_input(
            "Account Number",
            value=agent.bank_account_number if agent else "",
            key=f"{key_prefix}_bank_acct",
        )
        bank_ifsc = col_ifsc.text_input(
            "IFSC",
            value=agent.bank_ifsc if agent else "",
            key=f"{key_prefix}_bank_ifsc",
            placeholder="HDFC0001234",
        )

    with st.expander("Notes", expanded=bool(agent and agent.notes)):
        notes = st.text_area(
            "Notes",
            value=agent.notes if agent else "",
            key=f"{key_prefix}_notes",
            height=68,
        )

    if services is not None:
        location_ids = render_party_location_multiselect(
            key_prefix,
            services,
            agent.location_ids if agent else None,
        )
    elif agent:
        location_ids = list(agent.location_ids or [])
    else:
        location_ids = []

    return CommissionAgentInput(
        agent_name=agent_name,
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
        commission_profile=commission_profile,
        segment_ids=list(agent.segment_ids or []) if agent else [],
        source_customer_id=agent.source_customer_id if agent else "",
        location_ids=location_ids,
    )
