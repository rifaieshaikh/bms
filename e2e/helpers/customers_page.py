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
    open_customer_filters(page)
    select_filter_option(page, "registration_type", reg_type)
    page.get_by_role("button", name="Apply").click()
    wait_for_rerun(page)


def open_customer_filters(page: Page) -> None:
    """Open the Customers Filters dialog (st.dialog, not popover)."""
    close_popovers(page)
    btn = page.locator('[class*="st-key-customers_filters_open_btn"] button')
    if btn.count() == 0:
        open_filter_popover(page)
    else:
        btn.first.click()
    page.get_by_text("Filters", exact=True).wait_for()
    expect(page.get_by_test_id("stDialog")).to_be_visible()


def filters_dialog(page: Page):
    return page.get_by_test_id("stDialog")


def filter_widget(page: Page, field_key: str):
    """Container of a Filters widget, addressed by its schema field key."""
    return filters_dialog(page).locator(f'[class*="st-key-customers_flt_{field_key}"]')


def focus_filter_dropdown(page: Page, field_key: str):
    """Focus the dropdown input of a Filters field and return the control."""
    root = filter_widget(page, field_key)
    expect(root.first).to_be_visible()
    control = root.first.locator('[data-baseweb="select"] input, input').first
    control.focus()
    return control


def select_filter_option(page: Page, field_key: str, option: str) -> None:
    """Open a Filters dropdown and pick ``option`` by its visible label."""
    control = focus_filter_dropdown(page, field_key)
    control.click()
    page.wait_for_timeout(300)
    option_loc = page.get_by_role("option", name=option, exact=True)
    if option_loc.count() == 0:
        option_loc = page.locator('[data-baseweb="popover"]').get_by_text(
            option, exact=True
        )
    option_loc.first.click()
    page.wait_for_timeout(250)


def selected_filter_options(page: Page, field_key: str) -> list[str]:
    """Chosen option labels of a multi-select Filters dropdown."""
    root = filter_widget(page, field_key).first
    tags = root.locator('[data-baseweb="tag"]')
    return [t.strip() for t in tags.all_inner_texts() if t.strip()]


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
