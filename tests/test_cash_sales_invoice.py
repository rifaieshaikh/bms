"""Tests for cash sales invoice posting."""

import pytest

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.domain.finance.accounting.entities import Account
from vaybooks.bms.domain.finance.accounting.services import ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.domain.shared.india import (
    CGST_OUTPUT_ACCOUNT_NAME,
    IGST_OUTPUT_ACCOUNT_NAME,
    SGST_OUTPUT_ACCOUNT_NAME,
)
from tests.conftest import FakeAccountRepository, FakeCounterRepository, FakeVoucherRepository


def _seed_accounts(repo: FakeAccountRepository) -> dict[str, Account]:
    accounts = {
        "cash": Account(
            id="cash",
            account_name="Cash Drawer",
            account_type=AccountType.ASSET,
            is_store_account=True,
        ),
        "customer": Account(
            id="customer",
            account_name="Customer - Test",
            account_type=AccountType.ASSET,
            linked_customer_id="cust-1",
        ),
        "sales": Account(
            id="sales",
            account_name="Sales",
            account_type=AccountType.REVENUE,
        ),
        "discount": Account(
            id="discount",
            account_name="Discount Allowed",
            account_type=AccountType.EXPENSE,
        ),
        "advance": Account(
            id="advance",
            account_name=ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME,
            account_type=AccountType.LIABILITY,
        ),
    }
    for account in accounts.values():
        repo.save(account)
    return accounts


def _service() -> AccountingAppService:
    return AccountingAppService(
        FakeAccountRepository(),
        FakeVoucherRepository(),
        FakeCounterRepository(),
    )


def test_cash_sales_invoice_full_payment_no_discount():
    service = _service()
    accounts = _seed_accounts(service._account_repo)

    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=0.0,
        amount_received=1000.0,
        store_invoice_number="SI-100",
    )

    assert voucher.voucher_type == VoucherType.SALES_INVOICE
    assert voucher.is_cash_sales_invoice
    assert len(voucher.lines) == 4
    assert voucher.cash_movement_amount == 1000.0
    assert accounts["customer"].current_balance == 0.0
    assert accounts["sales"].current_balance == -1000.0
    assert accounts["cash"].current_balance == 1000.0


def test_cash_sales_invoice_partial_payment_leaves_customer_balance():
    service = _service()
    accounts = _seed_accounts(service._account_repo)

    service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=0.0,
        amount_received=600.0,
        store_invoice_number="SI-101",
    )

    assert accounts["customer"].current_balance == 400.0
    assert accounts["cash"].current_balance == 600.0


def test_cash_sales_invoice_overpay_creates_customer_credit():
    service = _service()
    accounts = _seed_accounts(service._account_repo)

    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=0.0,
        amount_received=1200.0,
        store_invoice_number="SI-101B",
    )

    assert voucher.cash_movement_amount == 1200.0
    # Excess ₹200 stays as customer credit (negative balance).
    assert accounts["customer"].current_balance == -200.0
    assert accounts["cash"].current_balance == 1200.0
    from vaybooks.bms.domain.finance.accounting.sales_parsing import (
        sales_amounts_from_lines,
    )

    amounts = sales_amounts_from_lines(voucher.lines)
    assert amounts["net"] == 1000.0
    assert amounts["collected"] == 1200.0
    assert amounts["outstanding"] == 0.0
    assert amounts["payment_status"] == "paid"


def test_cash_sales_invoice_with_discount():
    service = _service()
    accounts = _seed_accounts(service._account_repo)

    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=100.0,
        amount_received=900.0,
        store_invoice_number="SI-102",
    )

    assert len(voucher.lines) == 6
    assert accounts["customer"].current_balance == 0.0
    assert accounts["discount"].current_balance == 100.0


def test_cash_sales_invoice_zero_payment_leaves_full_customer_balance():
    service = _service()
    accounts = _seed_accounts(service._account_repo)

    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=0.0,
        amount_received=0.0,
        store_invoice_number="SI-104",
    )

    assert len(voucher.lines) == 2
    assert not voucher.is_cash_sales_invoice
    assert accounts["customer"].current_balance == 1000.0
    assert accounts["cash"].current_balance == 0.0


def test_cash_sales_invoice_allows_overpay_with_discount():
    service = _service()
    accounts = _seed_accounts(service._account_repo)

    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=100.0,
        amount_received=950.0,
        store_invoice_number="SI-103",
    )

    # Net due 900; received 950 → ₹50 customer credit.
    assert voucher.cash_movement_amount == 950.0
    assert accounts["customer"].current_balance == -50.0
    assert accounts["cash"].current_balance == 950.0
    assert accounts["discount"].current_balance == 100.0


