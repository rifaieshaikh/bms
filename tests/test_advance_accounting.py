"""Tests for Advance From Customers receipt, invoice, refund, and order close posting."""

import pytest

from vaybooks.bms.application.finance.accounting.service import (
    ADVANCE_RELEASE_DESCRIPTION_PREFIX,
    AccountingAppService,
)
from vaybooks.bms.domain.finance.accounting.entities import Account
from vaybooks.bms.domain.finance.accounting.services import ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from tests.conftest import FakeAccountRepository, FakeCounterRepository, FakeVoucherRepository


def _seed_accounts(repo: FakeAccountRepository) -> dict[str, Account]:
    accounts = {
        "cash": Account(
            id="cash",
            account_name="Cash Drawer",
            account_type=AccountType.ASSET,
            is_store_account=True,
        ),
        "advance": Account(
            id="advance",
            account_name=ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME,
            account_type=AccountType.LIABILITY,
        ),
        "customer": Account(
            id="customer",
            account_name="Customer - Test",
            account_type=AccountType.ASSET,
            linked_customer_id="cust-1",
        ),
        "customization": Account(
            id="customization",
            account_name="Customization",
            account_type=AccountType.REVENUE,
        ),
        "discount": Account(
            id="discount",
            account_name="Discount Allowed",
            account_type=AccountType.EXPENSE,
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


def test_advance_receipt_uses_advance_voucher_type():
    service = _service()
    accounts = _seed_accounts(service._account_repo)

    voucher = service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        5000.0,
        "Advance for CO-001",
        reference_order_id="order-1",
    )

    assert voucher.voucher_type == VoucherType.ADVANCE
    assert len(voucher.lines) == 4
    assert voucher.lines[-1].account_id == accounts["advance"].id
    assert accounts["advance"].current_balance == -5000.0
    assert accounts["customer"].current_balance == 0.0
    assert accounts["cash"].current_balance == 5000.0
    assert voucher.cash_movement_amount == 5000.0


def test_customer_payment_uses_receipt_voucher_type_two_lines():
    service = _service()
    accounts = _seed_accounts(service._account_repo)

    voucher = service.create_customer_payment(
        accounts["cash"].id,
        accounts["customer"].id,
        4000.0,
        "Payment for CO-001",
        reference_order_id="order-1",
    )

    assert voucher.voucher_type == VoucherType.RECEIPT
    assert len(voucher.lines) == 2
    assert voucher.lines[0].debit_amount == 4000.0
    assert voucher.lines[1].credit_amount == 4000.0
    assert accounts["customer"].current_balance == -4000.0
    assert service.get_order_unapplied_advance("order-1") == 0.0
    assert service.get_order_customer_payments("order-1") == 4000.0


def test_unapplied_advance_ignores_customer_payments():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        10000.0,
        "Advance",
        reference_order_id="order-1",
    )
    service.create_customer_payment(
        accounts["cash"].id,
        accounts["customer"].id,
        4000.0,
        "Payment",
        reference_order_id="order-1",
    )

    assert service.get_order_unapplied_advance("order-1") == 10000.0
    assert service.get_order_customer_payments("order-1") == 4000.0
    assert service.get_order_total_received("order-1") == 14000.0


def test_invoice_applies_advance_up_to_net_amount():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        5000.0,
        "Advance for CO-001",
        reference_order_id="order-1",
    )

    voucher = service.create_sales_invoice(
        accounts["customer"].id,
        accounts["customization"].id,
        4000.0,
        "Invoice INV-001",
        reference_order_id="order-1",
        reference_invoice_id="inv-1",
        advance_applied=4000.0,
        voucher_type=VoucherType.CUSTOMIZATION_INVOICE,
    )

    advance_line = next(
        line for line in voucher.lines if line.account_id == accounts["advance"].id
    )
    assert advance_line.debit_amount == 4000.0
    assert accounts["advance"].current_balance == -1000.0
    assert accounts["customer"].current_balance == 0.0
    assert service.get_order_unapplied_advance("order-1") == 1000.0


def test_invoice_splits_advance_and_customer_balance():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        1000.0,
        "Advance for CO-002",
        reference_order_id="order-2",
    )

    service.create_sales_invoice(
        accounts["customer"].id,
        accounts["customization"].id,
        5000.0,
        "Invoice INV-002",
        reference_order_id="order-2",
        reference_invoice_id="inv-2",
        advance_applied=1000.0,
        voucher_type=VoucherType.CUSTOMIZATION_INVOICE,
    )

    assert accounts["customer"].current_balance == 4000.0
    assert service.get_order_unapplied_advance("order-2") == 0.0


