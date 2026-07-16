"""Business settings — Indian-standard business profile."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VendorRegistrationType
from vaybooks.bms.domain.shared.india import INDIAN_STATES


def render(services: dict):
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("business_settings")
    mark_wired("settings.business.save")
    st.title("Business Settings")
    business = services["business"].get_profile()

    state_labels = [f"{s['code']} — {s['name']}" for s in INDIAN_STATES]
    code_by_label = {f"{s['code']} — {s['name']}": s["code"] for s in INDIAN_STATES}
    default_state = 0
    if business.state_code:
        label = next(
            (f"{s['code']} — {s['name']}" for s in INDIAN_STATES if s["code"] == business.state_code),
            state_labels[0],
        )
        if label in state_labels:
            default_state = state_labels.index(label)

    with st.form("business_settings_form"):
        st.subheader("Identity")
        legal_name = st.text_input("Legal name", value=business.legal_name)
        trade_name = st.text_input("Trade name", value=business.trade_name)

        st.subheader("Address")
        address_line1 = st.text_input("Address line 1", value=business.address_line1)
        address_line2 = st.text_input("Address line 2", value=business.address_line2)
        col_city, col_pin, col_country = st.columns(3)
        city = col_city.text_input("City", value=business.city)
        pincode = col_pin.text_input("PIN code", value=business.pincode, placeholder="6 digits")
        country = col_country.text_input("Country", value=business.country or "India")
        state_label = st.selectbox("State", state_labels, index=default_state)

        st.subheader("Contact")
        col_phone, col_email = st.columns(2)
        phone = col_phone.text_input("Phone", value=business.phone, placeholder="10-digit mobile")
        email = col_email.text_input("Email", value=business.email)

        st.subheader("Tax")
        reg_types = [t.value for t in VendorRegistrationType]
        reg_idx = (
            reg_types.index(business.registration_type.value)
            if business.registration_type.value in reg_types
            else 0
        )
        registration = st.selectbox("Registration type", reg_types, index=reg_idx)
        col_gstin, col_pan = st.columns(2)
        gstin = col_gstin.text_input("GSTIN", value=business.gstin)
        pan = col_pan.text_input("PAN", value=business.pan, placeholder="ABCDE1234F")
        composition_tax_rate = st.number_input(
            "Composition GST rate (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(getattr(business, "composition_tax_rate", 1.0) or 0),
            step=0.1,
            disabled=registration != VendorRegistrationType.COMPOSITION.value,
            help="Applied to sales when Registration type is Composition.",
        )

        if st.form_submit_button("Save business settings", type="primary"):
            try:
                services["business"].update_profile(
                    legal_name=legal_name,
                    trade_name=trade_name,
                    address_line1=address_line1,
                    address_line2=address_line2,
                    city=city,
                    state_code=code_by_label.get(state_label, ""),
                    pincode=pincode,
                    country=country,
                    phone=phone,
                    email=email,
                    gstin=gstin,
                    pan=pan,
                    registration_type=VendorRegistrationType(registration),
                    composition_tax_rate=composition_tax_rate,
                )
                st.success("Business settings saved.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
