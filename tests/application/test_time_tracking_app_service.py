from datetime import date

import pytest

from vaybooks.bms.application.time_tracking_app_service import TimeTrackingAppService
from vaybooks.bms.domain.orders.entities import CustomizationItem, CustomizationOrder, OrderActivity
from vaybooks.bms.domain.shared.enums import ActivityStatus, OrderStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.time_tracking.entities import TimeEntry
from tests.conftest import FakeOrderRepository, FakeTimeTrackingRepository


def _build_order_with_bill() -> CustomizationOrder:
    order = CustomizationOrder(
        id="QA-TC-TIME-007-mra9he1x",
        order_number="QA-TC-TIME-007-mra9he1x",
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
            is_required=True,
        )
    )
    return order


def _time_service(order_repo=None, time_repo=None) -> TimeTrackingAppService:
    return TimeTrackingAppService(
        time_repo or FakeTimeTrackingRepository(),
        order_repo or FakeOrderRepository(),
    )


@pytest.mark.parametrize(
    "start_time,end_time,match",
    [
        ("", "13:00", "start_time: This field is required"),
        ("10:00", "", "end_time: This field is required"),
        ("", "", "start_time: This field is required"),
    ],
)
def test_record_time_entry_rejects_missing_times(start_time, end_time, match):
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _build_order_with_bill()
    order_repo.save(order)

    service = _time_service(order_repo, time_repo)
    before_count = len(service.get_entries_by_order(order.id))

    with pytest.raises(ValidationError, match=match):
        service.record_time_entry(
            order_id=order.id,
            bill_id="bill-zb013",
            activity_id="act-stitch",
            work_date=date.today(),
            start_time=start_time,
            end_time=end_time,
        )

    assert len(service.get_entries_by_order(order.id)) == before_count


def _seed_entries(time_repo: FakeTimeTrackingRepository, order: CustomizationOrder):
    entries = [
        TimeEntry(
            order_id=order.id,
            order_number=order.order_number,
            bill_id="bill-zb013",
            bill_number="ZB013",
            activity_id="act-stitch",
            activity_name="Stitching",
            work_date=date.today(),
            start_time="09:00",
            end_time="13:30",
            duration_minutes=270,
            worker_name="Ravi",
        ),
        TimeEntry(
            order_id=order.id,
            order_number="ORDER-XYZ",
            bill_id="bill-hand",
            bill_number="ZB014",
            activity_id="act-hand",
            activity_name="Hand Work",
            work_date=date.today(),
            start_time="10:00",
            end_time="12:00",
            duration_minutes=120,
            worker_name="Meena",
        ),
    ]
    for entry in entries:
        time_repo.save(entry)
    return entries


def test_search_entries_filters_by_bill_number():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _build_order_with_bill()
    order_repo.save(order)
    _seed_entries(time_repo, order)

    service = _time_service(order_repo, time_repo)
    results = service.search_entries(bill_number="ZB014")

    assert len(results) == 1
    assert results[0].bill_number == "ZB014"


def test_search_entries_filters_by_order_number():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _build_order_with_bill()
    order_repo.save(order)
    _seed_entries(time_repo, order)

    service = _time_service(order_repo, time_repo)
    results = service.search_entries(order_number="ORDER-XYZ")

    assert len(results) == 1
    assert results[0].order_number == "ORDER-XYZ"


def test_search_entries_filters_by_worker():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _build_order_with_bill()
    order_repo.save(order)
    _seed_entries(time_repo, order)

    service = _time_service(order_repo, time_repo)
    results = service.search_entries(worker_name="ravi")

    assert len(results) == 1
    assert results[0].worker_name == "Ravi"


def test_search_entries_filters_by_activity():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _build_order_with_bill()
    order_repo.save(order)
    _seed_entries(time_repo, order)

    service = _time_service(order_repo, time_repo)
    results = service.search_entries(activity_name="Hand Work")

    assert len(results) == 1
    assert results[0].activity_name == "Hand Work"


def test_search_entries_combined_filters_use_and_semantics():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _build_order_with_bill()
    order_repo.save(order)
    _seed_entries(time_repo, order)

    service = _time_service(order_repo, time_repo)
    results = service.search_entries(
        bill_number="ZB013",
        activity_name="Stitching",
        worker_name="Ravi",
    )

    assert len(results) == 1
    assert results[0].bill_number == "ZB013"


def test_search_entries_empty_filters_return_all():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _build_order_with_bill()
    order_repo.save(order)
    _seed_entries(time_repo, order)

    service = _time_service(order_repo, time_repo)
    results = service.search_entries()

    assert len(results) == 2


def test_search_entries_filters_by_work_date_range():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _build_order_with_bill()
    order_repo.save(order)
    entries = _seed_entries(time_repo, order)
    service = _time_service(order_repo, time_repo)

    today = date.today()
    results = service.search_entries(work_date_from=today, work_date_to=today)

    assert len(results) == 2
    assert all(e.work_date == today for e in results)

    old_date = date(2020, 1, 1)
    time_repo.save(
        TimeEntry(
            order_id=order.id,
            order_number=order.order_number,
            bill_id="bill-old",
            bill_number="ZB099",
            activity_id="act-stitch",
            activity_name="Stitching",
            work_date=old_date,
            start_time="09:00",
            end_time="10:00",
            duration_minutes=60,
        )
    )
    results_today = service.search_entries(work_date_from=today, work_date_to=today)
    assert len(results_today) == 2
    assert all(e.work_date == today for e in results_today)


def test_update_time_entry_supports_overnight_shift():
    order_repo = FakeOrderRepository()
    time_repo = FakeTimeTrackingRepository()
    order = _build_order_with_bill()
    order_repo.save(order)
    service = _time_service(order_repo, time_repo)

    entry = service.record_time_entry(
        order_id=order.id,
        bill_id="bill-zb013",
        activity_id="act-stitch",
        work_date=date.today(),
        start_time="23:30",
        end_time="00:45",
        ends_next_day=True,
    )

    updated = service.update_time_entry(
        entry.id,
        work_date=date.today(),
        start_time="22:00",
        end_time="01:00",
        ends_next_day=True,
    )

    assert updated.duration_minutes == 180
