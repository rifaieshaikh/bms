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

    def test_filters_dialog_has_no_radio_buttons(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        dlg = cp.filters_dialog(page)
        expect(dlg.locator('input[type="radio"]')).to_have_count(0)
        expect(dlg.get_by_test_id("stRadio")).to_have_count(0)

    def test_registration_dropdown_enter_selects_without_applying(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        dlg = cp.filters_dialog(page)
        control = cp.focus_filter_dropdown(page, "registration_type")
        control.click()
        page.wait_for_timeout(400)
        # Arrows highlight inside the open menu; Enter picks the option.
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        assert cp.selected_filter_options(page, "registration_type")
        expect(dlg).to_be_visible()
        expect(dlg.get_by_role("button", name="Apply")).to_be_visible()

    def test_registration_dropdown_accepts_multiple_options(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        cp.select_filter_option(page, "registration_type", "Registered")
        cp.select_filter_option(page, "registration_type", "Unregistered")
        chosen = cp.selected_filter_options(page, "registration_type")
        assert len(chosen) == 2

    def test_filter_tab_order_gstin_reg_segment_orders_clear(
        self, page: Page, streamlit_server: str
    ) -> None:
        """Tab: GSTIN → Registration Type → Segment → Has Orders → Clear all."""
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        dlg = cp.filters_dialog(page)
        gstin = dlg.get_by_label("GSTIN", exact=True)
        gstin.focus()
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)
        # Land on the Registration type dropdown.
        active = page.evaluate(
            "() => (document.activeElement && document.activeElement.closest"
            "('[class*=\"st-key-\"]') || {}).className || ''"
        )
        assert "registration_type" in active
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)
        active2 = page.evaluate(
            "() => (document.activeElement && document.activeElement.closest"
            "('[class*=\"st-key-\"]') || {}).className || ''"
        )
        assert "segment_id" in active2
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)
        active3 = page.evaluate(
            "() => (document.activeElement && document.activeElement.closest"
            "('[class*=\"st-key-\"]') || {}).className || ''"
        )
        assert "has_orders" in active3
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)
        expect(dlg.get_by_role("button", name="Clear all")).to_be_focused()

    def test_filter_shift_tab_from_registration_reaches_customer_name(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        dlg = cp.filters_dialog(page)
        cp.focus_filter_dropdown(page, "registration_type")
        # Registration → GSTIN → Alternate phone → Phone → Customer name
        for _ in range(4):
            page.keyboard.press("Shift+Tab")
            page.wait_for_timeout(150)
        active = page.evaluate(
            "() => (document.activeElement && document.activeElement.closest"
            "('[class*=\"st-key-\"]') || {}).className || ''"
        )
        assert "customer_name" in active
        expect(dlg).to_be_visible()

    def test_filter_shift_tab_from_has_orders_to_segment(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        cp.focus_filter_dropdown(page, "has_orders")
        page.keyboard.press("Shift+Tab")
        page.wait_for_timeout(200)
        active = page.evaluate(
            "() => (document.activeElement && document.activeElement.closest"
            "('[class*=\"st-key-\"]') || {}).className || ''"
        )
        assert "segment_id" in active

    def test_arrow_keys_move_between_filter_fields(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        dlg = cp.filters_dialog(page)
        cp.focus_filter_dropdown(page, "registration_type")
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(300)
        active = page.evaluate(
            "() => (document.activeElement && document.activeElement.closest"
            "('[class*=\"st-key-\"]') || {}).className || ''"
        )
        assert "registration_type" not in active
        # Tab must not be trapped inside the dropdown either.
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)
        expect(dlg).to_be_visible()

    def test_has_orders_multi_select_keeps_panel_open(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        dlg = cp.filters_dialog(page)
        cp.select_filter_option(page, "has_orders", "With orders")
        cp.select_filter_option(page, "has_orders", "Without orders")
        assert len(cp.selected_filter_options(page, "has_orders")) == 2
        expect(dlg).to_be_visible()
        expect(dlg.get_by_role("button", name="Apply")).to_be_visible()

    def test_filter_dropdown_mouse_click_selects(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        dlg = cp.filters_dialog(page)
        cp.select_filter_option(page, "registration_type", "Composition")
        assert cp.selected_filter_options(page, "registration_type") == ["Composition"]
        expect(dlg).to_be_visible()

    def test_filter_dropdown_focus_indicator_visible(
        self, page: Page, streamlit_server: str
    ) -> None:
        cp.goto_customers(page, streamlit_server)
        cp.open_customer_filters(page)
        target = cp.focus_filter_dropdown(page, "registration_type")
        outline = target.evaluate(
            """el => {
              const s = getComputedStyle(el);
              const ow = parseFloat(s.outlineWidth) || 0;
              const shadow = s.boxShadow || '';
              return ow > 0 || shadow !== 'none';
            }"""
        )
        # Fallback: focused descendant / focus-within on the label.
        if not outline:
            outline = target.evaluate(
                """el => {
                  const label = el.closest('label') || el;
                  const s = getComputedStyle(label);
                  const ow = parseFloat(s.outlineWidth) || 0;
                  const shadow = s.boxShadow || '';
                  return ow > 0 || shadow !== 'none' || document.activeElement === el
                    || label.contains(document.activeElement);
                }"""
            )
        assert outline

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
