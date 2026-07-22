from datetime import date

import pytest

from vaybooks.bms.domain.boutique.activities.entities import ActivityConfig
from vaybooks.bms.domain.boutique.activities.services import ActivityDomainService
from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder, OrderActivity
from vaybooks.bms.domain.shared.enums import ActivityStatus, ActivityType, OrderStatus
from vaybooks.bms.domain.shared.exceptions import IncompleteTimeEntriesError
from vaybooks.bms.domain.boutique.time_tracking.entities import TimeEntry


def _make_order_with_activity():
    activity = ActivityConfig(
        id="act1",
        activity_name="Stitching",
        activity_type=ActivityType.IN_HOUSE,
        is_in_house=True,
        requires_time_tracking=True,
        default_hourly_expense=500,
    )
    order_activity = OrderActivity(
        order_activity_id="oa1",
        activity_id="act1",
        activity_name="Stitching",
        is_required=True,
    )
    order = CustomizationOrder(
        id="ord1",
        order_number="CO-0001",
        customer_id="c1",
        customer_name="Aysha",
        phone_number="9876543210",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        order_activities=[order_activity],
    )
    return order, order_activity, activity


def test_cannot_complete_with_incomplete_time():
    order, order_activity, activity = _make_order_with_activity()
    incomplete_entry = TimeEntry(
        order_id="ord1",
        order_number="CO-0001",
        bill_id="b1",
        bill_number="ZB001",
        activity_id="act1",
        activity_name="Stitching",
        work_date=date.today(),
        start_time="10:00",
        end_time="",
        duration_minutes=0,
    )
    service = ActivityDomainService()
    with pytest.raises(IncompleteTimeEntriesError):
        service.prepare_completion(order, order_activity, activity, [incomplete_entry])


def test_cannot_complete_without_time_entries():
    order, order_activity, activity = _make_order_with_activity()
    service = ActivityDomainService()
    with pytest.raises(IncompleteTimeEntriesError):
        service.prepare_completion(order, order_activity, activity, [])


def test_ready_for_delivery_when_all_done():
    from vaybooks.bms.domain.boutique.orders.services import OrderDomainService
    from tests.conftest import FakeBillRegistryRepository, FakeOrderRepository

    order, oa1, _ = _make_order_with_activity()
    oa2 = OrderActivity(
        order_activity_id="oa2",
        activity_id="act2",
        activity_name="Dyeing",
        is_required=True,
        activity_status=ActivityStatus.SKIPPED,
    )
    order.order_activities.append(oa2)
    oa1.activity_status = ActivityStatus.COMPLETED

    domain = OrderDomainService(FakeOrderRepository(), FakeBillRegistryRepository())
    domain.recalculate_status(order)
    assert order.order_status == OrderStatus.READY_FOR_DELIVERY
