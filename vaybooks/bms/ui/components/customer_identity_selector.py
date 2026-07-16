"""Shared customer name/mobile selector for sales document forms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st


@dataclass(frozen=True)
class CustomerIdentitySelection:
    customer_id: str
    customer_name: str
    phone_number: str
    customer: Any | None = None


def _name_label(customer) -> str:
    return f"{customer.customer_name} — {customer.phone_number}"


def _mobile_label(customer) -> str:
    return f"{customer.phone_number} — {customer.customer_name}"


def render_customer_identity_selector(
    customer_service,
    *,
    key_prefix: str,
    initial_customer=None,
) -> CustomerIdentitySelection:
    """Render linked, searchable name and mobile dropdowns.

    Both dropdowns accept new values. Selecting an existing customer in either
    one synchronizes the other; a new name/mobile pair is resolved when the
    parent form is submitted.
    """
    customers = customer_service.list_all_customers()
    customer_by_id = {customer.id: customer for customer in customers}
    name_to_customer = {_name_label(customer): customer for customer in customers}
    mobile_to_customer = {
        _mobile_label(customer): customer for customer in customers
    }
    name_label_by_id = {
        customer.id: _name_label(customer) for customer in customers
    }
    mobile_label_by_id = {
        customer.id: _mobile_label(customer) for customer in customers
    }

    name_key = f"{key_prefix}_customer_name"
    mobile_key = f"{key_prefix}_customer_mobile"
    matched_key = f"{key_prefix}_customer_id"

    if name_key not in st.session_state:
        st.session_state[name_key] = (
            name_label_by_id.get(initial_customer.id)
            if initial_customer is not None
            else None
        )
    if mobile_key not in st.session_state:
        st.session_state[mobile_key] = (
            mobile_label_by_id.get(initial_customer.id)
            if initial_customer is not None
            else None
        )
    if matched_key not in st.session_state and initial_customer is not None:
        st.session_state[matched_key] = initial_customer.id

    def _on_name_change() -> None:
        value = st.session_state.get(name_key)
        if not value:
            st.session_state[mobile_key] = None
            st.session_state.pop(matched_key, None)
            return
        customer = name_to_customer.get(value)
        if customer is not None:
            st.session_state[mobile_key] = mobile_label_by_id[customer.id]
            st.session_state[matched_key] = customer.id
        else:
            st.session_state.pop(matched_key, None)

    def _on_mobile_change() -> None:
        value = st.session_state.get(mobile_key)
        if not value:
            st.session_state[name_key] = None
            st.session_state.pop(matched_key, None)
            return
        customer = mobile_to_customer.get(value)
        if customer is None:
            try:
                customer = customer_service.lookup_customer_by_phone(value)
            except Exception:
                customer = None
        if customer is not None:
            st.session_state[name_key] = name_label_by_id[customer.id]
            st.session_state[mobile_key] = mobile_label_by_id[customer.id]
            st.session_state[matched_key] = customer.id
        else:
            st.session_state.pop(matched_key, None)

    name_options = sorted(name_to_customer, key=str.casefold)
    mobile_options = sorted(mobile_to_customer, key=str.casefold)
    current_name = st.session_state.get(name_key)
    current_mobile = st.session_state.get(mobile_key)
    if current_name and current_name not in name_options:
        name_options.append(current_name)
    if current_mobile and current_mobile not in mobile_options:
        mobile_options.append(current_mobile)

    name_col, mobile_col = st.columns(2)
    with name_col:
        selected_name = st.selectbox(
            "Customer Name",
            options=name_options,
            index=None,
            key=name_key,
            on_change=_on_name_change,
            accept_new_options=True,
            placeholder="Search or enter customer name",
        )
    with mobile_col:
        selected_mobile = st.selectbox(
            "Mobile Number",
            options=mobile_options,
            index=None,
            key=mobile_key,
            on_change=_on_mobile_change,
            accept_new_options=True,
            placeholder="Search or enter mobile number",
        )

    matched_id = st.session_state.get(matched_key) or ""
    matched_customer = customer_by_id.get(matched_id)
    if matched_customer is not None:
        st.caption(f"Existing customer: **{matched_customer.customer_name}**")
        return CustomerIdentitySelection(
            customer_id=matched_customer.id,
            customer_name=matched_customer.customer_name,
            phone_number=matched_customer.phone_number,
            customer=matched_customer,
        )

    selected_name_customer = name_to_customer.get(selected_name)
    selected_mobile_customer = mobile_to_customer.get(selected_mobile)
    return CustomerIdentitySelection(
        customer_id="",
        customer_name=(
            selected_name_customer.customer_name
            if selected_name_customer is not None
            else (selected_name or "").strip()
        ),
        phone_number=(
            selected_mobile_customer.phone_number
            if selected_mobile_customer is not None
            else (selected_mobile or "").strip()
        ),
    )


def resolve_customer_identity(
    customer_service,
    selection: CustomerIdentitySelection,
):
    """Return the selected customer or create one using sales-order checks."""
    if selection.customer_id:
        customer = customer_service.get_customer_detail(selection.customer_id)
        if customer is not None:
            return customer
    if not selection.customer_name:
        raise ValueError("Customer name is required")
    if not selection.phone_number:
        raise ValueError("Mobile number is required")
    return customer_service.find_or_create_customer(
        selection.customer_name,
        selection.phone_number,
    )
