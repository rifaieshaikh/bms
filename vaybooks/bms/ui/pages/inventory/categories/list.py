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
from vaybooks.bms.ui.keyboard.dialog_actions import (
    consume_submit,
    open_dialog,
)
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import render_card_grid

C_ADD = "inv_category_add_dialog"
C_EDIT = "inv_category_edit_dialog"
SUBMIT_ADD = "submit_inv_category_add"
SUBMIT_EDIT = "submit_inv_category_edit"


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


def _open_add_category() -> None:
    clear_all_dialog_flags()
    open_dialog(C_ADD, submit_key=SUBMIT_ADD, clear_others=False)
    mark_wired("inventory.category.add", "list.primary", "dialog.save")


def _open_edit_category(category_id: str) -> None:
    clear_all_dialog_flags()
    open_dialog(C_EDIT, submit_key=SUBMIT_EDIT, value=category_id, clear_others=False)
    mark_wired("inventory.category.save", "dialog.save", "list.edit_nth.1")


@st.dialog("Add Category", width="medium", on_dismiss=make_dismiss_handler(C_ADD))
def _add_category_dialog(inventory):
    mark_wired("dialog.save", "inventory.category.add")
    parent_labels, parent_map = _parent_options(inventory)
    name = st.text_input("Category name", key=f"{C_ADD}_name")
    description = st.text_area("Description", key=f"{C_ADD}_description")
    parent_label = st.selectbox(
        "Parent category", parent_labels, key=f"{C_ADD}_parent"
    )
    cols = st.columns(2)
    do_create = cols[0].button(
        "Create Category", type="primary", use_container_width=True
    ) or consume_submit(SUBMIT_ADD)
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(C_ADD, None)
        st.rerun()
    if not do_create:
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
    mark_wired("dialog.save", "inventory.category.save")
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
    name = st.text_input(
        "Category name", value=category.name, key=f"{C_EDIT}_name_{category_id}"
    )
    description = st.text_area(
        "Description",
        value=category.description or "",
        key=f"{C_EDIT}_description_{category_id}",
    )
    parent_label = st.selectbox(
        "Parent category",
        parent_labels,
        index=parent_labels.index(current_parent)
        if current_parent in parent_labels
        else 0,
        key=f"{C_EDIT}_parent_{category_id}",
    )
    st.caption(f"Full path: {full_path}")
    is_active = st.checkbox(
        "Active", value=category.is_active, key=f"{C_EDIT}_active_{category_id}"
    )

    cols = st.columns(2)
    do_save = cols[0].button(
        "Save Changes", type="primary", use_container_width=True
    ) or consume_submit(SUBMIT_EDIT)
    if cols[1].button("Delete", use_container_width=True):
        try:
            inventory.delete_category(category_id)
            st.session_state.pop(C_EDIT, None)
            st.success("Category deleted")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
        return

    if do_save:
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
            _open_edit_category(category.id)
            st.rerun()

    render_card_grid(
        page_categories,
        _render,
        suffix="inv_categories",
        card_min_width=240,
    )


def render(services: dict):
    inventory = services["inventory"]
    mark_wired(
        "inventory.category.add",
        "list.filters.open",
        "list.sort.open",
        "list.primary",
    )
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
        _open_add_category()
    if bar.get("edit_nth"):
        _open_edit_category(bar["edit_nth"])
        st.rerun()
    if st.session_state.get(C_ADD):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(C_ADD, SUBMIT_ADD)
        register_armed_dialog(C_ADD)
        _add_category_dialog(inventory)
    if st.session_state.get(C_EDIT):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(C_EDIT, SUBMIT_EDIT)
        register_armed_dialog(C_EDIT)
        _edit_category_dialog(inventory, st.session_state[C_EDIT])
