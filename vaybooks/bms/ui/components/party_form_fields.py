"""Shared address and tax fields for customer/vendor forms."""

from __future__ import annotations

from typing import Any, Optional, Type

import streamlit as st

from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.india import INDIAN_STATES


def _state_options() -> tuple[list[str], dict[str, str]]:
    labels = [f"{s['code']} — {s['name']}" for s in INDIAN_STATES]
    code_by_label = {f"{s['code']} — {s['name']}": s["code"] for s in INDIAN_STATES}
    return labels, code_by_label


def _state_label_for_code(state_code: str) -> str:
    for state in INDIAN_STATES:
        if state["code"] == state_code:
            return f"{state['code']} — {state['name']}"
    return ""


def render_party_address_tax_fields(
    key_prefix: str,
    *,
    party: Optional[Any] = None,
    registration_type_enum: Type[PartyRegistrationType] = PartyRegistrationType,
) -> dict:
    st.markdown("**Address**")
    address_line1 = st.text_input(
        "Address Line 1",
        value=getattr(party, "address_line1", "") if party else "",
        key=f"{key_prefix}_addr1",
    )
    address_line2 = st.text_input(
        "Address Line 2",
        value=getattr(party, "address_line2", "") if party else "",
        key=f"{key_prefix}_addr2",
    )
    col_city, col_pin = st.columns(2)
    city = col_city.text_input(
        "City",
        value=getattr(party, "city", "") if party else "",
        key=f"{key_prefix}_city",
    )
    pincode = col_pin.text_input(
        "PIN Code",
        value=getattr(party, "pincode", "") if party else "",
        key=f"{key_prefix}_pin",
        placeholder="6 digits",
    )
    state_labels, code_by_label = _state_options()
    default_state_idx = 0
    state_code = getattr(party, "state_code", "") if party else ""
    if state_code:
        label = _state_label_for_code(state_code)
        if label in state_labels:
            default_state_idx = state_labels.index(label)
    state_label = st.selectbox(
        "State",
        state_labels,
        index=default_state_idx,
        key=f"{key_prefix}_state",
    )
    country = st.text_input(
        "Country",
        value=getattr(party, "country", "India") if party else "India",
        key=f"{key_prefix}_country",
    )

    st.markdown("**Tax**")
    reg_types = list(registration_type_enum)
    reg_labels = [t.value for t in reg_types]
    default_reg_idx = 0
    if party and getattr(party, "registration_type", None):
        try:
            default_reg_idx = reg_types.index(party.registration_type)
        except ValueError:
            default_reg_idx = 0
    else:
        try:
            default_reg_idx = reg_types.index(PartyRegistrationType.UNREGISTERED)
        except ValueError:
            default_reg_idx = 0
    registration_label = st.selectbox(
        "Registration Type",
        reg_labels,
        index=default_reg_idx,
        key=f"{key_prefix}_reg",
    )
    registration_type = registration_type_enum(registration_label)
    col_gstin, col_pan = st.columns(2)
    gstin = col_gstin.text_input(
        "GSTIN",
        value=getattr(party, "gstin", "") if party else "",
        key=f"{key_prefix}_gstin",
        placeholder="Required for Registered parties",
    )
    pan = col_pan.text_input(
        "PAN",
        value=getattr(party, "pan", "") if party else "",
        key=f"{key_prefix}_pan",
        placeholder="ABCDE1234F",
    )
    msme_number = st.text_input(
        "MSME (Udyam) Number",
        value=getattr(party, "msme_number", "") if party else "",
        key=f"{key_prefix}_msme",
    )

    return {
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": city,
        "state_code": code_by_label.get(state_label, ""),
        "pincode": pincode,
        "country": country or "India",
        "gstin": gstin,
        "pan": pan,
        "registration_type": registration_type,
        "msme_number": msme_number,
    }
