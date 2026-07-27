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

        st.subheader("Customer identity")
        st.caption(
            "Controls whether name and phone are mandatory when creating customers "
            "(including quick-create on sales and boutique orders)."
        )
        require_customer_name = st.checkbox(
            "Customer name is required",
            value=bool(getattr(business, "require_customer_name", True)),
        )
        require_customer_phone = st.checkbox(
            "Customer phone is required",
            value=bool(getattr(business, "require_customer_phone", True)),
        )

        st.subheader("Invoice numbering")
        st.caption(
            "App mode auto-generates sales invoice numbers using the prefix and "
            "financial year. External mode requires entering the store invoice number."
        )
        mode_options = ["app", "external"]
        current_mode = (getattr(business, "invoice_numbering_mode", None) or "external")
        if current_mode not in mode_options:
            current_mode = "external"
        invoice_numbering_mode = st.radio(
            "Sales invoice numbering",
            mode_options,
            index=mode_options.index(current_mode),
            format_func=lambda m: (
                "App (auto-generate)" if m == "app" else "External (enter manually)"
            ),
            horizontal=True,
        )
        invoice_number_prefix = st.text_input(
            "Invoice number prefix",
            value=getattr(business, "invoice_number_prefix", None) or "INV/{FY}/",
            help="Use {FY} for the financial year label, e.g. INV/{FY}/ → INV/2026-27/0001",
        )
        month_labels = [
            (1, "January"),
            (2, "February"),
            (3, "March"),
            (4, "April"),
            (5, "May"),
            (6, "June"),
            (7, "July"),
            (8, "August"),
            (9, "September"),
            (10, "October"),
            (11, "November"),
            (12, "December"),
        ]
        fy_month = int(getattr(business, "fy_start_month", 4) or 4)
        fy_idx = next(
            (i for i, (m, _) in enumerate(month_labels) if m == fy_month), 3
        )
        fy_choice = st.selectbox(
            "Financial year start month",
            month_labels,
            index=fy_idx,
            format_func=lambda item: item[1],
            help="Default April for India (Apr–Mar). Applied to sales invoices and purchase bills.",
        )
        fy_start_month = fy_choice[0]

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
                    require_customer_name=require_customer_name,
                    require_customer_phone=require_customer_phone,
                    invoice_numbering_mode=invoice_numbering_mode,
                    invoice_number_prefix=invoice_number_prefix,
                    fy_start_month=fy_start_month,
                )
                st.success("Business settings saved.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    st.divider()
    st.subheader("Enabled modules")
    st.caption(
        "Controls which product modules appear in the left panel "
        "(combined with plan, feature flags, and role permissions)."
    )
    from vaybooks.bms.domain.entitlements.catalog import ALL_MODULES, MODULE_LABELS

    plans_svc = services.get("plans")
    if plans_svc is None:
        st.info("Plans service is not available.")
        return
    ent = plans_svc.get_org_entitlement()
    with st.form("enabled_modules_form"):
        selected_modules = st.multiselect(
            "Modules",
            options=list(ALL_MODULES),
            default=[m for m in ent.enabled_modules if m in ALL_MODULES],
            format_func=lambda m: MODULE_LABELS.get(m, m),
        )
        if st.form_submit_button("Save modules", type="primary"):
            try:
                plans_svc.set_enabled_modules(selected_modules)
                st.success("Enabled modules updated.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
