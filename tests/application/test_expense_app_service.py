from datetime import date

import pytest

from vaybooks.bms.application.expense_app_service import ExpenseAppService
from vaybooks.bms.domain.orders.entities import CustomizationItem, CustomizationOrder, OrderActivity
from vaybooks.bms.domain.shared.enums import ActivityStatus, ExpenseSource, OrderStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import FakeExpenseRepository, FakeOrderRepository


def _build_order_with_bill() -> CustomizationOrder:
    order = CustomizationOrder(
        id="O-ZB013",
        order_number="O-ZB013",
        customer_id="cust-1",
        customer_name="Test Customer",
        phone_number="9876543210",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        order_status=OrderStatus.IN_PROGRESS,
        customization_items=[
            CustomizationItem(
                item_id="bill-zb013",
                bill_number="ZB013",
                description="Test item",
                sell_amount=5000.0,
            )
        ],
    )
    order.order_activities.append(
        OrderActivity(
            activity_id="act-stitch",
            activity_name="Stitching",
            bill_id="bill-zb013",
            activity_status=ActivityStatus.IN_PROGRESS,
            current_status="In Progress",
        )
    )
    return order


def _expense_service(order_repo=None, expense_repo=None) -> ExpenseAppService:
    return ExpenseAppService(
        expense_repo or FakeExpenseRepository(),
        order_repo or FakeOrderRepository(),
    )


@pytest.mark.parametrize("purchase_price,selling_price", [(-500, -500), (0, 100), (100, 0)])
def test_add_expense_rejects_non_positive_price(purchase_price, selling_price):
    order_repo = FakeOrderRepository()
    expense_repo = FakeExpenseRepository()
    order = _build_order_with_bill()
    order_repo.save(order)

    service = _expense_service(order_repo, expense_repo)

    with pytest.raises(ValidationError, match="Price must be a positive value"):
        service.add_expense(
            order_id=order.id,
            expense_date=date.today(),
            expense_name="QA-TC-EXP-004-mra9he1x",
            expense_source=ExpenseSource.IN_HOUSE.value,
            purchase_price=purchase_price,
            selling_price=selling_price,
            bill_id="bill-zb013",
        )

    assert service.get_expenses_by_order(order.id) == []
    assert service.get_expenses_by_bill("bill-zb013") == []


def test_add_expense_accepts_positive_price():
    order_repo = FakeOrderRepository()
    expense_repo = FakeExpenseRepository()
    order = _build_order_with_bill()
    order_repo.save(order)

    service = _expense_service(order_repo, expense_repo)
    expense = service.add_expense(
        order_id=order.id,
        expense_date=date.today(),
        expense_name="Valid expense",
        expense_source=ExpenseSource.IN_HOUSE.value,
        purchase_price=500.0,
        selling_price=500.0,
        bill_id="bill-zb013",
    )

    assert expense.purchase_price == 500.0
    assert len(service.get_expenses_by_order(order.id)) == 1
    assert len(service.get_expenses_by_bill("bill-zb013")) == 1
