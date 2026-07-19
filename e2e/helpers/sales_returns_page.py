"""Playwright helpers for Sales Returns list, dialog, and detail actions."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from e2e.helpers.list_page import (
    close_popovers,
    wait_for_rerun,
    wait_for_streamlit_ready,
)

PATH = "sales-returns"
TITLE = "Sales Returns"
GRID_SUFFIX = "sales_returns_list"
ACTION_TIMEOUT = 30_000


def dialog(page: Page) -> Locator:
    return page.get_by_test_id("stDialog")


def wait_for_list_ready(page: Page) -> None:
    page.get_by_role("heading", name=TITLE, level=3).wait_for(timeout=ACTION_TIMEOUT)
    page.locator('[data-testid="stAppViewContainer"]').wait_for(
        state="visible", timeout=ACTION_TIMEOUT
    )
    expect(page.get_by_role("button", name="+ Record Return")).to_be_enabled(
        timeout=ACTION_TIMEOUT
    )
    close_popovers(page)


def goto_returns(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/{PATH}")
    wait_for_list_ready(page)


def reload_returns(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/{PATH}")
    page.reload()
    wait_for_list_ready(page)


def open_record_return(page: Page, base_url: str) -> None:
    goto_returns(page, base_url)
    close_popovers(page)
    page.get_by_role("button", name="+ Record Return").click()
    expect(dialog(page)).to_be_visible(timeout=ACTION_TIMEOUT)


def _selectbox_control(root: Locator, label: str) -> Locator:
    """Click target for a Streamlit selectbox labeled ``label``."""
    by_label = root.get_by_label(label, exact=True)
    if by_label.count() > 0:
        return by_label.first
    block = root.locator('[data-testid="stSelectbox"]').filter(has_text=label)
    combo = block.get_by_role("combobox")
    if combo.count() > 0:
        return combo.first
    return block.locator("div").last


def _text_input(root: Locator, label: str) -> Locator:
    by_label = root.get_by_label(label, exact=True)
    if by_label.count() > 0:
        return by_label.first
    block = root.locator('[data-testid="stTextInput"]').filter(has_text=label)
    box = block.get_by_role("textbox")
    if box.count() > 0:
        return box.first
    return block.locator("input").first


def _select_option(page: Page, root: Locator, label: str, option: str) -> None:
    control = _selectbox_control(root, label)
    control.click()
    page.wait_for_timeout(300)
    # Streamlit searchable selectboxes (accept_new_options) need typed filter text.
    try:
        control.fill(option)
    except Exception:
        page.keyboard.type(option, delay=15)
    page.wait_for_timeout(500)
    popover = page.locator('[data-baseweb="popover"]')
    option_loc = popover.get_by_text(option, exact=True)
    if option_loc.count() == 0:
        option_loc = page.get_by_role("option", name=option)
    if option_loc.count() == 0:
        # Partial match on unique customer name fragment
        option_loc = page.get_by_text(option, exact=True)
    if option_loc.count() == 0 and "—" in option:
        option_loc = page.get_by_text(option.split("—", 1)[0].strip())
    expect(option_loc.first).to_be_visible(timeout=ACTION_TIMEOUT)
    option_loc.first.click()
    page.wait_for_timeout(400)


def select_customer(page: Page, name: str, phone: str) -> None:
    dlg = dialog(page)
    label = f"{name} — {phone}"
    control = _selectbox_control(dlg, "Customer Name")
    control.click()
    page.wait_for_timeout(350)
    # Type to filter — do not fill() (accept_new_options treats fill as a new value).
    page.keyboard.type(name, delay=20)
    page.wait_for_timeout(600)
    option = page.locator('[data-baseweb="popover"]').get_by_text(label, exact=True)
    if option.count() == 0:
        option = page.get_by_role("option", name=label)
    if option.count() == 0:
        option = page.get_by_text(label, exact=True)
    expect(option.first).to_be_visible(timeout=ACTION_TIMEOUT)
    option.first.click()
    wait_for_rerun(page, 2500)
    expect(dialog(page)).to_be_visible(timeout=ACTION_TIMEOUT)
    expect(dialog(page).get_by_text(re.compile(r"Existing customer"))).to_be_visible(
        timeout=ACTION_TIMEOUT
    )


def _wait_streamlit_idle(page: Page, *, timeout: int = ACTION_TIMEOUT) -> None:
    """Wait until the Streamlit 'Running...' status clears."""
    running = page.get_by_role("img", name="Running...")
    try:
        running.first.wait_for(state="visible", timeout=2_000)
    except Exception:
        pass
    try:
        expect(running).to_have_count(0, timeout=timeout)
    except AssertionError:
        # Status widget may keep a hidden node; fall back to a settle delay.
        page.wait_for_timeout(1500)


def select_original_invoice(page: Page, store_invoice_number: str) -> None:
    dlg = dialog(page)
    expect(dlg).to_be_visible(timeout=ACTION_TIMEOUT)
    _selectbox_control(dlg, "Original invoice number").click()
    page.wait_for_timeout(500)
    # Labels look like: "INV-xxx — 2026-07-17 — ₹200.00"
    option = page.get_by_text(re.compile(re.escape(store_invoice_number)))
    expect(option.first).to_be_visible(timeout=ACTION_TIMEOUT)
    option.first.click()
    _wait_streamlit_idle(page)
    wait_for_rerun(page, 1500)
    expect(dialog(page)).to_be_visible(timeout=ACTION_TIMEOUT)
    # Invoice selection rebuilds the lines editor; scroll so lower fields mount.
    try:
        dialog(page).evaluate(
            "el => { el.scrollTop = el.scrollHeight; }"
        )
    except Exception:
        page.keyboard.press("End")
    page.wait_for_timeout(500)
    expect(
        dialog(page).get_by_role("textbox", name="Return reason")
    ).to_be_visible(timeout=ACTION_TIMEOUT)


def fill_return_reason(page: Page, reason: str) -> None:
    field = dialog(page).get_by_role("textbox", name="Return reason")
    expect(field).to_be_visible(timeout=ACTION_TIMEOUT)
    field.scroll_into_view_if_needed()
    field.click()
    field.fill("")
    # Character typing keeps Streamlit session_state in sync (fill alone can be lost).
    field.press_sequentially(reason, delay=25)
    field.press("Tab")
    page.wait_for_timeout(400)
    expect(field).to_have_value(reason)


def read_return_number(page: Page) -> str:
    field = _text_input(dialog(page), "Return number")
    return (field.input_value() or "").strip()


def submit_for_approval(page: Page) -> None:
    reason = dialog(page).get_by_role("textbox", name="Return reason")
    if reason.count() and not (reason.input_value() or "").strip():
        raise AssertionError("Return reason is empty before submit")
    btn = dialog(page).get_by_role("button", name="Submit for approval")
    btn.scroll_into_view_if_needed()
    btn.click()
    _wait_streamlit_idle(page)
    try:
        expect(dialog(page)).not_to_be_visible(timeout=ACTION_TIMEOUT)
    except AssertionError as exc:
        alert = dialog(page).locator('[data-testid="stAlert"]')
        detail = ""
        if alert.count():
            detail = alert.first.inner_text()
        reason_val = ""
        try:
            reason_val = reason.input_value()
        except Exception:
            pass
        raise AssertionError(
            f"Submit for approval left dialog open. Alert: {detail!r}; "
            f"reason={reason_val!r}"
        ) from exc
    wait_for_rerun(page, 2500)


def submit_for_approval_allow_error(page: Page) -> None:
    btn = dialog(page).get_by_role("button", name="Submit for approval")
    btn.scroll_into_view_if_needed()
    btn.click()
    wait_for_rerun(page, 2500)


def assert_dialog_error(page: Page, text: str | re.Pattern) -> None:
    expect(dialog(page).get_by_text(text)).to_be_visible(timeout=ACTION_TIMEOUT)


def _open_filter_popover_safe(page: Page) -> None:
    """Open Filters even when a leftover overlay blocks the normal path."""
    close_popovers(page)
    btn = page.locator('[data-testid="stPopoverButton"]').first
    expect(btn).to_be_visible(timeout=ACTION_TIMEOUT)
    try:
        btn.click(timeout=5_000)
    except Exception:
        btn.click(force=True)
    page.get_by_text("Filters", exact=True).wait_for(timeout=ACTION_TIMEOUT)


def filter_by_return_number(page: Page, return_number: str) -> None:
    _open_filter_popover_safe(page)
    page.get_by_label("Return number", exact=True).fill(return_number)
    page.get_by_role("button", name="Apply").click()
    wait_for_rerun(page)
    close_popovers(page)
    wait_for_streamlit_ready(page, min_ms=500)


def filter_by_customer(page: Page, customer_name: str) -> None:
    _open_filter_popover_safe(page)
    page.get_by_label("Customer", exact=True).fill(customer_name)
    page.get_by_role("button", name="Apply").click()
    wait_for_rerun(page)
    close_popovers(page)
    wait_for_streamlit_ready(page, min_ms=500)


def filter_by_status(page: Page, status: str) -> None:
    _open_filter_popover_safe(page)
    status_box = page.get_by_label("Status", exact=True)
    status_box.click()
    page.wait_for_timeout(400)
    option = page.locator('[data-baseweb="popover"]').get_by_text(status, exact=True)
    if option.count() == 0:
        option = page.get_by_role("option", name=status)
    option.first.click()
    page.wait_for_timeout(200)
    page.get_by_role("button", name="Apply").click()
    wait_for_rerun(page)
    close_popovers(page)
    wait_for_streamlit_ready(page, min_ms=500)


def _card_grid(page: Page) -> Locator:
    return page.locator(f'[class*="st-key-card_grid_{GRID_SUFFIX}"]')


def assert_return_card_visible(page: Page, return_number: str) -> None:
    # Prefer scoped grid; fall back to page text (HTML card titles).
    grid_match = _card_grid(page).get_by_text(return_number, exact=True)
    if grid_match.count() > 0:
        expect(grid_match.first).to_be_visible(timeout=ACTION_TIMEOUT)
        return
    expect(page.get_by_text(return_number, exact=True).first).to_be_visible(
        timeout=ACTION_TIMEOUT
    )


def assert_return_card_absent(page: Page, return_number: str) -> None:
    expect(page.get_by_text(return_number, exact=True)).to_have_count(0)


def open_view_for_return(
    page: Page, return_number: str, *, base_url: str | None = None
) -> None:
    """Open return detail via list View (keeps Streamlit navigation session)."""
    if base_url:
        goto_returns(page, base_url)
    filter_by_return_number(page, return_number)
    assert_return_card_visible(page, return_number)
    # After exact filter, a single card remains — avoid brittle wrapper ancestry.
    view_btn = page.get_by_role("button", name="View").first
    view_btn.scroll_into_view_if_needed()
    view_btn.click()
    page.get_by_role("heading", name="Sales Return", level=3).wait_for(
        timeout=ACTION_TIMEOUT
    )
    wait_for_streamlit_ready(page)
    number_field = _text_input(page.locator('[data-testid="stMain"]'), "Return number")
    expect(number_field).to_have_value(return_number)


def detail_status(page: Page) -> str:
    return page.get_by_label("Status", exact=True).input_value().strip()


def detail_return_number(page: Page) -> str:
    return page.get_by_label("Return number", exact=True).input_value().strip()


def click_detail_action(page: Page, label: str) -> None:
    btn = page.get_by_role("button", name=label, exact=True).first
    expect(btn).to_be_enabled(timeout=ACTION_TIMEOUT)
    btn.scroll_into_view_if_needed()
    btn.click()
    wait_for_rerun(page, 3500)
    wait_for_streamlit_ready(page)


def assert_return_status(
    page: Page, status: str, *, return_number: str | None = None
) -> None:
    """Assert status in Mongo (source of truth) and on the detail Status field."""
    if return_number:
        from e2e.helpers.sales_seed import get_return_by_number

        sales_return = get_return_by_number(return_number)
        assert sales_return is not None, f"Missing return {return_number}"
        assert sales_return.status.value == status, (
            f"Expected DB status {status!r}, got {sales_return.status.value!r}"
        )
    status_field = page.locator('[data-testid="stTextInput"]').filter(
        has_text="Status"
    ).get_by_role("textbox")
    if status_field.count() == 0:
        status_field = page.get_by_label("Status", exact=True)
    expect(status_field.first).to_have_value(status, timeout=ACTION_TIMEOUT)


def assert_detail_status(page: Page, status: str) -> None:
    assert_return_status(page, status)


def assert_edit_disabled_on_detail(page: Page) -> None:
    edit = page.get_by_role("button", name="Edit", exact=True)
    if edit.count() == 0:
        return
    expect(edit.first).to_be_disabled()


def invoice_option_visible_in_dialog(page: Page, store_invoice_number: str) -> bool:
    dlg = dialog(page)
    _selectbox_control(dlg, "Original invoice number").click()
    page.wait_for_timeout(500)
    matches = page.get_by_text(re.compile(re.escape(store_invoice_number)))
    visible = matches.count() > 0
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    return visible


def create_pending_return_from_invoice(
    page: Page,
    base_url: str,
    *,
    customer_name: str,
    phone: str,
    store_invoice_number: str,
    reason: str = "E2E return reason",
) -> str:
    """Open dialog, link invoice, submit; return the assigned return number."""
    open_record_return(page, base_url)
    select_customer(page, customer_name, phone)
    select_original_invoice(page, store_invoice_number)
    return_number = read_return_number(page)
    if not return_number.startswith("SR-"):
        raise AssertionError(f"Expected reserved SR- number, got {return_number!r}")
    fill_return_reason(page, reason)
    submit_for_approval(page)
    # Fresh navigation clears dialog/session chrome; filter finds card across pages.
    goto_returns(page, base_url)
    filter_by_return_number(page, return_number)
    assert_return_card_visible(page, return_number)
    return return_number
