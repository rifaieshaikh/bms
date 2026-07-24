from datetime import date

from vaybooks.bms.application.boutique.deliveries.service import DeliveryAppService
from vaybooks.bms.application.boutique.time_tracking.service import TimeTrackingAppService
from vaybooks.bms.domain.boutique.deliveries.entities import Delivery
from vaybooks.bms.domain.boutique.orders.entities import (
    CustomizationItem,
    CustomizationOrder,
    OrderActivity,
)
from vaybooks.bms.domain.boutique.time_tracking.entities import TaskType
from vaybooks.bms.domain.shared.enums import ActivityStatus, OrderStatus
from tests.conftest import (
    FakeDeliveryRepository,
    FakeInvoiceRepository,
    FakeOrderRepository,
    FakeTimeTrackingRepository,
)


def _order_with_item(etd: date | None = None) -> CustomizationOrder:
    etd = etd or date(2026, 8, 15)
    return CustomizationOrder(
        id="ord-tasks-1",
        order_number="O-TASKS-1",
        customer_id="cust-1",
        customer_name="Test Customer",
        phone_number="9000000001",
        order_date=date(2026, 7, 1),
        expected_delivery_date=etd,
        order_status=OrderStatus.IN_PROGRESS,
        customization_items=[
            CustomizationItem(
                item_id="item-1",
                bill_number="ZB100",
                description="Dress",
                expected_delivery_date=etd,
            )
        ],
        order_activities=[
            OrderActivity(
                activity_id="act-stitch",
                activity_name="Stitching",
                bill_id="item-1",
                activity_status=ActivityStatus.COMPLETED,
                current_status="Completed",
                is_required=True,
            )
        ],
    )


def test_upsert_etd_task_creates_and_updates():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _order_with_item(date(2026, 8, 15))
    order_repo.save(order)
    service = TimeTrackingAppService(time_repo, order_repo)

    created = service.upsert_etd_task(order, order.customization_items[0])
    assert created is not None
    assert created.task_type == TaskType.ETD
    assert created.work_date == date(2026, 8, 15)
    assert created.bill_id == "item-1"

    order.customization_items[0].expected_delivery_date = date(2026, 9, 1)
    updated = service.upsert_etd_task(order, order.customization_items[0])
    assert updated.id == created.id
    assert updated.work_date == date(2026, 9, 1)
    assert len(service.get_entries_by_order(order.id)) == 1


def test_create_delivery_task_on_record_delivery():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    delivery_repo = FakeDeliveryRepository()
    invoice_repo = FakeInvoiceRepository()
    order = _order_with_item()
    order.order_status = OrderStatus.READY_FOR_DELIVERY
    order_repo.save(order)

    deliveries = DeliveryAppService(
        delivery_repo, order_repo, invoice_repo, time_repo=time_repo
    )
    delivery = deliveries.record_delivery(
        order.id,
        bill_ids=["item-1"],
        delivery_date=date(2026, 8, 20),
        delivery_notes="Handed over",
        allow_already_delivered=True,
    )
    entries = time_repo.find_by_order(order.id)
    delivery_tasks = [e for e in entries if e.task_type == TaskType.DELIVERY]
    assert len(delivery_tasks) == 1
    assert delivery_tasks[0].work_date == date(2026, 8, 20)
    assert delivery_tasks[0].activity_id == f"delivery:{delivery.id}"


def test_list_for_calendar_defaults_to_etd_filter():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _order_with_item(date(2026, 8, 15))
    order_repo.save(order)
    service = TimeTrackingAppService(time_repo, order_repo)
    service.upsert_etd_task(order, order.customization_items[0])
    service.record_time_entry(
        order_id=order.id,
        bill_id="item-1",
        activity_id="act-stitch",
        work_date=date(2026, 8, 10),
        start_time="09:00",
        end_time="11:00",
        worker_name="Asha",
    )
    service.create_delivery_task(
        order,
        Delivery(
            order_id=order.id,
            order_number=order.order_number,
            bill_ids=["item-1"],
            delivery_date=date(2026, 8, 20),
        ),
    )

    start, end = date(2026, 8, 1), date(2026, 8, 31)
    etd_only = service.list_for_calendar(start, end, task_type=TaskType.ETD)
    assert len(etd_only) == 1
    assert etd_only[0].task_type == TaskType.ETD

    activity_only = service.list_for_calendar(
        start, end, task_type=TaskType.ACTIVITY, worker_name="Asha"
    )
    assert len(activity_only) == 1
    assert activity_only[0].worker_name == "Asha"

    all_tasks = service.list_for_calendar(start, end, task_type="all")
    assert len(all_tasks) == 3

    by_activity = service.list_for_calendar(
        start, end, task_type=TaskType.ACTIVITY, activity_name="Stitching"
    )
    assert len(by_activity) == 1
    assert by_activity[0].activity_name == "Stitching"

    no_match = service.list_for_calendar(
        start, end, task_type=TaskType.ACTIVITY, activity_name="Handwork"
    )
    assert no_match == []

    outside = service.list_for_calendar(
        date(2026, 9, 1), date(2026, 9, 30), task_type="all"
    )
    assert outside == []


def test_record_time_entry_sets_activity_task_type():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _order_with_item()
    order_repo.save(order)
    service = TimeTrackingAppService(time_repo, order_repo)
    entry = service.record_time_entry(
        order_id=order.id,
        bill_id="item-1",
        activity_id="act-stitch",
        work_date=date(2026, 8, 10),
        start_time="09:00",
        end_time="10:00",
    )
    assert entry.task_type == TaskType.ACTIVITY
