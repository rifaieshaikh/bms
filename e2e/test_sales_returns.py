"""Sales Returns E2E — SAL-RET Wave 1 (Pending Approval workflow)."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from e2e.helpers import sales_returns_page as rp
from e2e.helpers.sales_seed import (
    create_cash_sale_fixture,
    create_pending_return_for_fixture,
    product_qty,
    return_has_voucher,
)


class TestSalesReturnsWave1:
    def test_sal_ret_001_create_minimum_return(
        self, page: Page, streamlit_server: str
    ) -> None:
        """SAL-RET-001 | sales-ret-001 — create minimum return as Pending Approval."""
        fixture = create_cash_sale_fixture()
        return_number = rp.create_pending_return_from_invoice(
            page,
            streamlit_server,
            customer_name=fixture.customer_name,
            phone=fixture.phone,
            store_invoice_number=fixture.store_invoice_number,
            reason="Damaged on arrival",
        )
        assert return_number.startswith("SR-")
        rp.open_view_for_return(page, return_number, base_url=streamlit_server)
        rp.assert_return_status(
            page, "Pending Approval", return_number=return_number
        )

    def test_sal_ret_002_block_save_when_mandatory_missing(
        self, page: Page, streamlit_server: str
    ) -> None:
        """SAL-RET-002 | sales-ret-002 — block submit when reason/lines missing."""
        fixture = create_cash_sale_fixture()
        rp.open_record_return(page, streamlit_server)
        rp.select_customer(page, fixture.customer_name, fixture.phone)
        reserved = rp.read_return_number(page)
        # Leave reason empty and no invoice lines selected.
        rp.submit_for_approval_allow_error(page)
        # Dialog should remain (validation) and reserved number must not become a card.
        expect(rp.dialog(page)).to_be_visible()
        rp.goto_returns(page, streamlit_server)
        rp.filter_by_return_number(page, reserved)
        rp.assert_return_card_absent(page, reserved)

    def test_sal_ret_003_unique_auto_return_numbers(
        self, page: Page, streamlit_server: str
    ) -> None:
        """SAL-RET-003 | sales-ret-003 — unique auto return numbers."""
        first = create_cash_sale_fixture()
        second = create_cash_sale_fixture()
        n1 = rp.create_pending_return_from_invoice(
            page,
            streamlit_server,
            customer_name=first.customer_name,
            phone=first.phone,
            store_invoice_number=first.store_invoice_number,
            reason="First unique return",
        )
        n2 = rp.create_pending_return_from_invoice(
            page,
            streamlit_server,
            customer_name=second.customer_name,
            phone=second.phone,
            store_invoice_number=second.store_invoice_number,
            reason="Second unique return",
        )
        assert n1 != n2
        assert n1.startswith("SR-") and n2.startswith("SR-")

    def test_sal_ret_007_list_filter_by_status_and_number(
        self, page: Page, streamlit_server: str
    ) -> None:
        """SAL-RET-007 | sales-ret-007 — list filter including Status."""
        fixture = create_cash_sale_fixture()
        return_number = rp.create_pending_return_from_invoice(
            page,
            streamlit_server,
            customer_name=fixture.customer_name,
            phone=fixture.phone,
            store_invoice_number=fixture.store_invoice_number,
            reason="Filter status return",
        )
        rp.goto_returns(page, streamlit_server)
        rp.filter_by_status(page, "Pending Approval")
        rp.filter_by_return_number(page, return_number)
        rp.assert_return_card_visible(page, return_number)
        rp.goto_returns(page, streamlit_server)
        rp.filter_by_return_number(page, return_number)
        rp.assert_return_card_visible(page, return_number)
        rp.goto_returns(page, streamlit_server)
        expect(page.get_by_role("heading", name="Sales Returns", level=3)).to_be_visible()

    def test_happy_workflow_approve_to_close(
        self, page: Page, streamlit_server: str
    ) -> None:
        """Approve → Goods Received (restock) → Process Refund → Close."""
        fixture = create_cash_sale_fixture(qty=1.0)
        qty_before = product_qty(fixture.product_id)
        return_number = create_pending_return_for_fixture(
            fixture, reason="Full happy-path return"
        )
        rp.open_view_for_return(page, return_number, base_url=streamlit_server)

        rp.click_detail_action(page, "Approve")
        rp.assert_return_status(page, "Approved", return_number=return_number)

        rp.click_detail_action(page, "Mark Goods Received")
        rp.assert_return_status(page, "Goods Received", return_number=return_number)
        assert product_qty(fixture.product_id) == qty_before + 1.0

        rp.click_detail_action(page, "Process Refund")
        rp.assert_return_status(
            page, "Refund Processed", return_number=return_number
        )
        assert return_has_voucher(return_number)

        rp.click_detail_action(page, "Close")
        rp.assert_return_status(page, "Closed", return_number=return_number)
        # No further workflow actions; Edit not offered when Closed
        expect(page.get_by_role("button", name="Approve")).to_have_count(0)
        expect(page.get_by_role("button", name="Close")).to_have_count(0)

    def test_reject_pending_no_stock_change(
        self, page: Page, streamlit_server: str
    ) -> None:
        """Reject pending return — stock unchanged; terminal."""
        fixture = create_cash_sale_fixture(qty=1.0)
        qty_before = product_qty(fixture.product_id)
        return_number = create_pending_return_for_fixture(
            fixture, reason="Reject this return"
        )
        rp.open_view_for_return(page, return_number, base_url=streamlit_server)
        rp.click_detail_action(page, "Reject")
        rp.assert_return_status(page, "Rejected", return_number=return_number)
        assert product_qty(fixture.product_id) == qty_before
        expect(page.get_by_role("button", name="Approve")).to_have_count(0)
        expect(page.get_by_role("button", name="Edit")).to_have_count(0)

    def test_invoice_hidden_until_reject(
        self, page: Page, streamlit_server: str
    ) -> None:
        """Invoice unavailable after non-rejected return; available again after reject."""
        fixture = create_cash_sale_fixture(qty=1.0)
        return_number = create_pending_return_for_fixture(
            fixture, reason="Hide invoice return"
        )

        rp.open_record_return(page, streamlit_server)
        rp.select_customer(page, fixture.customer_name, fixture.phone)
        assert not rp.invoice_option_visible_in_dialog(
            page, fixture.store_invoice_number
        )
        rp.goto_returns(page, streamlit_server)
        rp.open_view_for_return(page, return_number, base_url=streamlit_server)
        rp.click_detail_action(page, "Reject")
        rp.assert_return_status(page, "Rejected", return_number=return_number)

        rp.open_record_return(page, streamlit_server)
        rp.select_customer(page, fixture.customer_name, fixture.phone)
        assert rp.invoice_option_visible_in_dialog(
            page, fixture.store_invoice_number
        )
