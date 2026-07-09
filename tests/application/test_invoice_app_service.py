from datetime import date, datetime, timezone

import pytest

from vaybooks.bms.application.invoice_app_service import InvoiceAppService
from vaybooks.bms.application.time_tracking_app_service import TimeTrackingAppService
from vaybooks.bms.domain.deliveries.entities import Delivery
from vaybooks.bms.domain.expenses.entities import Expense
from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.invoices.services import InvoiceDomainService
from vaybooks.bms.domain.orders.entities import CustomizationItem, CustomizationOrder, OrderActivity
from vaybooks.bms.domain.shared.enums import ActivityStatus, ExpenseSource, OrderStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.time_tracking.entities import TimeEntry
from tests.conftest import (
    FakeCounterRepository,
    FakeDeliveryRepository,
    FakeExpenseRepository,
    FakeInvoiceRepository,
    FakeOrderRepository,
    FakeTimeTrackingRepository,
)


def _build_o1001_order() -> CustomizationOrder:
    order = CustomizationOrder(
        id="O-1001",
        order_number="O-1001",
        customer_id="cust-1",
        customer_name="Ananya Rao",
        phone_number="9876543210",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        order_status=OrderStatus.READY_FOR_DELIVERY,
        customization_items=[
            CustomizationItem(
                item_id="bill-zb005",
                bill_number="ZB005",
                description="Blouse",
                sell_amount=4500.0,
            ),
            CustomizationItem(
                item_id="bill-zb006",
                bill_number="ZB006",
                description="Lehenga",
                sell_amount=3500.0,
            ),
        ],
    )
    for item in order.customization_items:
        order.order_activities.append(
            OrderActivity(
                activity_id="act-stitch",
                activity_name="Stitching",
                bill_id=item.item_id,
                activity_status=ActivityStatus.COMPLETED,
                current_status="Completed",
            )
        )
    return order


def _build_o1004_order() -> CustomizationOrder:
    order = CustomizationOrder(
        id="O-1004",
        order_number="O-1004",
        customer_id="cust-4",
        customer_name="Ananya Rao",
        phone_number="9876543211",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        order_status=OrderStatus.READY_FOR_DELIVERY,
        customization_items=[
            CustomizationItem(
                item_id="bill-zb015",
                bill_number="ZB015",
                description="Bridal Lehenga",
                sell_amount=6000.0,
            )
        ],
    )
    order.order_activities.append(
        OrderActivity(
            activity_id="act-stitch",
            activity_name="Stitching",
            bill_id="bill-zb015",
            activity_status=ActivityStatus.COMPLETED,
            current_status="Completed",
        )
    )
    return order


def test_generate_invoice_sets_total_amount_and_invoice_generated_status():
    order_repo = FakeOrderRepository()
    invoice_repo = FakeInvoiceRepository()
    expense_repo = FakeExpenseRepository()
    counter_repo = FakeCounterRepository()

    order = _build_o1001_order()
    order_repo.save(order)

    service = InvoiceAppService(
        invoice_repo,
        order_repo,
        expense_repo,
        counter_repo,
    )

    bill_ids = ["bill-zb005", "bill-zb006"]
    item_amounts = {"bill-zb005": 4500.0, "bill-zb006": 3500.0}
    expected_total = sum(item_amounts.values())

    invoice = service.generate_invoice(
        order_id=order.id,
        bill_ids=bill_ids,
        invoice_amount=expected_total,
        item_amounts=item_amounts,
    )

    assert invoice.total_amount == expected_total
    assert invoice.bill_ids == bill_ids
    assert invoice.order_id == "O-1001"

    updated = order_repo.find_by_id("O-1001")
    assert updated.order_status == OrderStatus.INVOICE_GENERATED

    persisted = invoice_repo.find_by_id(invoice.id)
    assert persisted.total_amount == expected_total


def test_empty_bill_ids_leaves_order_status_unchanged():
    order_repo = FakeOrderRepository()
    invoice_repo = FakeInvoiceRepository()
    expense_repo = FakeExpenseRepository()
    counter_repo = FakeCounterRepository()

    order = _build_o1004_order()
    order_repo.save(order)

    service = InvoiceAppService(
        invoice_repo,
        order_repo,
        expense_repo,
        counter_repo,
    )

    with pytest.raises(ValidationError, match="Select at least one bill"):
        service.generate_invoice(
            order_id=order.id,
            bill_ids=[],
            invoice_amount=6000.0,
        )

    updated = order_repo.find_by_id("O-1004")
    assert updated.order_status == OrderStatus.READY_FOR_DELIVERY
    assert invoice_repo.list_by_order("O-1004") == []


