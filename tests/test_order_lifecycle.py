"""Order lifecycle: complete and status resolution."""

from datetime import date

import pytest

from vaybooks.bms.domain.order_status import resolve_order_status
from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder
from vaybooks.bms.domain.boutique.orders.services import OrderDomainService
from vaybooks.bms.domain.shared.enums import OrderStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import FakeBillRegistryRepository, FakeOrderRepository


def _order(status: OrderStatus) -> CustomizationOrder:
    return CustomizationOrder(
        id="ord1",
        order_number="CO-0001",
        customer_id="c1",
        customer_name="Test",
        phone_number="9876543210",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        order_status=status,
    )


def test_complete_order_from_delivered():
    domain = OrderDomainService(FakeOrderRepository(), FakeBillRegistryRepository())
    order = _order(OrderStatus.DELIVERED)
    domain.complete_order(order)
    assert order.order_status == OrderStatus.COMPLETED


def test_complete_order_rejects_non_delivered():
    domain = OrderDomainService(FakeOrderRepository(), FakeBillRegistryRepository())
    with pytest.raises(ValidationError, match="Only delivered"):
        domain.complete_order(_order(OrderStatus.IN_PROGRESS))


def test_resolve_order_status_preserves_completed():
    order = _order(OrderStatus.COMPLETED)
    assert resolve_order_status(order) == OrderStatus.COMPLETED
