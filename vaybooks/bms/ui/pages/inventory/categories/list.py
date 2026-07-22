import streamlit as st

from vaybooks.bms.domain.inventory.category_tree import build_category_path
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.inventory.inventory_product_card import inventory_category_card
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_CATEGORIES

C_ADD = "inv_category_add_dialog"
C_EDIT = "inv_category_edit_dialog"


def _list_categories_indexed(inventory):
    categories = inventory.list_categories(active_only=False)
    return {c.id: c for c in categories}, categories


def _parent_options_from(
    by_id: dict,
    categories,
    exclude_id: str | None = None,
) -> tuple[list[str], dict[str, str | None]]:
    labels = ["— (root)"]
    mapping: dict[str, str | None] = {"— (root)": None}
    for category in categories:
        if exclude_id and category.id == exclude_id:
            continue
        path = build_category_path(category.id, by_id)
        label = path or category.name
        if label in mapping:
            label = f"{label} [{category.id[:8]}]"
        labels.append(label)
        mapping[label] = category.id
    return labels, mapping


def _parent_options(inventory, exclude_id: str | None = None) -> tuple[list[str], dict[str, str | None]]:
    by_id, categories = _list_categories_indexed(inventory)
    return _parent_options_from(by_id, categories, exclude_id=exclude_id)


@st.dialog("Add Category", width="medium", on_dismiss=make_dismiss_handler(C_ADD))
def _add_category_dialog(inventory):
    parent_labels, parent_map = _parent_options(inventory)
    # Use a form so Playwright submits name/parent atomically with the button.
    with st.form("add_inv_cat_form", clear_on_submit=False):
        name = st.text_input("Category name")
        description = st.text_area("Description")
        parent_label = st.selectbox("Parent category", parent_labels)
        submitted = st.form_submit_button("Create Category", type="primary")
    if not submitted:
        return
    parent_id = parent_map.get(parent_label)
    if not name.strip():
        st.error("Category name is required")
        return
    try:
        inventory.create_category(name, description, parent_id=parent_id)
        st.session_state.pop(C_ADD, None)
        st.success(f"Created {name}")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


@st.dialog("Edit Category", width="medium", on_dismiss=make_dismiss_handler(C_EDIT))
def _edit_category_dialog(inventory, category_id: str):
    by_id, categories = _list_categories_indexed(inventory)
    category = by_id.get(category_id)
    if not category:
        st.error("Category not found")
        return

    parent_labels, parent_map = _parent_options_from(
        by_id, categories, exclude_id=category_id
    )
    current_parent = "— (root)"
    for label, pid in parent_map.items():
        if pid == category.parent_id:
            current_parent = label
            break

    full_path = build_category_path(category_id, by_id) or category.name
    with st.form("edit_inv_cat_form", clear_on_submit=False):
        name = st.text_input("Category name", value=category.name)
        description = st.text_area(
            "Description", value=category.description or ""
        )
        parent_label = st.selectbox(
            "Parent category",
            parent_labels,
            index=parent_labels.index(current_parent)
            if current_parent in parent_labels
            else 0,
        )
        st.caption(f"Full path: {full_path}")
        is_active = st.checkbox("Active", value=category.is_active)
        saved = st.form_submit_button(
            "Save Changes", type="primary", use_container_width=True
        )
    if saved:
        parent_id = parent_map.get(parent_label)
        try:
            inventory.update_category(
                category_id, name, description, is_active, parent_id=parent_id
            )
            st.session_state.pop(C_EDIT, None)
            st.success("Category updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
            return

    if st.button("Delete", use_container_width=True):
        try:
            inventory.delete_category(category_id)
            st.session_state.pop(C_EDIT, None)
            st.success("Category deleted")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _load_categories(services, filters, sort):
    try:
        inventory = services["inventory"]
        by_id, categories = _list_categories_indexed(inventory)
        for category in categories:
            try:
                setattr(category, "path", build_category_path(category.id, by_id))
            except Exception:
                setattr(category, "path", category.name)
        return categories
    except Exception:
        return []


def _render_cards(page_categories, services):
    inventory = services["inventory"]

    def _render(category, _i):
        try:
            product_count = inventory.count_products_in_category(category.id)
        except Exception:
            product_count = 0
        edit_clicked = inventory_category_card(
            category,
            product_count=product_count,
            path=getattr(category, "path", category.name),
        )
        if edit_clicked:
            clear_all_dialog_flags()
            st.session_state[C_EDIT] = category.id
            register_armed_dialog(C_EDIT)
            st.rerun()

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
        page_key_nav="inventory_categories_list",
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        st.session_state[C_ADD] = True
        register_armed_dialog(C_ADD)
    if st.session_state.get(C_ADD):
        _add_category_dialog(inventory)
    if st.session_state.get(C_EDIT):
        _edit_category_dialog(inventory, st.session_state[C_EDIT])
