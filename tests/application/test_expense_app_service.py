from datetime import date

import pytest

from vaybooks.bms.application.boutique.expenses.service import ExpenseAppService
from vaybooks.bms.application.boutique.invoices.service import InvoiceAppService
from vaybooks.bms.domain.boutique.deliveries.entities import Delivery
from vaybooks.bms.domain.boutique.orders.entities import CustomizationItem, CustomizationOrder, OrderActivity
from vaybooks.bms.domain.shared.enums import ActivityStatus, ExpenseSource, OrderStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import (
    FakeCounterRepository,
    FakeDeliveryRepository,
    FakeExpenseRepository,
    FakeInvoiceRepository,
    FakeOrderRepository,
)


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


def test_expense_edit_recalculates_invoice_mph_and_item_snapshot():
    order_repo = FakeOrderRepository()
    expense_repo = FakeExpenseRepository()
    invoice_repo = FakeInvoiceRepository()
    delivery_repo = FakeDeliveryRepository()
    counter_repo = FakeCounterRepository()

    order = _build_order_with_bill()
    # Invoicing requires completed activities for the bill.
    for act in order.order_activities:
        if act.bill_id == "bill-zb013":
            act.activity_status = ActivityStatus.COMPLETED
            act.current_status = "Completed"
    order_repo.save(order)

    # Mark item delivered so item MPH snapshot is eligible.
    delivery_repo.save(
        Delivery(
            order_id=order.id,
            order_number=order.order_number,
            bill_ids=["bill-zb013"],
            delivery_date=date.today(),
        )
    )

    invoice_service = InvoiceAppService(
        invoice_repo,
        order_repo,
        expense_repo,
        counter_repo,
        delivery_repo=delivery_repo,
    )
    expense_service = ExpenseAppService(
        expense_repo,
        order_repo,
        invoice_service=invoice_service,
        invoice_repo=invoice_repo,
        delivery_repo=delivery_repo,
    )

    # Initial expense + invoice
    exp = expense_service.add_expense(
        order_id=order.id,
        expense_date=date.today(),
        expense_name="Stitching",
        expense_source=ExpenseSource.IN_HOUSE.value,
        purchase_price=100.0,
        selling_price=100.0,
        quantity=4.0,
        bill_id="bill-zb013",
        linked_time_hours=4.0,
        linked_time_minutes=240,
    )
    inv = invoice_service.record_invoice(
        order.id,
        "INV-EXP-1",
        ["bill-zb013"],
        5000.0,
        item_amounts={"bill-zb013": 5000.0},
    )
    before_invoice = invoice_repo.find_by_id(inv.id)
    before_invoice_margin = before_invoice.margin_amount
    before_invoice_mph = before_invoice.margin_per_hour
    before_item = order_repo.find_by_id(order.id).get_item_by_id("bill-zb013")
    assert before_item.mph_snapshot_at is not None

    # Edit expense: increase selling to change margin/MPH.
    exp.selling_price = 200.0
    exp.calculate_totals()
    expense_service.update_expense(exp)

    after_invoice = invoice_repo.find_by_id(inv.id)
    after_item = order_repo.find_by_id(order.id).get_item_by_id("bill-zb013")

    assert after_invoice.margin_amount != before_invoice_margin
    assert after_invoice.margin_per_hour != before_invoice_mph
    assert after_item.margin_per_hour != before_item.margin_per_hour