def test_snapshot_skips_items_with_existing_mph_snapshot():
    order = CustomizationOrder(
        id="O-1002",
        order_number="O-1002",
        customer_id="cust-2",
        customer_name="Priya Menon",
        phone_number="9123456780",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        customization_items=[
            CustomizationItem(
                item_id="bill-zb010",
                bill_number="ZB010",
                description="Blouse",
                sell_amount=5000.0,
                margin_per_hour=800.0,
                mph_snapshot_at=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
            )
        ],
    )
    invoice = Invoice(
        order_id=order.id,
        order_number=order.order_number,
        invoice_number="INV-0001",
        invoice_date=date.today(),
        invoice_amount=5000.0,
        total_amount=5000.0,
        bill_ids=["bill-zb010"],
        item_amounts={"bill-zb010": 5000.0},
        margin_per_hour=800.0,
    )
    delivery = Delivery(
        order_id=order.id,
        order_number=order.order_number,
        bill_ids=["bill-zb010"],
        delivery_date=date.today(),
    )
    expenses = [
        Expense(
            order_id=order.id,
            order_number=order.order_number,
            expense_date=date.today(),
            expense_name="Stitching",
            expense_source=ExpenseSource.IN_HOUSE,
            purchase_price=100.0,
            selling_price=200.0,
            quantity=8.0,
            total_purchase_price=800.0,
            total_selling_price=1600.0,
            linked_time_hours=8.0,
            linked_time_minutes=480,
            bill_id="bill-zb010",
        )
    ]

    InvoiceDomainService.snapshot_order_items(order, [invoice], [delivery], expenses)

    item = order.get_item_by_id("bill-zb010")
    assert item.margin_per_hour == 800.0
    assert item.mph_snapshot_at == datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def test_update_time_entry_does_not_change_frozen_invoice_mph():
    order_repo = FakeOrderRepository()
    invoice_repo = FakeInvoiceRepository()
    expense_repo = FakeExpenseRepository()
    counter_repo = FakeCounterRepository()
    time_repo = FakeTimeTrackingRepository()

    order = CustomizationOrder(
        id="O-1002",
        order_number="O-1002",
        customer_id="cust-2",
        customer_name="Priya Menon",
        phone_number="9123456780",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        customization_items=[
            CustomizationItem(
                item_id="bill-zb010",
                bill_number="ZB010",
                sell_amount=5000.0,
                margin_per_hour=800.0,
                mph_snapshot_at=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
            )
        ],
    )
    order_repo.save(order)

    invoice = Invoice(
        order_id=order.id,
        order_number=order.order_number,
        invoice_number="INV-0002",
        invoice_date=date.today(),
        invoice_amount=5000.0,
        total_amount=5000.0,
        bill_ids=["bill-zb010"],
        item_amounts={"bill-zb010": 5000.0},
        margin_per_hour=800.0,
    )
    invoice_repo.save(invoice)

    entry = TimeEntry(
        id="time-1",
        order_id=order.id,
        order_number=order.order_number,
        bill_id="bill-zb010",
        bill_number="ZB010",
        activity_id="act-stitch",
        activity_name="Stitching",
        work_date=date.today(),
        start_time="09:00",
        end_time="11:00",
        duration_minutes=120,
    )
    time_repo.save(entry)

    time_service = TimeTrackingAppService(time_repo, order_repo)
    time_service.update_time_entry(
        entry.id,
        work_date=date.today(),
        start_time="09:00",
        end_time="17:00",
        worker_name="Worker",
        notes="Corrected",
    )

    updated_entry = time_repo.find_by_id(entry.id)
    assert updated_entry.duration_minutes == 480

    persisted_invoice = invoice_repo.find_by_id(invoice.id)
    assert persisted_invoice.margin_per_hour == 800.0

    updated_order = order_repo.find_by_id(order.id)
    item = updated_order.get_item_by_id("bill-zb010")
    assert item.margin_per_hour == 800.0
    assert item.mph_snapshot_at is not None


def _build_zb006_mixed_expenses(order_id: str, bill_id: str) -> list[Expense]:
    """In-house stitching (4 h) plus outsourced dying (₹800) for TC-INV-003."""
    return [
        Expense(
            id="exp-stitch-zb006",
            order_id=order_id,
            order_number=order_id,
            expense_date=date.today(),
            expense_name="Stitching - In House",
            expense_source=ExpenseSource.IN_HOUSE,
            purchase_price=100.0,
            selling_price=0.0,
            quantity=4.0,
            total_purchase_price=400.0,
            total_selling_price=0.0,
            linked_time_hours=4.0,
            linked_time_minutes=240,
            bill_id=bill_id,
            bill_number="ZB006",
            activity_name="Stitching",
        ),
        Expense(
            id="exp-dying-zb006",
            order_id=order_id,
            order_number=order_id,
            expense_date=date.today(),
            expense_name="Dyeing - Outsourced",
            expense_source=ExpenseSource.OUTSOURCED,
            purchase_price=800.0,
            selling_price=800.0,
            quantity=1.0,
            total_purchase_price=800.0,
            total_selling_price=800.0,
            linked_time_hours=0.0,
            bill_id=bill_id,
            bill_number="ZB006",
            activity_name="Dyeing",
        ),
    ]


