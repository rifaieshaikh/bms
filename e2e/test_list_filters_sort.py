"""Playwright E2E filter/sort tests for all list pages."""

import pytest
from playwright.sync_api import Page

from e2e.helpers.list_page import (
    LIST_PAGES,
    apply_sort,
    card_titles,
    goto_list,
    open_filter_popover,
    open_sort_popover,
)

SORT_FIELD_BY_PAGE = {
    "customers": "Customer name",
    "vendors": "Vendor name",
    "orders": "Order number",
    "items": "Measurement bill number",
    "accounts": "Account name",
    "vouchers": "Voucher number",
    "inventory-products": "Product name",
    "trial-balance": "Account name",
}


@pytest.mark.parametrize("path,title,selector", LIST_PAGES)
def test_list_page_loads(page: Page, streamlit_server: str, path, title, selector):
    goto_list(page, streamlit_server, path, title)
    assert title in page.content()


@pytest.mark.parametrize("path,title,selector", LIST_PAGES)
def test_sort_popover_apply_does_not_crash(
    page: Page, streamlit_server: str, path, title, selector
):
    goto_list(page, streamlit_server, path, title)
    field = SORT_FIELD_BY_PAGE.get(path)
    if not field:
        open_sort_popover(page)
        page.get_by_role("button", name="Apply sort").click()
    else:
        apply_sort(page, field, "Ascending")
    page.wait_for_timeout(1000)
    assert title in page.content()


@pytest.mark.parametrize("path,title,selector", LIST_PAGES)
def test_sort_without_apply_keeps_order(
    page: Page, streamlit_server: str, path, title, selector
):
    if selector != "h3":
        pytest.skip("card title extraction only implemented for h3 pages")
    goto_list(page, streamlit_server, path, title)
    before = card_titles(page, selector)
    open_sort_popover(page)
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    after = card_titles(page, selector)
    assert before == after
