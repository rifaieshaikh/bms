"""Delivery partner detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.parties.delivery_partners.entities import DeliveryPartnerInput
from vaybooks.bms.domain.shared.enums import DeliveryNoteStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.location_fields import (
    render_party_location_multiselect,
)
from vaybooks.bms.ui.components.sales.delivery_charge_payment import (
    render_pay_delivery_charges,
)


def render(services: dict) -> None:
    partner_id = navigation.current_detail_id("delivery_partner_detail")
    if not partner_id:
        st.warning("Delivery partner not specified")
        return
    svc = services["delivery_partners"]
    partner = svc.get_partner(partner_id)
    if not partner:
        st.warning("Delivery partner not found")
        return
    if st.button("← Back", key="dp_detail_back"):
        navigation.go_back_to_list("delivery_partners", "delivery_partners_list")
        return

    st.title(partner.display_name)
    st.caption(partner.phone_number)
    left, right = st.columns(2)
    with left:
        st.markdown("**Contact**")
        st.write(partner.email or "—")
        st.write(partner.alternate_phone_number or "")
        st.write(partner.formatted_address or "—")
    with right:
        st.markdown("**Compliance**")
        st.write(f"GSTIN: {partner.gstin or '—'}")
        st.write(f"PAN: {partner.pan or '—'}")
        st.write(f"Payment terms: {partner.payment_terms or '—'}")
        st.write("Active" if partner.is_active else "Inactive")

    account_id = svc.get_partner_account_id(partner.id)
    if account_id and services.get("accounting"):
        account = services["accounting"].get_account(account_id)
        if account:
            st.metric("Outstanding payable", f"₹{account.current_balance:,.2f}")

    st.subheader("Pay delivery charge")
    render_pay_delivery_charges(
        services, partner_id=partner.id, key_prefix=f"dp_pay_{partner.id[:8]}"
    )

    history = []
    if services.get("sales"):
        history = services["sales"].list_delivery_notes_by_partner(partner.id)
    if history:
        st.subheader("Delivery history")
        for dn in history:
            if dn.status == DeliveryNoteStatus.CANCELLED:
                continue
            pay = (
                dn.charges.payment_status.value
                if hasattr(dn.charges.payment_status, "value")
                else str(dn.charges.payment_status)
            )
            st.write(
                f"{dn.dn_number} — {dn.delivery_date} — {dn.customer_name} — "
                f"{dn.status.value} — charge ₹{dn.charges.amount:,.2f} ({pay})"
            )
            if st.button("Open DN", key=f"dp_open_dn_{dn.id}"):
                navigation.go_to_detail("delivery_note_detail", dn.id)
                st.rerun()

    with st.expander("Edit partner"):
        name = st.text_input("Partner name", value=partner.partner_name, key="dp_e_name")
        legal = st.text_input(
            "Legal / display name",
            value=partner.legal_display_name,
            key="dp_e_legal",
        )
        phone = st.text_input("Phone", value=partner.phone_number, key="dp_e_phone")
        alt = st.text_input(
            "Alternate phone",
            value=partner.alternate_phone_number or "",
            key="dp_e_alt",
        )
        email = st.text_input("Email", value=partner.email, key="dp_e_email")
        address = st.text_input(
            "Address", value=partner.address_line1, key="dp_e_address"
        )
        gstin = st.text_input("GSTIN", value=partner.gstin, key="dp_e_gstin")
        pan = st.text_input("PAN", value=partner.pan, key="dp_e_pan")
        terms = st.text_input(
            "Payment terms", value=partner.payment_terms, key="dp_e_terms"
        )
        notes = st.text_area("Notes", value=partner.notes, key="dp_e_notes")
        active = st.checkbox("Active", value=partner.is_active, key="dp_e_active")
        location_ids = render_party_location_multiselect(
            "dp_e", services, partner.location_ids
        )
        if st.button("Save", type="primary", key="dp_e_save"):
            try:
                svc.update_partner(
                    partner.id,
                    DeliveryPartnerInput(
                        partner_name=name,
                        legal_display_name=legal or name,
                        phone_number=phone,
                        alternate_phone_number=alt or None,
                        email=email,
                        address_line1=address,
                        gstin=gstin,
                        pan=pan,
                        payment_terms=terms,
                        is_active=active,
                        notes=notes,
                        default_expense_ledger_id=partner.default_expense_ledger_id,
                        location_ids=location_ids,
                    ),
                )
                st.success("Saved")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
