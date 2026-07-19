"""Playwright helpers for list pages (filter/sort popovers)."""

from __future__ import annotations

from playwright.sync_api import Page, expect

LIST_PAGES = [
    ("customers", "Customers", "h3"),
    ("vendors", "Vendors", "strong"),
    ("customizationOrders", "Customization Orders", "h3"),
    ("customizationItems", "Customization Items", "h3"),
    ("time", "Time Log", "h3"),
    ("accounts", "Chart of Accounts", "h3"),
    ("vouchers", "All Vouchers", "h3"),
    ("receipts", "Receipts", "h3"),
    ("payments", "Vendor Payments", "h3"),
    ("accounting-invoices", "Accounting Invoices", "h3"),
    ("journal", "Journal Entries", "h3"),
    ("trial-balance", "Trial Balance", "h3"),
    ("activities", "Activity Configuration", "h3"),
    ("services", "Service Configuration", "h3"),
    ("inventory-categories", "Product Categories", "h3"),
    ("inventory-products", "Inventory Products", "h3"),
    ("inventory-stock", "Stock on Hand", "h3"),
    ("inventory-stock-ledger", "Stock Ledger", "h3"),
]


def goto_list(page: Page, base_url: str, path: str, title: str) -> None:
    page.goto(f"{base_url}/{path}")
    page.get_by_role("heading", name=title, level=3).wait_for(timeout=30_000)
    wait_for_streamlit_ready(page)


def wait_for_streamlit_ready(page: Page, *, min_ms: int = 1200) -> None:
    """Allow Streamlit websocket handshake before clicking widgets."""
    page.locator('[data-testid="stAppViewContainer"]').wait_for(
        state="visible", timeout=30_000
    )
    page.wait_for_timeout(min_ms)


def _dialog_open(page: Page) -> bool:
    dlg = page.get_by_test_id("stDialog")
    try:
        return dlg.count() > 0 and dlg.first.is_visible()
    except Exception:
        return False


def _blocking_overlay_visible(page: Page) -> bool:
    """True when a Baseweb/Streamlit popover layer may intercept clicks."""
    if _popover_panel_visible(page):
        return True
    # Leftover Baseweb portals often block Add/Edit even after the panel text is gone.
    for sel in (
        '[data-baseweb="popover"]',
        '[data-baseweb="menu"]',
        '[data-testid="stPopoverBody"]',
    ):
        loc = page.locator(sel)
        try:
            n = loc.count()
        except Exception:
            continue
        for i in range(min(n, 6)):
            try:
                node = loc.nth(i)
                if not node.is_visible():
                    continue
                # Ignore menus inside an open dialog (parent select, etc.).
                if node.locator("xpath=ancestor::*[@data-testid='stDialog']").count():
                    continue
                return True
            except Exception:
                continue
    return False


def close_popovers(page: Page) -> None:
    """Dismiss filter/sort/Baseweb overlays without Escape-closing st.dialogs."""
    if _dialog_open(page):
        return
    if not (_blocking_overlay_visible(page) or _popover_panel_visible(page)):
        return
    for _ in range(4):
        if not (_blocking_overlay_visible(page) or _popover_panel_visible(page)):
            break
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    _click_list_heading(page)
    page.wait_for_timeout(150)


def _click_list_heading(page: Page) -> None:
    if _dialog_open(page):
        return
    heading = page.locator('[data-testid="stMainBlockContainer"]').get_by_role(
        "heading", level=3
    ).first
    try:
        if heading.count() and heading.is_visible():
            heading.click(force=True, timeout=3_000)
    except Exception:
        try:
            page.mouse.click(24, 120)
        except Exception:
            pass


def _popover_panel_visible(page: Page) -> bool:
    for label in ("Filters", "Sort by"):
        loc = page.get_by_text(label, exact=True)
        if loc.count() == 0:
            continue
        try:
            if loc.first.is_visible():
                return True
        except Exception:
            continue
    return False


def wait_for_rerun(page: Page, ms: int = 2000) -> None:
    page.wait_for_timeout(ms)


def open_filter_popover(page: Page) -> None:
    close_popovers(page)
    page.locator('[data-testid="stPopoverButton"]').first.click()
    page.get_by_text("Filters", exact=True).wait_for()


def open_sort_popover(page: Page) -> None:
    close_popovers(page)
    page.locator('[data-testid="stPopoverButton"]').nth(1).click()
    page.get_by_text("Sort by", exact=True).wait_for()


def apply_filter(page: Page, label: str, value: str) -> None:
    open_filter_popover(page)
    page.get_by_label(label, exact=True).fill(value)
    page.get_by_role("button", name="Apply").click()
    wait_for_rerun(page)
    close_popovers(page)
    wait_for_streamlit_ready(page, min_ms=500)


def clear_filters(page: Page) -> None:
    open_filter_popover(page)
    clear_btn = page.get_by_role("button", name="Clear all", exact=True)
    # Prefer the Filters panel Apply-row button over multiselect chip clear icons.
    panel_clear = page.locator('[data-testid="stPopoverBody"]').get_by_role(
        "button", name="Clear all", exact=True
    )
    if panel_clear.count() > 0:
        clear_btn = panel_clear
    elif clear_btn.count() > 1:
        clear_btn = page.locator(
            'button[data-testid="stBaseButton-secondary"]'
        ).filter(has_text="Clear all")
    if clear_btn.count() > 0:
        try:
            if clear_btn.first.is_visible():
                clear_btn.first.click()
                wait_for_rerun(page, 800)
        except Exception:
            pass
    close_popovers(page)
    wait_for_streamlit_ready(page, min_ms=300)


def apply_sort(page: Page, field_label: str, direction: str) -> None:
    open_sort_popover(page)
    page.get_by_label("Field").click()
    page.get_by_role("option", name=field_label).click()
    page.get_by_text(direction, exact=True).click()
    page.get_by_role("button", name="Apply sort").click()
    wait_for_rerun(page)
    close_popovers(page)
    wait_for_streamlit_ready(page, min_ms=500)


def card_titles(page: Page, selector: str, *, grid_suffix: str = "") -> list[str]:
    if grid_suffix:
        root = page.locator(f'[class*="st-key-card_grid_{grid_suffix}"]')
        if selector == "strong":
            close_popovers(page)
            loc = root.locator('[data-testid="stVerticalBlockBorderWrapper"] strong')
        else:
            loc = root.locator(selector)
    elif selector == "strong":
        close_popovers(page)
        loc = page.locator('[data-testid="stMarkdownContainer"] strong')
    else:
        loc = page.locator(selector)
    return [t.strip() for t in loc.all_inner_texts() if t.strip()]


def record_count_caption(page: Page) -> str:
    return page.locator('[data-testid="stCaptionContainer"]').first.inner_text()
