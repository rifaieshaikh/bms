"""Customer E2E: list/filter/sort first, then create/edit scenarios."""

from playwright.sync_api import Page, expect

from e2e.helpers import customers_page as cp
from e2e.helpers.list_page import clear_filters
from e2e.helpers.party_form import (
    PartyFull,
    PartyMinimal,
    PartyRegistered,
    fill_customer_full,
    fill_customer_minimal,
    fill_customer_registered,
    dialog,
    set_registration_type,
)
from e2e.helpers.unique import unique_gstin_pan, unique_name, unique_phone


class TestCustomerListFilterSort:
    """Section 1 — list, filter, and sort (run before create tests)."""

    def test_list_page_loads(self, page: Page, streamlit_server: str) -> None:
        cp.goto_customers(page, streamlit_server)
        assert "Customers" in page.content()

    def test_filter_partial_name_returns_empty(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.filter_by_name(page, "NoSuchCustomerXYZ")
        cp.assert_empty_or_zero(page)

    def test_filter_clear_restores_list(self, page: Page, streamlit_server: str) -> None:
        cp.goto_customers(page, streamlit_server)
        before = cp.customer_card_names(page)
        cp.filter_by_name(page, "NoSuchCustomerXYZ")
        clear_filters(page)
        after = cp.customer_card_names(page)
        assert len(after) >= len(before) or len(before) == 0

    def test_sort_by_name_changes_order(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        before = cp.customer_card_names(page)
        if len(before) < 2:
            return
        cp.sort_by_name(page, "Ascending")
        after = cp.customer_card_names(page)
        assert before != after


class TestCustomerCreate:
    """Section 2 — create with minimal, full, and registered profiles."""

    def test_minimal_create_then_filter_by_phone(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("Minimal")
        phone = unique_phone()
        cp.open_add_customer(page, streamlit_server)
        fill_customer_minimal(page, PartyMinimal(name=name, phone=phone))
        cp.submit_create(page)
        cp.goto_customers(page, streamlit_server)
        clear_filters(page)
        cp.filter_by_phone(page, phone)
        cp.assert_card_visible(page, name)

    def test_full_unregistered_create_then_filter_by_name(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("Full")
        phone = unique_phone()
        alt = unique_phone("8")
        data = PartyFull(
            name=name,
            phone=phone,
            alt_phone=alt,
            email="full.e2e@example.com",
            notes="Full profile E2E",
        )
        cp.open_add_customer(page, streamlit_server)
        fill_customer_full(page, data)
        cp.submit_create(page)
        cp.goto_customers(page, streamlit_server)
        clear_filters(page)
        cp.filter_by_name(page, name)
        cp.assert_card_visible(page, name)

    def test_registered_with_gstin_then_filter(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("Registered")
        phone = unique_phone()
        gstin, pan = unique_gstin_pan()
        data = PartyRegistered(name=name, phone=phone, gstin=gstin, pan=pan)
        cp.open_add_customer(page, streamlit_server)
        fill_customer_registered(page, data)
        cp.submit_create(page)
        cp.goto_customers(page, streamlit_server)
        clear_filters(page)
        cp.filter_by_gstin(page, gstin)
        cp.assert_card_visible(page, name)
        clear_filters(page)
        cp.filter_by_registration(page, "Registered")
        cp.assert_card_visible(page, name)


class TestCustomerValidation:
    """Section 3 — negative create scenarios."""

    def test_registered_without_gstin_shows_error(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.open_add_customer(page, streamlit_server)
        fill_customer_minimal(
            page, PartyMinimal(name=unique_name("NoGST"), phone=unique_phone())
        )
        set_registration_type(page, "Registered")
        cp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("GSTIN is required")).to_be_visible()

    def test_invalid_phone_shows_error(self, page: Page, streamlit_server: str) -> None:
        cp.open_add_customer(page, streamlit_server)
        fill_customer_minimal(
            page, PartyMinimal(name=unique_name("BadPhone"), phone="12345")
        )
        cp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("valid 10-digit")).to_be_visible()

    def test_invalid_pincode_when_provided(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.open_add_customer(page, streamlit_server)
        fill_customer_minimal(
            page, PartyMinimal(name=unique_name("BadPin"), phone=unique_phone())
        )
        dialog(page).get_by_role("button", name="Address", exact=True).click()
        page.wait_for_timeout(300)
        dialog(page).get_by_label("PIN Code").fill("40001")
        dialog(page).get_by_label("PIN Code").press("Tab")
        page.wait_for_timeout(250)
        cp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("PIN code must be exactly 6 digits")).to_be_visible()

    def test_duplicate_phone_shows_warning(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("DupSource")
        phone = unique_phone()
        cp.open_add_customer(page, streamlit_server)
        fill_customer_minimal(page, PartyMinimal(name=name, phone=phone))
        cp.submit_create(page)
        cp.open_add_customer(page, streamlit_server)
        fill_customer_minimal(
            page, PartyMinimal(name=unique_name("DupTarget"), phone=phone)
        )
        cp.submit_create_allow_dialog(page)
        expect(dialog(page)).to_be_visible()
        expect(dialog(page).get_by_text("already exists")).to_be_visible()
        expect(
            dialog(page).get_by_role("button", name="Open existing customer")
        ).to_be_visible()

    def test_missing_name_blocked(self, page: Page, streamlit_server: str) -> None:
        cp.open_add_customer(page, streamlit_server)
        dialog(page).get_by_label("Phone Number *").fill(unique_phone())
        cp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("Name is required")).to_be_visible()

    def test_missing_phone_blocked(self, page: Page, streamlit_server: str) -> None:
        cp.open_add_customer(page, streamlit_server)
        dialog(page).get_by_label("Customer Name *").fill(unique_name("NoPhone"))
        cp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("Phone number is required")).to_be_visible()
