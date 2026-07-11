"""Product Categories E2E: list/filter/sort, CRUD, hierarchy, validation."""

import pytest
from playwright.sync_api import Page, expect

from e2e.helpers import categories_page as cp
from e2e.helpers.inventory_seed import (
    create_category,
    create_category_chain,
    create_product_in_category,
    unique_sku,
)
from e2e.helpers.list_page import clear_filters
from e2e.helpers.unique import unique_name, unique_suffix


@pytest.fixture(autouse=True)
def _reset_category_filters(page: Page, streamlit_server: str) -> None:
    cp.ensure_clean_list(page, streamlit_server)


class TestCategoryListFilterSort:
    def test_list_page_loads(self, page: Page, streamlit_server: str) -> None:
        cp.goto_categories(page, streamlit_server)
        assert "Product Categories" in page.content()
        page.get_by_role("button", name="Add Category").wait_for()

    def test_filter_partial_name_returns_empty(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.apply_name_filter(page, "NoSuchCategoryXYZ")
        cp.assert_empty_or_zero(page)

    def test_filter_clear_restores_list(self, page: Page, streamlit_server: str) -> None:
        before = cp.category_card_paths(page)
        cp.apply_name_filter(page, "NoSuchCategoryXYZ")
        clear_filters(page)
        after = cp.category_card_paths(page)
        assert len(after) >= len(before) or len(before) == 0

    def test_filter_by_name_finds_category(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("FilterCat")
        create_category(name)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, name)
        cp.assert_card_visible(page, name)

    def test_sort_by_name(self, page: Page, streamlit_server: str) -> None:
        first = unique_name("SortA")
        second = unique_name("SortB")
        create_category(first)
        create_category(second)
        cp.reload_categories(page, streamlit_server)
        before = cp.category_card_paths(page)
        cp.sort_by_name(page, "Oldest first")
        after = cp.category_card_paths(page)
        assert before != after or len(before) < 2


class TestCategoryCreate:
    def test_create_root_minimal(self, page: Page, streamlit_server: str) -> None:
        name = unique_name("Root")
        cp.open_add_category(page, streamlit_server)
        cp.fill_add_form(page, name)
        cp.submit_create(page)
        cp.filter_by_name(page, name)
        cp.assert_card_visible(page, name)

    def test_create_with_description(self, page: Page, streamlit_server: str) -> None:
        name = unique_name("Desc")
        cp.open_add_category(page, streamlit_server)
        cp.fill_add_form(page, name, description="E2E description text")
        cp.submit_create(page)
        cp.filter_by_name(page, name)
        expect(page.get_by_text("E2E description text")).to_be_visible()

    def test_create_child_shows_path(self, page: Page, streamlit_server: str) -> None:
        root = unique_name("Parent")
        child = unique_name("Child")
        create_category(root)
        cp.reload_categories(page, streamlit_server)
        cp.open_add_category(page, streamlit_server)
        cp.fill_add_form(page, child, parent_label=root)
        cp.submit_create(page)
        cp.filter_by_name(page, child)
        cp.assert_card_visible(page, f"{root} > {child}")

    def test_same_name_different_parents(self, page: Page, streamlit_server: str) -> None:
        root_a = unique_name("RootA")
        root_b = unique_name("RootB")
        shared = f"E2E Shared {unique_suffix()}"
        id_a = create_category(root_a)
        create_category(root_b)
        create_category(shared, id_a)
        cp.reload_categories(page, streamlit_server)
        cp.open_add_category(page, streamlit_server)
        cp.fill_add_form(page, shared, parent_label=root_b)
        cp.submit_create(page)
        cp.apply_name_filter(page, shared)
        cp.assert_card_visible(page, f"{root_a} > {shared}")
        cp.assert_card_visible(page, f"{root_b} > {shared}")


class TestCategoryValidation:
    def test_empty_name_on_create(self, page: Page, streamlit_server: str) -> None:
        cp.open_add_category(page, streamlit_server)
        cp.fill_add_form(page, "   ")
        cp.submit_create_allow_dialog(page)
        cp.assert_error_in_dialog(page, "Category name is required")

    def test_empty_name_on_edit(self, page: Page, streamlit_server: str) -> None:
        name = unique_name("EditEmpty")
        create_category(name)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, name)
        cp.open_edit_for(page, name)
        cp.fill_edit_form(page, "   ")
        cp.dialog(page).get_by_role("button", name="Save Changes").click()
        cp.assert_error_in_dialog(page, "Category name is required")

    def test_duplicate_under_same_parent(self, page: Page, streamlit_server: str) -> None:
        root = unique_name("DupRoot")
        child = unique_name("DupChild")
        root_id = create_category(root)
        create_category(child, root_id)
        cp.reload_categories(page, streamlit_server)
        cp.open_add_category(page, streamlit_server)
        cp.fill_add_form(page, child, parent_label=root)
        cp.submit_create_allow_dialog(page)
        cp.assert_error_in_dialog(page, "already exists under the parent")


