"""Playwright helpers for Product Categories list page."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from e2e.helpers.list_page import (
    apply_sort,
    clear_filters,
    close_popovers,
    open_filter_popover,
)

PATH = "inventory-categories"
TITLE = "Product Categories"
GRID_SUFFIX = "inv_categories"
ACTION_TIMEOUT = 15_000


def dialog(page: Page) -> Locator:
    return page.get_by_test_id("stDialog")


def _add_button(page: Page) -> Locator:
    return page.get_by_role("button", name="Add Category", exact=True)


def wait_for_list_ready(page: Page) -> None:
    """Wait until the categories list is interactive after a Streamlit rerun."""
    page.get_by_role("heading", name=TITLE, level=3).wait_for(timeout=ACTION_TIMEOUT)
    page.locator('[data-testid="stAppViewContainer"]').wait_for(
        state="visible", timeout=ACTION_TIMEOUT
    )
    expect(_add_button(page)).to_be_enabled(timeout=ACTION_TIMEOUT)
    close_popovers(page)


def goto_categories(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/{PATH}")
    wait_for_list_ready(page)


def reload_categories(page: Page, base_url: str) -> None:
    """Hard reload after API seed so Streamlit picks up new Mongo data."""
    page.goto(f"{base_url}/{PATH}")
    page.reload()
    wait_for_list_ready(page)


def ensure_clean_list(page: Page, base_url: str) -> None:
    """Fresh navigate so each test starts without stale filters/dialogs."""
    goto_categories(page, base_url)
    chips = page.get_by_role("button", name=re.compile(r"Category name"))
    if chips.count() > 0:
        try:
            if chips.first.is_visible():
                clear_filters(page)
                wait_for_list_ready(page)
        except Exception:
            pass
    close_popovers(page)


def _card_grid(page: Page) -> Locator:
    return page.locator(f'[class*="st-key-card_grid_{GRID_SUFFIX}"]')


def _cards(page: Page) -> Locator:
    grid_cards = _card_grid(page).locator(
        '[data-testid="stVerticalBlockBorderWrapper"]'
    )
    if grid_cards.count() > 0:
        return grid_cards
    return page.locator('[data-testid="stMainBlockContainer"]').locator(
        '[data-testid="stVerticalBlockBorderWrapper"]'
    )


def _card_by_title(page: Page, path_heading: str) -> Locator:
    return _cards(page).filter(has_text=path_heading).first


def _title_locator(page: Page, path_heading: str) -> Locator:
    return page.locator(".z-card-title").filter(has_text=path_heading).first


def _select_option(page: Page, dlg: Locator, label: str, option: str) -> None:
    """Select a Streamlit selectbox option; retries until the value sticks."""
    field = dlg.get_by_label(label, exact=False)
    last_error: Exception | None = None
    for _ in range(3):
        try:
            # Escape closes st.dialog — only click away from open listboxes.
            field.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(option, delay=15)
            popover = page.locator('[data-baseweb="popover"]').last
            option_loc = popover.get_by_text(option, exact=True)
            if option_loc.count() == 0:
                option_loc = popover.locator("li").filter(has_text=option)
            if option_loc.count() == 0:
                option_loc = page.get_by_role("option", name=option)
            expect(option_loc.first).to_be_visible(timeout=ACTION_TIMEOUT)
            option_loc.first.click()
            expect(dlg.get_by_text(option, exact=False).first).to_be_visible(
                timeout=5_000
            )
            return
        except Exception as exc:
            last_error = exc
            # Do not Escape — that dismisses the Streamlit dialog.
            try:
                field.click()
            except Exception:
                pass
    raise AssertionError(f"Could not select {option!r} for {label!r}: {last_error}")


def _fill_text(dlg: Locator, label: str, value: str) -> None:
    field = dlg.get_by_label(label, exact=False)
    field.click()
    field.fill(value)
    field.press("Tab")
    field.page.wait_for_timeout(250)


def _click_through_overlays(locator: Locator) -> None:
    """Force-click list actions so leftover Baseweb layers cannot block them."""
    close_popovers(locator.page)
    locator.click(force=True, timeout=ACTION_TIMEOUT)


def open_add_dialog(page: Page) -> None:
    close_popovers(page)
    # Prefer the keyed primary action over a generic role match.
    keyed = page.locator('[class*="st-key-inv_categories_add_btn"]').get_by_role(
        "button"
    )
    add_btn = keyed if keyed.count() > 0 else _add_button(page)
    for attempt in range(5):
        expect(add_btn).to_be_enabled(timeout=ACTION_TIMEOUT)
        close_popovers(page)
        _click_through_overlays(add_btn)
        dlg = dialog(page)
        try:
            expect(dlg).to_be_visible(timeout=12_000)
            expect(dlg.get_by_label("Category name")).to_be_visible(timeout=5_000)
            return
        except AssertionError:
            if attempt == 2:
                page.reload()
                wait_for_list_ready(page)
                keyed = page.locator(
                    '[class*="st-key-inv_categories_add_btn"]'
                ).get_by_role("button")
                add_btn = keyed if keyed.count() > 0 else _add_button(page)
            else:
                close_popovers(page)
                expect(add_btn).to_be_enabled(timeout=ACTION_TIMEOUT)
    expect(dialog(page)).to_be_visible(timeout=ACTION_TIMEOUT)


def open_add_category(page: Page, base_url: str) -> None:
    # Always navigate fresh so Add is clickable after prior creates/reruns.
    goto_categories(page, base_url)
    open_add_dialog(page)


def fill_add_form(
    page: Page,
    name: str,
    description: str = "",
    parent_label: str = "— (root)",
) -> None:
    dlg = dialog(page)
    _fill_text(dlg, "Category name", name)
    expect(dlg.get_by_label("Category name", exact=False)).to_have_value(
        name, timeout=ACTION_TIMEOUT
    )
    if description:
        _fill_text(dlg, "Description", description)
    if parent_label != "— (root)":
        _select_option(page, dlg, "Parent category", parent_label)
        # Forms don't live-update Chain caption; confirm combobox selection.
        expect(dlg.get_by_text(parent_label, exact=False).first).to_be_visible(
            timeout=ACTION_TIMEOUT
        )


def fill_edit_form(
    page: Page,
    name: str,
    description: str = "",
    parent_label: str | None = None,
    *,
    is_active: bool | None = None,
) -> None:
    dlg = dialog(page)
    _fill_text(dlg, "Category name", name)
    if description:
        _fill_text(dlg, "Description", description)
    if parent_label is not None:
        _select_option(page, dlg, "Parent category", parent_label)
    if is_active is not None:
        checkbox = dlg.get_by_label("Active")
        if is_active:
            checkbox.check()
        else:
            checkbox.uncheck()


def submit_create(page: Page) -> None:
    dlg = dialog(page)
    page.wait_for_timeout(400)
    btn = dlg.get_by_role("button", name="Create Category")
    expect(btn).to_be_enabled(timeout=ACTION_TIMEOUT)
    btn.click(timeout=ACTION_TIMEOUT)
    try:
        expect(dialog(page)).not_to_be_visible(timeout=30_000)
    except AssertionError:
        alert = dialog(page).locator('[data-testid="stAlert"]')
        detail = ""
        if alert.count() > 0:
            try:
                detail = alert.first.inner_text()
            except Exception:
                detail = "(alert present)"
        name_val = ""
        try:
            name_val = dialog(page).get_by_label("Category name", exact=False).input_value()
        except Exception:
            pass
        raise AssertionError(
            f"Create dialog stayed open. name={name_val!r} alert={detail!r}"
        )
    wait_for_list_ready(page)


def submit_create_allow_dialog(page: Page) -> None:
    dialog(page).get_by_role("button", name="Create Category").click()
    expect(dialog(page)).to_be_visible(timeout=ACTION_TIMEOUT)
    expect(dialog(page).locator('[data-testid="stAlert"]').first).to_be_visible(
        timeout=ACTION_TIMEOUT
    )


def submit_save_edit(page: Page) -> None:
    dlg = dialog(page)
    page.wait_for_timeout(400)
    btn = dlg.get_by_role("button", name="Save Changes")
    expect(btn).to_be_enabled(timeout=ACTION_TIMEOUT)
    btn.click(force=True)
    expect(dialog(page)).not_to_be_visible(timeout=30_000)
    wait_for_list_ready(page)


def click_delete(page: Page) -> None:
    dialog(page).get_by_role("button", name="Delete").click()
    expect(dialog(page)).not_to_be_visible(timeout=ACTION_TIMEOUT)
    wait_for_list_ready(page)


def apply_name_filter(page: Page, name: str) -> None:
    open_filter_popover(page)
    page.get_by_label("Category name", exact=True).fill(name)
    page.get_by_role("button", name="Apply").click()
    # Wait for filter chip — proves Streamlit committed the filter.
    expect(
        page.get_by_role("button", name=re.compile(re.escape(name)))
    ).to_be_visible(timeout=ACTION_TIMEOUT)
    close_popovers(page)
    # Apply often leaves an invisible Baseweb layer over the toolbar.
    page.locator('[data-testid="stMainBlockContainer"]').get_by_role(
        "heading", name=TITLE, level=3
    ).click(force=True)
    page.wait_for_timeout(200)
    wait_for_list_ready(page)


def filter_by_name(page: Page, name: str) -> None:
    apply_name_filter(page, name)
    # Prefer card title; fall back to any visible title text containing name.
    try:
        expect(_card_by_title(page, name)).to_be_visible(timeout=8_000)
    except AssertionError:
        expect(_title_locator(page, name)).to_be_visible(timeout=ACTION_TIMEOUT)


def open_edit_for(page: Page, path_heading: str) -> None:
    """Open Edit for a category card after filtering to a single result."""
    close_popovers(page)
    wait_for_list_ready(page)
    title = page.locator(".z-card-title").filter(has_text=path_heading).first
    expect(title).to_be_visible(timeout=ACTION_TIMEOUT)
    main = page.locator('[data-testid="stMainBlockContainer"]')
    edit = main.get_by_role("button", name="Edit")
    expect(edit.first).to_be_visible(timeout=ACTION_TIMEOUT)
    for _ in range(3):
        close_popovers(page)
        _click_through_overlays(edit.first)
        try:
            expect(dialog(page)).to_be_visible(timeout=12_000)
            expect(dialog(page).get_by_label("Category name")).to_be_visible(
                timeout=5_000
            )
            return
        except AssertionError:
            expect(edit.first).to_be_visible(timeout=ACTION_TIMEOUT)
    expect(dialog(page)).to_be_visible(timeout=ACTION_TIMEOUT)


def filter_active_only(page: Page, enabled: bool = True) -> None:
    open_filter_popover(page)
    checkbox = page.get_by_label("Active only")
    if enabled:
        checkbox.check()
    else:
        checkbox.uncheck()
    page.get_by_role("button", name="Apply").click()
    close_popovers(page)
    wait_for_list_ready(page)


def sort_by_name(page: Page, direction: str = "Ascending") -> None:
    apply_sort(page, "Category name", direction)
    wait_for_list_ready(page)


def category_card_paths(page: Page) -> list[str]:
    titles = page.locator(".z-card-title").all_inner_texts()
    cleaned = [t.strip() for t in titles if t.strip()]
    if cleaned:
        return cleaned
    return []


def assert_card_visible(page: Page, path_heading: str) -> None:
    try:
        expect(_card_by_title(page, path_heading)).to_be_visible(timeout=8_000)
    except AssertionError:
        expect(_title_locator(page, path_heading)).to_be_visible(timeout=ACTION_TIMEOUT)


def assert_card_badge(page: Page, path_heading: str, badge: str) -> None:
    card = _card_by_title(page, path_heading)
    try:
        expect(card).to_be_visible(timeout=8_000)
    except AssertionError:
        expect(_title_locator(page, path_heading)).to_be_visible(timeout=ACTION_TIMEOUT)
        card = _cards(page).filter(has_text=path_heading).first
    expect(card.get_by_text(badge, exact=True)).to_be_visible(timeout=ACTION_TIMEOUT)


def assert_error_in_dialog(page: Page, text: str) -> None:
    expect(dialog(page).get_by_text(text)).to_be_visible(timeout=ACTION_TIMEOUT)


def assert_empty_or_zero(page: Page) -> None:
    caption = page.locator('[data-testid="stCaptionContainer"]').first
    expect(caption).to_be_visible(timeout=ACTION_TIMEOUT)
    text = caption.inner_text()
    if "0 categories" in text:
        return
    expect(page.get_by_text("No product categories yet.")).to_be_visible(
        timeout=ACTION_TIMEOUT
    )