def test_preview_item_mph_mixed_in_house_and_outsourced_is_675():
    order_repo = FakeOrderRepository()
    invoice_repo = FakeInvoiceRepository()
    expense_repo = FakeExpenseRepository()
    counter_repo = FakeCounterRepository()

    order = _build_o1001_order()
    bill_id = "bill-zb006"
    order_repo.save(order)
    for expense in _build_zb006_mixed_expenses(order.id, bill_id):
        expense_repo.save(expense)

    service = InvoiceAppService(
        invoice_repo,
        order_repo,
        expense_repo,
        counter_repo,
    )

    rows = service.preview_item_mph(order.id, {bill_id: 3500.0})
    assert len(rows) == 1
    assert rows[0]["margin_per_hour"] == 675.0


def test_record_invoice_persists_preview_item_mph():
    order_repo = FakeOrderRepository()
    invoice_repo = FakeInvoiceRepository()
    expense_repo = FakeExpenseRepository()
    counter_repo = FakeCounterRepository()
    delivery_repo = FakeDeliveryRepository()

    order = _build_o1001_order()
    bill_id = "bill-zb006"
    order_repo.save(order)
    for expense in _build_zb006_mixed_expenses(order.id, bill_id):
        expense_repo.save(expense)

    service = InvoiceAppService(
        invoice_repo,
        order_repo,
        expense_repo,
        counter_repo,
        delivery_repo=delivery_repo,
    )

    preview_rows = service.preview_item_mph(order.id, {bill_id: 3500.0})
    expected_mph = preview_rows[0]["margin_per_hour"]

    invoice = service.record_invoice(
        order.id,
        "QA-TC-INV-003-test",
        [bill_id],
        3500.0,
        item_amounts={bill_id: 3500.0},
    )

    assert expected_mph == 675.0
    assert invoice.margin_per_hour == expected_mph

    persisted = service.get_invoice(invoice.id)
    assert persisted.margin_per_hour == expected_mph


def test_allocate_discount_proportionally_splits_by_gross():
    result = InvoiceDomainService.allocate_discount_proportionally(
        {"a": 1000.0, "b": 2000.0}, 300.0
    )
    assert result == {"a": 100.0, "b": 200.0}


def test_allocate_discount_last_item_absorbs_rounding_remainder():
    result = InvoiceDomainService.allocate_discount_proportionally(
        {"a": 100.0, "b": 100.0, "c": 100.0}, 100.0
    )
    # 33.33 + 33.33 + remainder 33.34 == 100.0
    assert round(sum(result.values()), 2) == 100.0


def test_redistribute_discount_delta_only_moves_the_difference():
    result = InvoiceDomainService.redistribute_discount_delta(
        {"a": 1000.0, "b": 2000.0},
        {"a": 50.0, "b": 100.0},
        300.0,  # was 150 → delta 150 split 1:2 → +50 / +100
    )
    assert result == {"a": 100.0, "b": 200.0}


def test_discount_does_not_change_mph():
    order_repo = FakeOrderRepository()
    invoice_repo = FakeInvoiceRepository()
    expense_repo = FakeExpenseRepository()
    counter_repo = FakeCounterRepository()
    delivery_repo = FakeDeliveryRepository()

    order = _build_o1001_order()
    bill_id = "bill-zb006"
    order_repo.save(order)
    for expense in _build_zb006_mixed_expenses(order.id, bill_id):
        expense_repo.save(expense)

    service = InvoiceAppService(
        invoice_repo, order_repo, expense_repo, counter_repo,
        delivery_repo=delivery_repo,
    )

    invoice = service.record_invoice(
        order.id,
        "INV-DISC",
        [bill_id],
        3500.0,
        item_amounts={bill_id: 3500.0},
        item_discounts={bill_id: 500.0},
    )

    # MPH still measured on gross 3500 (not net 3000): 2700 / 4 = 675.
    assert invoice.margin_per_hour == 675.0
    assert invoice.discount_amount == 500.0
    assert invoice.item_discounts == {bill_id: 500.0}
    assert invoice.net_amount == 3000.0


def test_reinvoicing_is_additive_in_preview():
    order_repo = FakeOrderRepository()
    invoice_repo = FakeInvoiceRepository()
    expense_repo = FakeExpenseRepository()
    counter_repo = FakeCounterRepository()
    delivery_repo = FakeDeliveryRepository()

    order = _build_o1001_order()
    bill_id = "bill-zb006"
    order_repo.save(order)
    for expense in _build_zb006_mixed_expenses(order.id, bill_id):
        expense_repo.save(expense)

    service = InvoiceAppService(
        invoice_repo, order_repo, expense_repo, counter_repo,
        delivery_repo=delivery_repo,
    )

    service.record_invoice(
        order.id, "INV-1", [bill_id], 1000.0, item_amounts={bill_id: 1000.0}
    )

    rows = service.preview_item_mph(order.id, {bill_id: 500.0})
    row = rows[0]
    assert row["previously_invoiced"] == 1000.0
    assert row["cumulative_gross"] == 1500.0
    # Cumulative margin: 1500 - 800 expense = 700 over 4 h = 175/h.
    assert row["margin_per_hour"] == 175.0