class TestCategoryEdit:
    def test_rename_category(self, page: Page, streamlit_server: str) -> None:
        old_name = unique_name("Old")
        new_name = unique_name("New")
        create_category(old_name)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, old_name)
        cp.open_edit_for(page, old_name)
        cp.fill_edit_form(page, new_name)
        cp.submit_save_edit(page)
        cp.filter_by_name(page, new_name)
        cp.assert_card_visible(page, new_name)

    def test_deactivate_shows_inactive_badge(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("Inactive")
        create_category(name)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, name)
        cp.open_edit_for(page, name)
        cp.fill_edit_form(page, name, is_active=False)
        cp.submit_save_edit(page)
        cp.filter_by_name(page, name)
        cp.assert_card_badge(page, name, "Inactive")

    def test_reparent_updates_path(self, page: Page, streamlit_server: str) -> None:
        root_a = unique_name("MoveA")
        root_b = unique_name("MoveB")
        child = unique_name("MoveChild")
        root_a_id = create_category(root_a)
        create_category(root_b)
        create_category(child, root_a_id)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, child)
        cp.open_edit_for(page, f"{root_a} > {child}")
        cp.fill_edit_form(page, child, parent_label=root_b)
        cp.submit_save_edit(page)
        cp.filter_by_name(page, child)
        cp.assert_card_visible(page, f"{root_b} > {child}")


class TestCategoryDelete:
    def test_delete_empty_leaf(self, page: Page, streamlit_server: str) -> None:
        name = unique_name("DeleteMe")
        create_category(name)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, name)
        cp.open_edit_for(page, name)
        cp.click_delete(page)
        cp.apply_name_filter(page, name)
        cp.assert_empty_or_zero(page)

    def test_delete_blocked_with_children(
        self, page: Page, streamlit_server: str
    ) -> None:
        root = unique_name("DelRoot")
        child = unique_name("DelChild")
        root_id = create_category(root)
        create_category(child, root_id)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, root)
        cp.open_edit_for(page, root)
        cp.dialog(page).get_by_role("button", name="Delete").click()
        cp.assert_error_in_dialog(page, "child categories")

    def test_delete_blocked_with_products(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("WithProd")
        cat_id = create_category(name)
        create_product_in_category(cat_id, unique_sku(), "E2E Widget")
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, name)
        cp.open_edit_for(page, name)
        cp.dialog(page).get_by_role("button", name="Delete").click()
        cp.assert_error_in_dialog(page, "products")

    def test_delete_child_then_parent(self, page: Page, streamlit_server: str) -> None:
        root = unique_name("DelParent")
        child = unique_name("DelLeaf")
        root_id = create_category(root)
        create_category(child, root_id)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, child)
        cp.open_edit_for(page, f"{root} > {child}")
        cp.click_delete(page)
        cp.filter_by_name(page, root)
        cp.open_edit_for(page, root)
        cp.click_delete(page)
        cp.apply_name_filter(page, root)
        cp.assert_empty_or_zero(page)


class TestCategoryHierarchy:
    def test_three_level_path(self, page: Page, streamlit_server: str) -> None:
        l1 = unique_name("L1")
        l2 = unique_name("L2")
        l3 = unique_name("L3")
        create_category_chain(l1, l2, l3)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, l3)
        cp.assert_card_visible(page, f"{l1} > {l2} > {l3}")

    def test_cycle_prevention_on_edit(self, page: Page, streamlit_server: str) -> None:
        a = unique_name("CycleA")
        b = unique_name("CycleB")
        c = unique_name("CycleC")
        create_category_chain(a, b, c)
        cp.reload_categories(page, streamlit_server)
        cp.filter_by_name(page, a)
        cp.open_edit_for(page, a)
        cp.fill_edit_form(page, a, parent_label=f"{a} > {b} > {c}")
        cp.dialog(page).get_by_role("button", name="Save Changes").click()
        cp.assert_error_in_dialog(page, "cycle")
