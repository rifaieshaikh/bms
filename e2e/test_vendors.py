"""Vendor E2E: list/filter/sort first, then create/edit scenarios."""

from playwright.sync_api import Page, expect

from e2e.helpers import vendors_page as vp
from e2e.helpers.list_page import clear_filters, close_popovers, open_sort_popover, wait_for_rerun
from e2e.helpers.party_form import (
    PartyFull,
    PartyMinimal,
    PartyRegistered,
    VALID_IFSC,
    fill_vendor_banking,
    fill_vendor_full,
    fill_vendor_minimal,
    fill_vendor_registered,
    dialog,
    set_registration_type,
)
from e2e.helpers.unique import unique_gstin_pan, unique_name, unique_phone


class TestVendorListFilterSort:
    """Section 1 — list, filter, and sort."""

    def test_list_page_loads(self, page: Page, streamlit_server: str) -> None:
        vp.goto_vendors(page, streamlit_server)
        assert "Vendors" in page.content()

    def test_filter_partial_name_returns_empty(
        self, page: Page, streamlit_server: str
    ) -> None:
        vp.goto_vendors(page, streamlit_server)
        vp.filter_by_name(page, "NoSuchVendorXYZ")
        vp.assert_empty_or_zero(page)

    def test_filter_clear_restores_list(self, page: Page, streamlit_server: str) -> None:
        vp.goto_vendors(page, streamlit_server)
        before = vp.vendor_card_names(page)
        vp.filter_by_name(page, "NoSuchVendorXYZ")
        clear_filters(page)
        after = vp.vendor_card_names(page)
        assert len(after) >= len(before) or len(before) == 0

    def test_sort_by_name_changes_order(self, page: Page, streamlit_server: str) -> None:
        vp.goto_vendors(page, streamlit_server)
        before = vp.vendor_card_names(page)
        if len(before) < 2:
            return
        vp.sort_by_name(page, "Ascending")
        after = vp.vendor_card_names(page)
        assert before != after

    def test_sort_without_apply_keeps_order(
        self, page: Page, streamlit_server: str
    ) -> None:
        vp.goto_vendors(page, streamlit_server)
        before = vp.vendor_card_names(page)
        open_sort_popover(page)
        page.keyboard.press("Escape")
        close_popovers(page)
        wait_for_rerun(page, 500)
        after = vp.vendor_card_names(page)
        assert before == after


class TestVendorCreate:
    """Section 2 — create scenarios."""

    def test_minimal_create_then_filter_by_phone(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("VMinimal")
        phone = unique_phone()
        vp.open_add_vendor(page, streamlit_server)
        fill_vendor_minimal(page, PartyMinimal(name=name, phone=phone))
        vp.submit_create(page)
        vp.goto_vendors(page, streamlit_server)
        clear_filters(page)
        vp.filter_by_phone(page, phone)
        vp.assert_vendor_visible(page, name)

    def test_full_unregistered_create_then_filter(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("VFull")
        phone = unique_phone()
        data = PartyFull(
            name=name,
            phone=phone,
            alt_phone=unique_phone("8"),
            notes="Vendor full E2E",
        )
        vp.open_add_vendor(page, streamlit_server)
        fill_vendor_full(page, data)
        vp.submit_create(page)
        vp.goto_vendors(page, streamlit_server)
        clear_filters(page)
        vp.filter_by_name(page, name)
        vp.assert_vendor_visible(page, name)

    def test_registered_with_gstin_and_banking(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("VRegistered")
        phone = unique_phone()
        gstin, pan = unique_gstin_pan()
        data = PartyRegistered(name=name, phone=phone, gstin=gstin, pan=pan)
        vp.open_add_vendor(page, streamlit_server)
        fill_vendor_registered(page, data)
        fill_vendor_banking(page)
        vp.submit_create(page)
        vp.goto_vendors(page, streamlit_server)
        clear_filters(page)
        vp.filter_by_phone(page, phone)
        vp.assert_vendor_visible(page, name)


class TestVendorValidation:
    """Section 3 — negative create scenarios."""

    def test_registered_without_gstin_shows_error(
        self, page: Page, streamlit_server: str
    ) -> None:
        vp.open_add_vendor(page, streamlit_server)
        fill_vendor_minimal(
            page, PartyMinimal(name=unique_name("VNoGST"), phone=unique_phone())
        )
        set_registration_type(page, "Registered")
        vp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("GSTIN is required")).to_be_visible()

    def test_invalid_phone_shows_error(self, page: Page, streamlit_server: str) -> None:
        vp.open_add_vendor(page, streamlit_server)
        fill_vendor_minimal(
            page, PartyMinimal(name=unique_name("VBadPhone"), phone="12345")
        )
        vp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("valid 10-digit")).to_be_visible()

    def test_banking_account_without_ifsc_shows_error(
        self, page: Page, streamlit_server: str
    ) -> None:
        vp.open_add_vendor(page, streamlit_server)
        fill_vendor_minimal(
            page, PartyMinimal(name=unique_name("VBank"), phone=unique_phone())
        )
        dialog(page).get_by_label("Account Number").fill("123456789012")
        dialog(page).get_by_label("Account Number").blur()
        page.wait_for_timeout(200)
        vp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("IFSC is required")).to_be_visible()

    def test_banking_ifsc_without_account_shows_error(
        self, page: Page, streamlit_server: str
    ) -> None:
        vp.open_add_vendor(page, streamlit_server)
        fill_vendor_minimal(
            page, PartyMinimal(name=unique_name("VIfsc"), phone=unique_phone())
        )
        dialog(page).get_by_label("IFSC").fill(VALID_IFSC)
        dialog(page).get_by_label("IFSC").blur()
        page.wait_for_timeout(200)
        vp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("Bank account number is required")).to_be_visible()

    def test_duplicate_phone_shows_warning(
        self, page: Page, streamlit_server: str
    ) -> None:
        name = unique_name("VDupSource")
        phone = unique_phone()
        vp.open_add_vendor(page, streamlit_server)
        fill_vendor_minimal(page, PartyMinimal(name=name, phone=phone))
        vp.submit_create(page)
        vp.open_add_vendor(page, streamlit_server)
        fill_vendor_minimal(
            page, PartyMinimal(name=unique_name("VDupTarget"), phone=phone)
        )
        vp.submit_create_allow_dialog(page)
        expect(dialog(page)).to_be_visible()
        expect(dialog(page).get_by_text("already exists")).to_be_visible()
        expect(
            dialog(page).get_by_role("button", name="Open existing vendor")
        ).to_be_visible()

    def test_missing_name_blocked(self, page: Page, streamlit_server: str) -> None:
        vp.open_add_vendor(page, streamlit_server)
        dialog(page).get_by_label("Phone Number *").fill(unique_phone())
        vp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("Name is required")).to_be_visible()

    def test_missing_phone_blocked(self, page: Page, streamlit_server: str) -> None:
        vp.open_add_vendor(page, streamlit_server)
        dialog(page).get_by_label("Vendor Name *").fill(unique_name("VNoPhone"))
        vp.submit_create_allow_dialog(page)
        expect(dialog(page).get_by_text("Phone number is required")).to_be_visible()
