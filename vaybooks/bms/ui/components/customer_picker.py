"""Customer search/select with inline add and edit (works inside dialogs)."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from vaybooks.bms.domain.shared.exceptions import ValidationError


def customer_picker(
    services: dict,
    key_prefix: str,
    default_customer_id: Optional[str] = None,
) -> Optional[str]:
    """Render customer search, selection, add, and edit. Returns selected customer_id."""
    customer_service = services["customers"]
    selected_key = f"{key_prefix}_customer_id"
    add_open_key = f"{key_prefix}_add_open"
    edit_open_key = f"{key_prefix}_edit_open"
    applied_key = f"{key_prefix}_default_applied"

    if default_customer_id and st.session_state.get(applied_key) != default_customer_id:
        st.session_state[selected_key] = default_customer_id
        st.session_state[applied_key] = default_customer_id
    elif default_customer_id is None:
        st.session_state.pop(applied_key, None)

    search = st.text_input(
        "Search customer by name or phone",
        key=f"{key_prefix}_search",
    )
    customers = customer_service.search_customers(search)
    options = {f"{c.customer_name} - {c.phone_number}": c.id for c in customers}
    option_labels = list(options.keys())

    selected_id = st.session_state.get(selected_key)
    if option_labels:
        default_idx = 0
        if selected_id and selected_id in options.values():
            default_idx = list(options.values()).index(selected_id)
        choice = st.selectbox(
            "Customer",
            option_labels,
            index=default_idx,
            key=f"{key_prefix}_select",
        )
        selected_id = options[choice]
        st.session_state[selected_key] = selected_id
    elif not st.session_state.get(add_open_key):
        st.info("No customers found. Add one below.")

    btn_cols = st.columns(2)
    if btn_cols[0].button("Add customer", key=f"{key_prefix}_btn_add"):
        st.session_state[add_open_key] = True
        st.session_state[edit_open_key] = False
        st.rerun()
    if btn_cols[1].button(
        "Edit customer",
        key=f"{key_prefix}_btn_edit",
        disabled=not selected_id,
    ):
        st.session_state[edit_open_key] = True
        st.session_state[add_open_key] = False
        st.rerun()

    if st.session_state.get(add_open_key):
        _render_add_customer(customer_service, key_prefix, selected_key, add_open_key)

    if st.session_state.get(edit_open_key) and selected_id:
        _render_edit_customer(
            customer_service, key_prefix, selected_id, edit_open_key
        )

    return st.session_state.get(selected_key)


def _render_add_customer(
    customer_service,
    key_prefix: str,
    selected_key: str,
    add_open_key: str,
) -> None:
    with st.container(border=True):
        st.markdown("**New customer**")
        name = st.text_input("Customer name", key=f"{key_prefix}_add_name")
        phone = st.text_input("Phone number", key=f"{key_prefix}_add_phone")
        alt_phone = st.text_input("Alternate phone", key=f"{key_prefix}_add_alt")
        address = st.text_area("Address", key=f"{key_prefix}_add_addr")
        notes = st.text_area("Notes", key=f"{key_prefix}_add_notes")

        save_cols = st.columns(2)
        if save_cols[0].button("Create customer", type="primary", key=f"{key_prefix}_add_save"):
            if not name or not phone:
                st.error("Name and phone are required")
                return
            try:
                customer = customer_service.create_customer(
                    name,
                    phone,
                    alt_phone or None,
                    address,
                    notes,
                )
                st.session_state[selected_key] = customer.id
                st.session_state[add_open_key] = False
                st.success(f"Created {customer.customer_name}")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(str(exc))
        if save_cols[1].button("Cancel", key=f"{key_prefix}_add_cancel"):
            st.session_state[add_open_key] = False
            st.rerun()


def _render_edit_customer(
    customer_service,
    key_prefix: str,
    customer_id: str,
    edit_open_key: str,
) -> None:
    customer = customer_service.get_customer_detail(customer_id)
    if not customer:
        st.error("Customer not found")
        st.session_state[edit_open_key] = False
        return

    with st.container(border=True):
        st.markdown("**Edit customer**")
        name = st.text_input(
            "Customer name",
            value=customer.customer_name,
            key=f"{key_prefix}_edit_name",
        )
        phone = st.text_input(
            "Phone number",
            value=customer.phone_number,
            key=f"{key_prefix}_edit_phone",
        )
        alt_phone = st.text_input(
            "Alternate phone",
            value=customer.alternate_phone_number or "",
            key=f"{key_prefix}_edit_alt",
        )
        address = st.text_area(
            "Address",
            value=customer.address or "",
            key=f"{key_prefix}_edit_addr",
        )
        notes = st.text_area(
            "Notes",
            value=customer.notes or "",
            key=f"{key_prefix}_edit_notes",
        )

        save_cols = st.columns(2)
        if save_cols[0].button("Save changes", type="primary", key=f"{key_prefix}_edit_save"):
            if not name or not phone:
                st.error("Name and phone are required")
                return
            try:
                customer_service.update_customer(
                    customer_id,
                    name,
                    phone,
                    alt_phone or None,
                    address,
                    notes,
                )
                st.session_state[edit_open_key] = False
                st.success("Customer updated")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(str(exc))
        if save_cols[1].button("Cancel", key=f"{key_prefix}_edit_cancel"):
            st.session_state[edit_open_key] = False
            st.rerun()
