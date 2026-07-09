import streamlit as st

from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.inventory_product_card import inventory_category_card
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_CATEGORIES

PENDING_EDIT = "pending_edit_inventory_category"


@st.dialog("Add Category")
def _add_category_dialog(inventory):
    name = st.text_input("Category name", key="add_inv_cat_name")
    description = st.text_area("Description", key="add_inv_cat_desc")

    if st.button("Create Category", type="primary"):
        if not name.strip():
            st.error("Category name is required")
            return
        try:
            inventory.create_category(name, description)
            st.success(f"Created {name}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Category")
def _edit_category_dialog(inventory, category_id: str):
    category = inventory.get_category(category_id)
    if not category:
        st.error("Category not found")
        return

    name = st.text_input(
        "Category name", value=category.name, key="edit_inv_cat_name"
    )
    description = st.text_area(
        "Description", value=category.description or "", key="edit_inv_cat_desc"
    )
    is_active = st.checkbox("Active", value=category.is_active, key="edit_inv_cat_active")

    cols = st.columns(2)
    if cols[0].button("Save Changes", type="primary", use_container_width=True):
        try:
            inventory.update_category(category_id, name, description, is_active)
            st.success("Category updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Delete", use_container_width=True):
        try:
            inventory.delete_category(category_id)
            st.success("Category deleted")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _load_categories(services, filters, sort):
    try:
        inventory = services["inventory"]
        categories = inventory.list_categories(active_only=False)
        counts: dict[str, int] = {}
        for product in inventory.list_products(active_only=False):
            counts[product.category_id] = counts.get(product.category_id, 0) + 1
        for category in categories:
            setattr(category, "product_count", counts.get(category.id, 0))
        return categories
    except Exception:
        return []


def _render_cards(page_categories, services):
    def _render(category, _i):
        if inventory_category_card(
            category,
            product_count=getattr(category, "product_count", 0),
        ):
            st.session_state[PENDING_EDIT] = category.id

    from vaybooks.bms.ui.styles import render_card_grid

    render_card_grid(
        page_categories,
        _render,
        suffix="inv_categories",
        card_min_width=240,
    )


def render(services: dict):
    inventory = services["inventory"]
    bar = render_list(
        INVENTORY_CATEGORIES,
        services=services,
        load_fn=_load_categories,
        card_renderer=_render_cards,
        primary_label="Add Category",
        primary_key="inv_categories_add_btn",
        count_label="categories",
        empty_text="No product categories yet.",
    )
    if bar["primary_clicked"]:
        _add_category_dialog(inventory)

    pending = st.session_state.pop(PENDING_EDIT, None)
    if pending:
        _edit_category_dialog(inventory, pending)
