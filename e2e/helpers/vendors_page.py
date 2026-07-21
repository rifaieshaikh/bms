"""Vendor list page: filter, sort, dialog, assertions."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from e2e.helpers.list_page import (
    apply_filter,
    apply_sort,
    card_titles,
    close_popovers,
    goto_list,
    open_filter_popover,
    record_count_caption,
    wait_for_rerun,
)

PATH = "vendors"
TITLE = "Vendors"
CARD_SELECTOR = "strong"


def goto_vendors(page: Page, base_url: str) -> None:
    goto_list(page, base_url, PATH, TITLE)


def open_add_vendor(page: Page, base_url: str) -> None:
    goto_vendors(page, base_url)
    close_popovers(page)
    page.get_by_role("button", name="Add Vendor").click()
    expect(page.get_by_test_id("stDialog")).to_be_visible()


def click_create(page: Page) -> None:
    page.get_by_test_id("stDialog").get_by_role("button", name="Create Vendor").click()


def submit_create(page: Page) -> None:
    click_create(page)
    expect(page.get_by_test_id("stDialog")).not_to_be_visible(timeout=30_000)
    wait_for_rerun(page)


def submit_create_allow_dialog(page: Page) -> None:
    click_create(page)
    wait_for_rerun(page, 5000)


def filter_by_name(page: Page, name: str) -> None:
    apply_filter(page, "Vendor name", name)


def filter_by_phone(page: Page, phone: str) -> None:
    apply_filter(page, "Phone", phone)


def filter_by_balance(page: Page, state: str) -> None:
    open_filter_popover(page)
    page.get_by_label("Payable balance").click()
    page.get_by_role("option", name=state).click()
    page.get_by_role("button", name="Apply").click()
    wait_for_rerun(page)


def assert_vendor_visible(page: Page, name: str) -> None:
    expect(page.locator(f'{CARD_SELECTOR}:has-text("{name}")').first).to_be_visible()


def assert_empty_or_zero(page: Page) -> None:
    caption = record_count_caption(page)
    if "0 vendors" in caption:
        return
    expect(page.get_by_text("No vendors found.")).to_be_visible()


def sort_by_name(page: Page, direction: str = "Ascending") -> None:
    apply_sort(page, "Vendor name", direction)


def vendor_card_names(page: Page) -> list[str]:
    return card_titles(page, CARD_SELECTOR, grid_suffix="vendors")
