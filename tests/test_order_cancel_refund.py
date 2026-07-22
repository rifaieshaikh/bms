"""Cancel order keeps advance pool; refund path uses proper cash voucher."""

from datetime import date

import pytest

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.boutique.orders.service import OrderAppService
from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder
from vaybooks.bms.domain.shared.enums import OrderStatus, VoucherType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import (
    FakeAccountRepository,
    FakeActivityRepository,
    FakeBillRegistryRepository,
    FakeCounterRepository,
    FakeCustomerRepository,
    FakeExpenseRepository,
    FakeOrderRepository,
    FakeTimeTrackingRepository,
    FakeVoucherRepository,
)
from tests.test_advance_accounting import _seed_accounts, _service


def _order_service(accounting: AccountingAppService) -> OrderAppService:
    return OrderAppService(
        FakeOrderRepository(),
        FakeBillRegistryRepository(),
        FakeCustomerRepository(),
        accounting._account_repo,
        FakeActivityRepository(),
        FakeTimeTrackingRepository(),
        FakeExpenseRepository(),
        FakeVoucherRepository(),
        FakeCounterRepository(),
        accounting_service=accounting,
    )


def _draft_order(order_repo: FakeOrderRepository, order_id: str = "ord-1") -> CustomizationOrder:
    order = CustomizationOrder(
        id=order_id,
        order_number="CO-0001",
        customer_id="cust-1",
        customer_name="Test Customer",
        phone_number="9999999999",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        order_status=OrderStatus.IN_PROGRESS,
    )
    return order_repo.save(order)


def test_cancel_order_does_not_release_advance():
    accounting = _service()
    accounts = _seed_accounts(accounting._account_repo)
    order_service = _order_service(accounting)
    order = _draft_order(order_service._order_repo)

    accounting.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        5000.0,
        "Advance",
        reference_order_id=order.id,
    )

    cancelled = order_service.cancel_order(order.id)

    assert cancelled.order_status == OrderStatus.CANCELLED
    assert accounting.get_order_unapplied_advance(order.id) == 5000.0
    assert not accounting.has_advance_release_journal(order.id)


def test_cancel_then_advance_refund_zeros_unapplied():
    accounting = _service()
    accounts = _seed_accounts(accounting._account_repo)
    order_service = _order_service(accounting)
    order = _draft_order(order_service._order_repo, "ord-2")

    accounting.create_advance_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        3000.0,
        "Advance",
        reference_order_id=order.id,
    )
    order_service.cancel_order(order.id)
    refund = accounting.create_advance_refund(
        accounts["customer"].id,
        accounts["cash"].id,
        3000.0,
        "Advance refund - CO-0001",
        reference_order_id=order.id,
    )

    assert refund.voucher_type == VoucherType.REFUND
    assert refund.is_advance_refund
    assert refund.cash_movement_amount == 3000.0
    assert accounting.get_order_unapplied_advance(order.id) == 0.0


def test_cannot_cancel_completed_order():
    accounting = _service()
    order_service = _order_service(accounting)
    order = _draft_order(order_service._order_repo, "ord-3")
    order.order_status = OrderStatus.COMPLETED
    order_service._order_repo.save(order)

    with pytest.raises(ValidationError, match="Completed orders cannot be cancelled"):
        order_service.cancel_order(order.id)
