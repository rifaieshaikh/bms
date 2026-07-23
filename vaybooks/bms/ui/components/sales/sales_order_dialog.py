"""Create sales order dialog (product lines via entry table)."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import PartyRegistrationType, SalesOrderStatus
from vaybooks.bms.ui.components.common.customer_identity_selector import (
    render_customer_identity_selector,
    resolve_customer_identity,
)
from vaybooks.bms.ui.components.common.dialog_state import reset_dialog_state
from vaybooks.bms.ui.components.sales.sales_lines_entry_table import (
    entry_table_focus_chain,
    entry_table_focus_columns,
    entry_table_grid_roles,
    render_sales_lines_entry_table,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.focus.registry import get_strategy
from vaybooks.bms.ui.keyboard.wired import mark_wired

SO_DIALOG = "sales_order_dialog"
SO_PRESELECT = "sales_order_dialog_preselect_customer_id"
SO_SUBMIT_KEY = "so_dialog_submit"
SO_FOCUS_KEY = f"{SO_DIALOG}_focus"


def arm_so_dialog(customer_id: str | None = None) -> None:
    reset_dialog_state(SO_DIALOG)
    open_dialog(SO_DIALOG, submit_key=SO_SUBMIT_KEY, value="new", clear_others=True)
    st.session_state[SO_FOCUS_KEY] = f"{SO_DIALOG}_customer_name"
    if customer_id:
        st.session_state[SO_PRESELECT] = customer_id
    else:
        st.session_state.pop(SO_PRESELECT, None)
    mark_wired("dialog.save")


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SO_DIALOG):
            st.session_state.pop(key, None)
    st.session_state.pop(SO_PRESELECT, None)
    st.session_state.pop(SO_SUBMIT_KEY, None)


def _customer_is_registered(customer) -> bool:
    if customer is None:
        return False
    if customer.registration_type == PartyRegistrationType.REGISTERED:
        return True
    return bool((customer.gstin or "").strip())


@st.dialog("Create Sales Order", width="large", on_dismiss=make_dismiss_handler(SO_DIALOG))
def sales_order_dialog(services: dict) -> None:
    if st.session_state.get(SO_DIALOG) != "new":
        return

    register_armed_dialog(SO_DIALOG)
    mark_wired("dialog.save")

    sales = services["sales"]
    customers = services["customers"]
    inventory = services.get("inventory")

    preselect_id = st.session_state.get(SO_PRESELECT)
    initial_customer = (
        customers.get_customer_detail(preselect_id) if preselect_id else None
    )
    customer_selection = render_customer_identity_selector(
        customers,
        key_prefix=SO_DIALOG,
        initial_customer=initial_customer,
    )
    selected_customer = customer_selection.customer
    business_service = services.get("business")
    business = business_service.get_profile() if business_service else None
    show_gst = business_is_registered(business)
    business_state = business.state_code if business else ""
    supply_type = "B2B" if _customer_is_registered(selected_customer) else "B2C"
    customer_state = (selected_customer.state_code if selected_customer else "") or ""
    if supply_type == "B2C" and not customer_state:
        customer_state = business_state
    if show_gst:
        if customer_state and business_state:
            place = (
                "Intra-state"
                if customer_state == business_state
                else "Inter-state (IGST)"
            )
            st.caption(f"Supply type: **{supply_type}** · {place}")
        else:
            st.caption(f"Supply type: **{supply_type}**")

    products = inventory.list_products(active_only=True) if inventory else []
    if not products:
        st.error("Add inventory products first.")
        return

    customer_name_key = f"{SO_DIALOG}_customer_name"
    expected_key = f"{SO_DIALOG}_expected"
    save_key = f"{SO_DIALOG}_save"
    cancel_key = f"{SO_DIALOG}_cancel"

    c1, c2 = st.columns(2)
    order_date = c1.date_input("Order date", value=date.today(), key=f"{SO_DIALOG}_date")
    expected_date = c2.date_input(
        "Expected date", value=date.today(), key=expected_key
    )
    notes = st.text_input("Notes", key=f"{SO_DIALOG}_notes")

    lines, gst_errors = render_sales_lines_entry_table(
        key_prefix=SO_DIALOG,
        products=products,
        initial_lines=None,
        customer_id=selected_customer.id if selected_customer else None,
        use_customer_pricing=True,
        show_discount=False,
        sales_service=sales,
        inventory_service=inventory,
        business_registered=show_gst,
        business=business,
        business_state_code=business_state,
        customer_state_code=customer_state,
        qty_field="qty_ordered",
        focus_restore_key=SO_FOCUS_KEY,
    )

    row_chain = entry_table_focus_chain(SO_DIALOG)
    row_columns = entry_table_focus_columns(SO_DIALOG)
    grid_roles = entry_table_grid_roles(SO_DIALOG)

    save_cols = st.columns(2)
    do_save = save_cols[0].button(
        "Save SO",
        type="primary",
        use_container_width=True,
        key=save_key,
    ) or consume_submit(SO_SUBMIT_KEY)
    if save_cols[1].button("Cancel", use_container_width=True, key=cancel_key):
        _clear()
        st.rerun()

    restore = st.session_state.pop(SO_FOCUS_KEY, None)
    get_strategy(SO_DIALOG).inject(
        chain=[customer_name_key, expected_key, *row_chain, save_key, cancel_key],
        restore_key=restore,
        columns=row_columns,
        above_first=expected_key,
        below_last=save_key,
        grid_roles=grid_roles,
        component_key=f"so_entry_{len(row_chain)}",
    )

    if do_save:
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            so_lines = [
                {
                    "product_id": row.get("product_id") or "",
                    "product_name": row.get("product_name") or "",
                    "qty_ordered": float(row.get("qty_ordered") or 0),
                    "rate": float(row.get("rate") or 0),
                }
                for row in lines
                if row.get("product_id") and float(row.get("qty_ordered") or 0) > 0
            ]
            if not so_lines:
                raise ValueError("Add at least one product line")
            customer = resolve_customer_identity(
                customers,
                customer_selection,
            )
            sales.create_sales_order(
                customer_id=customer.id,
                order_date=order_date,
                expected_date=expected_date,
                lines=so_lines,
                notes=notes,
                status=SalesOrderStatus.CONFIRMED,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_so_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(SO_DIALOG) == "new":
        sales_order_dialog(services)
