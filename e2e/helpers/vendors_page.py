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
    wait_for_streamlit_ready,
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


def _select_filter_option(page: Page, label: str, option: str) -> None:
    """Open a Filters selectbox and choose an option by visible label."""
    open_filter_popover(page)
    control = page.get_by_label(label, exact=True)
    control.click()
    page.wait_for_timeout(300)
    # Typing narrows searchable select options when many vendors exist.
    try:
        control.fill(option)
    except Exception:
        page.keyboard.type(option, delay=15)
    page.wait_for_timeout(400)
    popover = page.locator('[data-baseweb="popover"]')
    option_loc = popover.get_by_text(option, exact=True)
    if option_loc.count() == 0:
        option_loc = page.get_by_role("option", name=option)
    option_loc.first.click()
    page.wait_for_timeout(200)
    page.get_by_role("button", name="Apply").click()
    wait_for_rerun(page)
    close_popovers(page)
    wait_for_streamlit_ready(page, min_ms=500)


def filter_by_name(page: Page, name: str) -> None:
    """Filter by selecting a vendor from the Vendor name dropdown (ID-backed)."""
    _select_filter_option(page, "Vendor name", name)


def filter_by_phone(page: Page, phone: str) -> None:
    apply_filter(page, "Phone", phone)


def filter_by_alternate_phone(page: Page, phone: str) -> None:
    apply_filter(page, "Alternate phone", phone)


def filter_by_balance(page: Page, state: str) -> None:
    """Select a Payable balance option (radio or select)."""
    open_filter_popover(page)
    # Prefer radio label click (Payable balance is a horizontal radio).
    radio = page.get_by_role("radio", name=state)
    if radio.count() > 0:
        radio.first.click()
    else:
        control = page.get_by_label("Payable balance", exact=True)
        control.click()
        page.wait_for_timeout(300)
        option = page.get_by_role("option", name=state)
        if option.count() == 0:
            option = page.locator('[data-baseweb="popover"]').get_by_text(state, exact=True)
        option.first.click()
    page.get_by_role("button", name="Apply").click()
    wait_for_rerun(page)
    close_popovers(page)
    wait_for_streamlit_ready(page, min_ms=500)


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
