import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.inventory_product_card import inventory_product_card
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_PRODUCTS

PENDING_EDIT = "pending_edit_inventory_product"


@st.dialog("Add Product", width="medium")
def _add_product_dialog(inventory):
    categories = inventory.list_categories(active_only=True)
    if not categories:
        st.error("Create at least one category first.")
        return

    cat_opts = {c.name: c.id for c in categories}
    sku = st.text_input("SKU", key="add_inv_prod_sku")
    name = st.text_input("Product name", key="add_inv_prod_name")
    category = st.selectbox(
        "Category", list(cat_opts.keys()), key="add_inv_prod_cat"
    )
    unit = st.text_input("Unit", value="pcs", key="add_inv_prod_unit")
    rate = st.number_input(
        "Selling rate (₹)", min_value=0.0, value=0.0, key="add_inv_prod_rate"
    )
    opening = st.number_input(
        "Opening qty", min_value=0.0, value=0.0, key="add_inv_prod_opening"
    )

    if st.button("Create Product", type="primary"):
        try:
            inventory.create_product(
                sku, name, cat_opts[category], unit, rate, opening
            )
            st.success(f"Created {name}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Product", width="medium")
def _edit_product_dialog(inventory, product_id: str):
    product = inventory.get_product(product_id)
    if not product:
        st.error("Product not found")
        return

    categories = inventory.list_categories(active_only=False)
    cat_opts = {c.name: c.id for c in categories}
    cat_names = list(cat_opts.keys())
    cat_index = 0
    for i, cid in enumerate(cat_opts.values()):
        if cid == product.category_id:
            cat_index = i
            break

    sku = st.text_input("SKU", value=product.sku, key="edit_inv_prod_sku")
    name = st.text_input("Product name", value=product.name, key="edit_inv_prod_name")
    category = st.selectbox(
        "Category", cat_names, index=cat_index, key="edit_inv_prod_cat"
    )
    unit = st.text_input("Unit", value=product.unit, key="edit_inv_prod_unit")
    rate = st.number_input(
        "Selling rate (₹)",
        min_value=0.0,
        value=float(product.selling_rate),
        key="edit_inv_prod_rate",
    )
    is_active = st.checkbox(
        "Active", value=product.is_active, key="edit_inv_prod_active"
    )
    st.caption(f"Current stock: {product.current_qty:g} {product.unit}")

    if st.button("Save Changes", type="primary"):
        try:
            inventory.update_product(
                product_id, sku, name, cat_opts[category], unit, rate, is_active
            )
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
