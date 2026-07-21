"""Customer list page: filter, sort, dialog, assertions."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from e2e.helpers.list_page import (
    apply_filter,
    apply_sort,
    card_titles,
    clear_filters,
    close_popovers,
    goto_list,
    open_filter_popover,
    open_sort_popover,
    record_count_caption,
    wait_for_rerun,
)

PATH = "customers"
TITLE = "Customers"
CARD_SELECTOR = "h3"


def goto_customers(page: Page, base_url: str) -> None:
    goto_list(page, base_url, PATH, TITLE)


def open_add_customer(page: Page, base_url: str) -> None:
    goto_customers(page, base_url)
    close_popovers(page)
    page.get_by_role("button", name="Add Customer").click()
    expect(page.get_by_test_id("stDialog")).to_be_visible()


def click_create(page: Page) -> None:
    page.get_by_test_id("stDialog").get_by_role("button", name="Create Customer").click()


def submit_create(page: Page) -> None:
    click_create(page)
    expect(page.get_by_test_id("stDialog")).not_to_be_visible(timeout=30_000)
    wait_for_rerun(page)


def submit_create_allow_dialog(page: Page) -> None:
    click_create(page)
    wait_for_rerun(page, 5000)


def submit_save_edit(page: Page) -> None:
    page.get_by_test_id("stDialog").get_by_role("button", name="Save Changes").click()
    wait_for_rerun(page)


def filter_by_name(page: Page, name: str) -> None:
    apply_filter(page, "Customer name", name)


def filter_by_phone(page: Page, phone: str) -> None:
    apply_filter(page, "Phone", phone)


def filter_by_gstin(page: Page, gstin: str) -> None:
    apply_filter(page, "GSTIN", gstin)


def filter_by_registration(page: Page, reg_type: str) -> None:
    open_filter_popover(page)
    page.get_by_label("Registration type").click()
    page.locator('[data-baseweb="popover"]').get_by_text(reg_type, exact=True).click()
    page.get_by_role("button", name="Apply").click()
    wait_for_rerun(page)


def assert_card_count(page: Page, count: int) -> None:
    expect(page.locator(CARD_SELECTOR)).to_have_count(count)


def assert_card_visible(page: Page, name: str) -> None:
    expect(page.get_by_role("heading", name=name, level=3)).to_be_visible()


def assert_caption_count(page: Page, count: int) -> None:
    expect(page.locator('[data-testid="stCaptionContainer"]').first).to_contain_text(
        f"{count} customers"
    )


def assert_empty_or_zero(page: Page) -> None:
    caption = record_count_caption(page)
    if "0 customers" in caption:
        return
    expect(page.get_by_text("No customers found.")).to_be_visible()


def sort_by_name(page: Page, direction: str = "Ascending") -> None:
    apply_sort(page, "Customer name", direction)


def customer_card_names(page: Page) -> list[str]:
    return card_titles(page, CARD_SELECTOR, grid_suffix="customers")