def test_full_scenario_advance_invoice_payment():
    """₹10k advance, ₹15k invoice / ₹1k discount → ₹4k Dr; ₹4k payment clears."""
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        10000.0,
        "Advance",
        reference_order_id="order-csv",
    )
    service.create_sales_invoice(
        accounts["customer"].id,
        accounts["customization"].id,
        15000.0,
        "Invoice",
        reference_order_id="order-csv",
        reference_invoice_id="inv-csv",
        advance_applied=10000.0,
        discount_amount=1000.0,
        discount_account_id=accounts["discount"].id,
        voucher_type=VoucherType.CUSTOMIZATION_INVOICE,
    )

    assert accounts["customer"].current_balance == 4000.0
    assert service.get_order_unapplied_advance("order-csv") == 0.0

    service.create_customer_payment(
        accounts["cash"].id,
        accounts["customer"].id,
        4000.0,
        "Balance payment",
        reference_order_id="order-csv",
    )
    assert accounts["customer"].current_balance == 0.0
    assert service.get_order_total_received("order-csv") == 14000.0


def test_advance_refund_routes_through_advance_pool():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        5000.0,
        "Advance",
        reference_order_id="order-3",
    )

    refund = service.create_advance_refund(
        accounts["customer"].id,
        accounts["cash"].id,
        2000.0,
        "Advance refund",
        reference_order_id="order-3",
    )

    assert refund.is_advance_refund
    assert len(refund.lines) == 4
    assert refund.cash_movement_amount == 2000.0
    assert accounts["cash"].current_balance == 3000.0
    assert service.get_order_unapplied_advance("order-3") == 3000.0


def test_payment_refund_caps_to_customer_payments():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_customer_payment(
        accounts["cash"].id,
        accounts["customer"].id,
        3000.0,
        "Payment",
        reference_order_id="order-4",
    )

    refund = service.create_customer_payment_refund(
        accounts["customer"].id,
        accounts["cash"].id,
        1000.0,
        "Payment refund",
        reference_order_id="order-4",
    )

    assert not refund.is_advance_refund
    assert len(refund.lines) == 2
    assert refund.cash_movement_amount == 1000.0
    assert service.get_order_refundable_customer_payments("order-4") == 2000.0

    with pytest.raises(ValueError, match="refundable customer payments"):
        service.create_customer_payment_refund(
            accounts["customer"].id,
            accounts["cash"].id,
            5000.0,
            "Too much",
            reference_order_id="order-4",
        )


def test_release_advance_journal_on_order_close():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        5000.0,
        "Advance",
        reference_order_id="order-close",
    )

    journal = service.release_order_advance(
        "order-close", accounts["customer"].id, "CO-CLOSE"
    )

    assert journal is not None
    assert journal.voucher_type == VoucherType.JOURNAL
    assert journal.description.startswith(ADVANCE_RELEASE_DESCRIPTION_PREFIX)
    assert service.get_order_unapplied_advance("order-close") == 0.0
    assert accounts["advance"].current_balance == 0.0
    assert accounts["customer"].current_balance == -5000.0
    assert service.release_order_advance(
        "order-close", accounts["customer"].id, "CO-CLOSE"
    ) is None


def test_advance_refund_cash_movement_not_doubled():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        5000.0,
        "Advance",
        reference_order_id="order-refund",
    )
    refund = service.create_advance_refund(
        accounts["customer"].id,
        accounts["cash"].id,
        2500.0,
        "Refund",
        reference_order_id="order-refund",
    )
    assert refund.total_debit == 5000.0
    assert refund.cash_movement_amount == 2500.0


def test_payment_refund_cash_movement():
    service = _service()
    accounts = _seed_accounts(service._account_repo)
    service.create_customer_payment(
        accounts["cash"].id,
        accounts["customer"].id,
        3000.0,
        "Payment",
        reference_order_id="order-pay-refund",
    )
    refund = service.create_customer_payment_refund(
        accounts["customer"].id,
        accounts["cash"].id,
        1500.0,
        "Refund",
        reference_order_id="order-pay-refund",
    )
    assert refund.total_debit == 1500.0
    assert refund.cash_movement_amount == 1500.0
