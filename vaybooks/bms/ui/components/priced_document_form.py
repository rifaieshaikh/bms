from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import (
    EstimateStatus,
    PartyRegistrationType,
    QuotationStatus,
)
from vaybooks.bms.ui.components.customer_identity_selector import (
    render_customer_identity_selector,
    resolve_customer_identity,
)
from vaybooks.bms.ui.components.document_custom_fields import (
    render_document_custom_fields,
)
from vaybooks.bms.ui.components.sales_lines_editor import render_sales_lines_editor


def render_priced_document_form(
    services: dict,
    *,
    document_type: str,
    existing=None,
    key_prefix: str,
) -> bool:
    sales = services["sales"]
    business = services["business"].get_profile()
    customer_service = services["customers"]
    inventory = services["inventory"]
    products = inventory.list_products(active_only=True)
    if not products:
        st.warning("Add at least one active inventory product first.")
        return False
    template = business.document_templates.get(document_type)
    is_estimate = document_type == "estimate"
    date_field = "estimate_date" if is_estimate else "quotation_date"
    initial_lines = [
        {
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty": line.qty,
            "rate": line.rate,
        }
        for line in (getattr(existing, "lines", []) or [])
    ]
    initial_customer = (
        customer_service.get_customer_detail(existing.customer_id)
        if existing is not None
        else None
    )
    customer_selection = render_customer_identity_selector(
        customer_service,
        key_prefix=key_prefix,
        initial_customer=initial_customer,
    )
    registered = business_is_registered(business)
    selected_customer = customer_selection.customer
    customer_registered = bool(
        selected_customer
        and (
            selected_customer.registration_type
            == PartyRegistrationType.REGISTERED
            or (selected_customer.gstin or "").strip()
        )
    )
    business_state = business.state_code or ""
    customer_state = (
        (selected_customer.state_code or "") if selected_customer else ""
    )
    if not customer_registered and not customer_state:
        customer_state = business_state

    cols = st.columns(2)
    document_date = cols[0].date_input(
        "Document date",
        value=getattr(existing, date_field, date.today()),
        key=f"{key_prefix}_date",
    )
    valid_until = cols[1].date_input(
        "Valid until",
        value=getattr(existing, "valid_until", None)
        or (document_date + timedelta(days=30)),
        key=f"{key_prefix}_valid",
    )

    st.markdown("**Line items**")
    lines, gst_errors = render_sales_lines_editor(
        key_prefix=key_prefix,
        products=products,
        initial_lines=initial_lines,
        customer_id=selected_customer.id if selected_customer else None,
        use_customer_pricing=False,
        show_discount=False,
        sales_service=sales,
        inventory_service=inventory,
        business_registered=registered,
        business=business,
        business_state_code=business_state,
        customer_state_code=customer_state,
        qty_field="qty",
    )

    notes = st.text_area(
        "Notes", value=getattr(existing, "notes", ""), key=f"{key_prefix}_notes"
    )
    status_values = list(EstimateStatus if is_estimate else QuotationStatus)
    current_status = getattr(existing, "status", status_values[0])
    status = st.selectbox(
        "Status",
        status_values,
        index=status_values.index(current_status),
        format_func=lambda item: item.value,
        key=f"{key_prefix}_status",
    )
    existing_content = getattr(existing, "document_content", None)
    initial_custom = {
        item.key: item.value
        for item in (getattr(existing_content, "custom_fields", []) or [])
    }
    custom_values = render_document_custom_fields(
        template.custom_fields if template else [],
        key_prefix=f"{key_prefix}_custom",
        initial_values=initial_custom,
    )
    active_accounts = [item for item in business.bank_accounts if item.is_active]
    account_ids = [""] + [item.id for item in active_accounts]
    account_by_id = {item.id: item for item in active_accounts}
    current_account_id = getattr(
        getattr(existing_content, "bank_account", None), "id", ""
    )
    default_account = current_account_id or (
        template.default_bank_account_id if template else ""
    )
    account_index = (
        account_ids.index(default_account) if default_account in account_ids else 0
    )
    bank_account_id = st.selectbox(
        "Bank account on document",
        account_ids,
        index=account_index,
        format_func=lambda item_id: (
            "None" if not item_id else account_by_id[item_id].account_name
        ),
        key=f"{key_prefix}_bank",
    )
    terms = st.text_area(
        "Terms & Conditions",
        value=(
            getattr(existing_content, "terms_and_conditions", "")
            or (template.terms_and_conditions if template else "")
        ),
        key=f"{key_prefix}_terms",
    )
    if not st.button(
        "Update" if existing else "Create",
        type="primary",
        key=f"{key_prefix}_submit",
    ):
        return False
    if gst_errors:
        st.error(gst_errors[0])
        return False
    if not lines:
        st.error("Add at least one product line")
        return False
    customer = resolve_customer_identity(
        customer_service,
        customer_selection,
    )
    kwargs = {
        "customer_id": customer.id,
        date_field: document_date,
        "valid_until": valid_until,
        "lines": lines,
        "notes": notes,
        "status": status,
        "custom_values": custom_values,
        "bank_account_id": bank_account_id,
        "terms_and_conditions": terms,
    }
    if existing:
        method = sales.update_estimate if is_estimate else sales.update_quotation
        method(existing.id, **kwargs)
    else:
        method = sales.create_estimate if is_estimate else sales.create_quotation
        method(**kwargs)
    st.success("Document saved")
    return True
