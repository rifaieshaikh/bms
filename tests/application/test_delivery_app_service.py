from datetime import date

from vaybooks.bms.application.boutique.deliveries.service import DeliveryAppService
from vaybooks.bms.application.boutique.expenses.service import ExpenseAppService
from vaybooks.bms.domain.boutique.expenses.entities import Expense
from vaybooks.bms.domain.boutique.invoices.entities import Invoice
from vaybooks.bms.domain.shared.enums import ExpenseSource, OrderStatus
from tests.application.test_invoice_app_service import _build_o1001_order
from tests.conftest import (
    FakeDeliveryRepository,
    FakeExpenseRepository,
    FakeInvoiceRepository,
    FakeOrderRepository,
)


def _delivery_service(
    order_repo=None,
    invoice_repo=None,
    expense_repo=None,
    delivery_repo=None,
) -> DeliveryAppService:
    return DeliveryAppService(
        delivery_repo or FakeDeliveryRepository(),
        order_repo or FakeOrderRepository(),
        invoice_repo or FakeInvoiceRepository(),
        expense_repo or FakeExpenseRepository(),
    )


def _seed_invoiced_o1001():
    order_repo = FakeOrderRepository()
    invoice_repo = FakeInvoiceRepository()
    expense_repo = FakeExpenseRepository()
    delivery_repo = FakeDeliveryRepository()

    order = _build_o1001_order()
    order.order_status = OrderStatus.INVOICE_GENERATED
    order_repo.save(order)

    bill_ids = [item.item_id for item in order.customization_items]
    item_amounts = {item.item_id: float(item.sell_amount) for item in order.customization_items}
    invoice_repo.save(
        Invoice(
            order_id=order.id,
            order_number=order.order_number,
            invoice_number="INV-0001",
            invoice_date=date(2024, 6, 15),
            invoice_amount=8000.0,
            total_amount=8000.0,
            bill_ids=bill_ids,
            item_amounts=item_amounts,
        )
    )

    for item in order.customization_items:
        expense_repo.save(
            Expense(
                id=f"exp-{item.item_id}",
                order_id=order.id,
                order_number=order.order_number,
                expense_date=date(2024, 6, 10),
                expense_name=f"Stitching - {item.bill_number}",
                expense_source=ExpenseSource.IN_HOUSE,
                purchase_price=100.0,
                selling_price=200.0,
                quantity=5.0,
                total_purchase_price=500.0,
                total_selling_price=1000.0,
                linked_time_hours=5.0,
                bill_id=item.item_id,
                bill_number=item.bill_number,
                activity_id="act-stitch",
                activity_name="Stitching",
            )
        )

    return order_repo, invoice_repo, expense_repo, delivery_repo, bill_ids


def test_record_delivery_accepts_compact_order_ref_and_sets_delivered():
    order_repo, invoice_repo, expense_repo, delivery_repo, bill_ids = _seed_invoiced_o1001()
    service = _delivery_service(order_repo, invoice_repo, expense_repo, delivery_repo)

    delivery = service.record_delivery(
        order_id="O1001",
        bill_ids=bill_ids,
        delivery_date=date(2024, 6, 18),
    )

    assert delivery.order_id == "O-1001"
    assert delivery.bill_ids == bill_ids
    assert delivery.delivery_date == date(2024, 6, 18)

    updated = order_repo.find_by_id("O-1001")
    assert updated.order_status == OrderStatus.DELIVERED

    stored = delivery_repo.list_by_order("O-1001")
    assert len(stored) == 1
    assert stored[0].bill_ids == bill_ids


def test_record_delivery_freezes_item_mph():
    order_repo, invoice_repo, expense_repo, delivery_repo, bill_ids = _seed_invoiced_o1001()
    service = _delivery_service(order_repo, invoice_repo, expense_repo, delivery_repo)

    service.record_delivery(
        order_id="O-1001",
        bill_ids=bill_ids,
        delivery_date=date(2024, 6, 18),
    )

    updated = order_repo.find_by_id("O-1001")
    for item in updated.customization_items:
        assert item.mph_snapshot_at is not None
        assert item.margin_per_hour is not None


def test_expense_update_does_not_change_frozen_item_mph():
    order_repo, invoice_repo, expense_repo, delivery_repo, bill_ids = _seed_invoiced_o1001()
    delivery_service = _delivery_service(
        order_repo, invoice_repo, expense_repo, delivery_repo
    )
    delivery_service.record_delivery(
        order_id="O-1001",
        bill_ids=bill_ids,
        delivery_date=date(2024, 6, 18),
    )

    order = order_repo.find_by_id("O-1001")
    item = order.get_item_by_id("bill-zb005")
    frozen_mph = item.margin_per_hour
    frozen_at = item.mph_snapshot_at

    expense_service = ExpenseAppService(expense_repo, order_repo)
    expense = expense_repo.find_by_id("exp-bill-zb005")
    expense_service.update_expense_details(
        expense.id,
        expense_date=expense.expense_date,
        expense_name=expense.expense_name,
        expense_source=expense.expense_source.value,
        purchase_price=250.0,
        selling_price=400.0,
        quantity=6.0,
        notes="Post-delivery edit",
    )

    updated = order_repo.find_by_id("O-1001")
    frozen_item = updated.get_item_by_id("bill-zb005")
    assert frozen_item.margin_per_hour == frozen_mph
    assert frozen_item.mph_snapshot_at == frozen_at
