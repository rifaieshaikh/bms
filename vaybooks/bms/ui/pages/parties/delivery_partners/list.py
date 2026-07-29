"""Delivery Partners list (Masters / Parties)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.identity.location_access import location_ids_mongo_filter
from vaybooks.bms.domain.parties.delivery_partners.entities import DeliveryPartnerInput
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.auth.session import working_location_list_context
from vaybooks.bms.ui.components.common.location_fields import (
    render_party_location_multiselect,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import render_card_grid

DP_ADD = "delivery_partner_add_dialog"
SUBMIT_ADD = "submit_delivery_partner_add"


def _open_add() -> None:
    open_dialog(DP_ADD, submit_key=SUBMIT_ADD, clear_others=True)
    mark_wired("dialog.save")


@st.dialog(
    "Add Delivery Partner",
    width="large",
    on_dismiss=make_dismiss_handler(DP_ADD),
)
def _add_dialog(services: dict) -> None:
    if st.session_state.get(DP_ADD) != "new" and not st.session_state.get(DP_ADD):
        return
    register_armed_dialog(DP_ADD)
    mark_wired("dialog.save")
    name = st.text_input("Partner name *", key=f"{DP_ADD}_name")
    legal = st.text_input("Legal / display name", key=f"{DP_ADD}_legal")
    phone = st.text_input("Phone number *", key=f"{DP_ADD}_phone")
    alt = st.text_input("Alternate phone", key=f"{DP_ADD}_alt")
    email = st.text_input("Email", key=f"{DP_ADD}_email")
    address = st.text_input("Address", key=f"{DP_ADD}_address")
    gstin = st.text_input("GSTIN", key=f"{DP_ADD}_gstin")
    pan = st.text_input("PAN", key=f"{DP_ADD}_pan")
    terms = st.text_input("Payment terms", key=f"{DP_ADD}_terms")
    notes = st.text_area("Notes", key=f"{DP_ADD}_notes")
    active = st.checkbox("Active", value=True, key=f"{DP_ADD}_active")
    location_ids = render_party_location_multiselect(DP_ADD, services)
    cols = st.columns(2)
    do_create = cols[0].button("Create", type="primary", width="stretch") or consume_submit(
        SUBMIT_ADD
    )
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(DP_ADD, None)
        st.rerun()
    if do_create:
        try:
            partner = services["delivery_partners"].create_partner(
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
                    location_ids=location_ids,
                )
            )
            st.session_state.pop(DP_ADD, None)
            st.success(f"Created delivery partner: {partner.partner_name}")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))


def render(services: dict) -> None:
    st.title("Delivery Partners")
    st.caption("Logistics vendors and transporters used on delivery notes.")
    if st.button("+ Add Delivery Partner", type="primary", key="dp_list_add"):
        _open_add()
        st.rerun()
    if st.session_state.get(DP_ADD):
        _add_dialog(services)

    working, accessible = working_location_list_context(services)
    filt = location_ids_mongo_filter(working, accessible)
    partners = services["delivery_partners"].list_all_partners(location_filter=filt)
    if not partners:
        st.info("No delivery partners yet.")
        return

    def _card(partner, _suffix=""):
        with st.container(border=True):
            st.markdown(f"**{partner.display_name}**")
            st.caption(partner.phone_number)
            if partner.gstin:
                st.caption(f"GSTIN {partner.gstin}")
            status = "Active" if partner.is_active else "Inactive"
            st.caption(status)
            if st.button("Open", key=f"dp_open_{partner.id}"):
                navigation.go_to_detail("delivery_partner_detail", partner.id)
                st.rerun()

    render_card_grid(partners, _card, suffix="delivery_partners")