def test_cash_sales_invoice_with_gst_lines():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    for name in (
        CGST_OUTPUT_ACCOUNT_NAME,
        SGST_OUTPUT_ACCOUNT_NAME,
        IGST_OUTPUT_ACCOUNT_NAME,
    ):
        service._account_repo.save(
            Account(account_name=name, account_type=AccountType.LIABILITY)
        )

    sales_lines = [
        {
            "product_id": "p1",
            "description": "Item",
            "qty": 1,
            "rate": 1000,
            "taxable_amount": 1000.0,
            "cgst_amount": 90.0,
            "sgst_amount": 90.0,
            "igst_amount": 0.0,
            "utgst_amount": 0.0,
            "line_total": 1180.0,
        }
    ]

    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1180.0,
        discount_amount=0.0,
        amount_received=1180.0,
        store_invoice_number="SI-GST",
        sales_lines=sales_lines,
    )

    sales_credit = next(
        line for line in voucher.lines if line.description == "Sales invoice"
    )
    assert sales_credit.credit_amount == 1000.0
    customer_debit = voucher.lines[0]
    assert customer_debit.debit_amount == 1180.0
    assert accounts["sales"].current_balance == -1000.0

    from vaybooks.bms.domain.finance.accounting.sales_parsing import (
        sales_amounts_from_lines,
    )

    amounts = sales_amounts_from_lines(voucher.lines)
    assert amounts["taxable"] == 1000.0
    assert amounts["tax"] == 180.0
    assert amounts["gross"] == 1180.0
    assert amounts["net"] == 1180.0
    assert amounts["outstanding"] == 0.0
    assert amounts["payment_status"] == "paid"


def test_gst_invoice_outstanding_uses_grand_total():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    for name in (
        CGST_OUTPUT_ACCOUNT_NAME,
        SGST_OUTPUT_ACCOUNT_NAME,
        IGST_OUTPUT_ACCOUNT_NAME,
    ):
        service._account_repo.save(
            Account(account_name=name, account_type=AccountType.LIABILITY)
        )

    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1180.0,
        discount_amount=0.0,
        amount_received=0.0,
        store_invoice_number="SI-GST-OPEN",
        sales_lines=[
            {
                "product_id": "p1",
                "description": "Item",
                "qty": 1,
                "rate": 1000,
                "taxable_amount": 1000.0,
                "cgst_amount": 90.0,
                "sgst_amount": 90.0,
                "igst_amount": 0.0,
                "utgst_amount": 0.0,
                "line_total": 1180.0,
            }
        ],
    )

    from vaybooks.bms.domain.finance.accounting.sales_parsing import (
        sales_amounts_from_lines,
    )

    amounts = sales_amounts_from_lines(voucher.lines)
    assert amounts["gross"] == 1180.0
    assert amounts["outstanding"] == 1180.0
    assert amounts["payment_status"] == "unpaid"

    row = service.enrich_sales_invoice_row(voucher)
    assert row["outstanding"] == 1180.0
    assert row["payment_status"] == "unpaid"
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        4000.0,
        "General advance",
    )

    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=10000.0,
        discount_amount=0.0,
        amount_received=6000.0,
        store_invoice_number="SI-ADV",
        advance_applied=4000.0,
    )

    advance_line = next(
        line
        for line in voucher.lines
        if line.description == "Advance applied" and line.debit_amount > 0
    )
    assert advance_line.debit_amount == 4000.0
    assert accounts["advance"].current_balance == 0.0
    assert accounts["customer"].current_balance == 0.0
    assert (
        service.get_customer_unapplied_advance(
            accounts["customer"].id, general_only=True
        )
        == 0.0
    )

    from vaybooks.bms.domain.finance.accounting.sales_parsing import (
        sales_amounts_from_lines,
    )

    amounts = sales_amounts_from_lines(voucher.lines)
    assert amounts["collected"] == 10000.0
    assert amounts["outstanding"] == 0.0
    assert amounts["payment_status"] == "paid"


def test_cash_sales_invoice_rejects_order_tagged_advance():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        5000.0,
        "Order advance",
        reference_order_id="order-only",
    )

    with pytest.raises(ValueError, match="available customer advance"):
        service.create_cash_sales_invoice(
            accounts["customer"].id,
            accounts["cash"].id,
            gross_amount=3000.0,
            discount_amount=0.0,
            amount_received=0.0,
            store_invoice_number="SI-ORD-ADV",
            advance_applied=1000.0,
        )


def test_cash_sales_invoice_rejects_advance_above_available():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        500.0,
        "General",
    )

    with pytest.raises(ValueError, match="available customer advance"):
        service.create_cash_sales_invoice(
            accounts["customer"].id,
            accounts["cash"].id,
            gross_amount=2000.0,
            discount_amount=0.0,
            amount_received=0.0,
            store_invoice_number="SI-OVER-ADV",
            advance_applied=1000.0,
        )
