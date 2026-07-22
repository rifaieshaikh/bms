import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.inventory.inventory_product_card import inventory_product_card
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.inventory.product_form import clear_product_form_state, render_product_form
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_PRODUCTS

P_ADD = "inv_product_add_dialog"
P_EDIT = "inv_product_edit_dialog"
ADD_FORM_PREFIX = "inv_add_product"
EDIT_FORM_PREFIX = "inv_edit_product"


@st.dialog("Add Product", width="large", on_dismiss=make_dismiss_handler(P_ADD))
def _add_product_dialog(services):
    inventory = services["inventory"]
    business = services["business"].get_profile()
    payload = render_product_form(
        inventory=inventory,
        key_prefix=ADD_FORM_PREFIX,
        business=business,
        show_opening_qty=True,
        submit_label="Create Product",
    )
    if payload:
        try:
            created = inventory.create_product(
                payload["sku"],
                payload["name"],
                payload["category_ids"],
                selling_rate=payload["selling_rate"],
                mrp=payload["mrp"],
                gst_rate=payload["gst_rate"],
                opening_qty=payload["opening_qty"],
                unit_id=payload["unit_id"],
                hsn_sac=payload["hsn_sac"],
                gst_required=payload["gst_required"],
                specifications=payload["specifications"],
                custom_fields=payload["custom_fields"],
                pending_category_name=payload.get("pending_category_name"),
                pending_unit_code=payload.get("pending_unit_code"),
            )
            inventory.set_product_cost_fields(
                created.id,
                last_purchase_rate=float(payload.get("purchase_rate") or 0),
            )
            clear_product_form_state(ADD_FORM_PREFIX)
            st.session_state.pop(P_ADD, None)
            st.success(f"Created {payload['name']}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Product", width="large", on_dismiss=make_dismiss_handler(P_EDIT))
def _edit_product_dialog(services, product_id: str):
    inventory = services["inventory"]
    business = services["business"].get_profile()
    product = inventory.get_product(product_id)
    if not product:
        st.error("Product not found")
        return

    st.caption(f"Current stock: {product.current_qty:g} {product.unit}")

    payload = render_product_form(
        inventory=inventory,
        key_prefix=f"{EDIT_FORM_PREFIX}_{product_id}",
        existing=product,
        business=business,
        show_active=True,
        submit_label="Save Changes",
    )
    if payload:
        try:
            inventory.update_product(
                product_id,
                payload["sku"],
                payload["name"],
                payload["category_ids"],
                payload["unit_id"],
                payload["is_active"],
                hsn_sac=payload["hsn_sac"],
                selling_rate=payload["selling_rate"],
                mrp=payload["mrp"],
                gst_rate=payload["gst_rate"],
                gst_required=payload["gst_required"],
                specifications=payload["specifications"],
                custom_fields=payload["custom_fields"],
                pending_category_name=payload.get("pending_category_name"),
                pending_unit_code=payload.get("pending_unit_code"),
            )
            inventory.set_product_cost_fields(
                product_id,
                last_purchase_rate=float(payload.get("purchase_rate") or 0),
            )
            clear_product_form_state(f"{EDIT_FORM_PREFIX}_{product_id}")
            st.session_state.pop(P_EDIT, None)
            st.success("Product updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _load_products(services, filters, sort):
    try:
        return services["inventory"].list_products(active_only=False)
    except Exception:
        return []


def _render_cards(page_products, services):
    def _render(product, _i):
        view, edit = inventory_product_card(
            product, key_prefix="inv_prod", show_qty=True
        )
        if view:
            navigation.go_to_detail("inventory_product_detail", product.id)
        if edit:
            clear_all_dialog_flags()
            st.session_state[P_EDIT] = product.id
            register_armed_dialog(P_EDIT)

    render_card_grid(page_products, _render, suffix="inv_products", card_min_width=240)


def render(services: dict):
    bar = render_list(
        INVENTORY_PRODUCTS,
        services=services,
        load_fn=_load_products,
        card_renderer=_render_cards,
        primary_label="Add Product",
        primary_key="inv_products_add_btn",
        count_label="products",
        empty_text="No inventory products yet.",
        page_key_nav="inventory_products_list",
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        st.session_state[P_ADD] = True
        register_armed_dialog(P_ADD)
    if st.session_state.get(P_ADD):
        _add_product_dialog(services)
    if st.session_state.get(P_EDIT):
        _edit_product_dialog(services, st.session_state[P_EDIT])
