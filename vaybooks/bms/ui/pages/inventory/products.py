import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.inventory_product_card import inventory_product_card
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.product_form import clear_product_form_state, render_product_form
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_PRODUCTS

PENDING_EDIT = "pending_edit_inventory_product"
ADD_FORM_PREFIX = "inv_add_product"
EDIT_FORM_PREFIX = "inv_edit_product"


@st.dialog("Add Product", width="large")
def _add_product_dialog(inventory):
    categories = inventory.list_categories(active_only=True)
    if not categories:
        st.error("Create at least one category first.")
        return

    payload = render_product_form(
        inventory=inventory,
        key_prefix=ADD_FORM_PREFIX,
        categories=categories,
        show_opening_qty=True,
        submit_label="Create Product",
    )
    if payload:
        try:
            inventory.create_product(
                payload["sku"],
                payload["name"],
                payload["category_ids"],
                selling_rate=payload["selling_rate"],
                opening_qty=payload["opening_qty"],
                unit_id=payload["unit_id"],
                hsn_sac=payload["hsn_sac"],
                gst_rates=payload["gst_rates"],
                mrp_entries=payload["mrp_entries"],
                specifications=payload["specifications"],
                custom_fields=payload["custom_fields"],
            )
            clear_product_form_state(ADD_FORM_PREFIX)
            st.success(f"Created {payload['name']}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Product", width="large")
def _edit_product_dialog(inventory, product_id: str):
    product = inventory.get_product(product_id)
    if not product:
        st.error("Product not found")
        return

    categories = inventory.list_categories(active_only=False)
    if not categories:
        st.error("No categories available.")
        return

    st.caption(f"Current stock: {product.current_qty:g} {product.unit}")

    payload = render_product_form(
        inventory=inventory,
        key_prefix=f"{EDIT_FORM_PREFIX}_{product_id}",
        categories=categories,
        existing=product,
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
                payload["selling_rate"],
                payload["is_active"],
                hsn_sac=payload["hsn_sac"],
                gst_rates=payload["gst_rates"],
                mrp_entries=payload["mrp_entries"],
                specifications=payload["specifications"],
                custom_fields=payload["custom_fields"],
            )
            clear_product_form_state(f"{EDIT_FORM_PREFIX}_{product_id}")
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
            st.session_state[PENDING_EDIT] = product.id

    render_card_grid(page_products, _render, suffix="inv_products", card_min_width=240)


def render(services: dict):
    inventory = services["inventory"]
    bar = render_list(
        INVENTORY_PRODUCTS,
        services=services,
        load_fn=_load_products,
        card_renderer=_render_cards,
        primary_label="Add Product",
        primary_key="inv_products_add_btn",
        count_label="products",
        empty_text="No inventory products yet.",
    )
    if bar["primary_clicked"]:
        _add_product_dialog(inventory)

    pending = st.session_state.pop(PENDING_EDIT, None)
    if pending:
        _edit_product_dialog(inventory, pending)
