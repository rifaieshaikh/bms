
def test_time_tracking_page_renders_with_zero_entries():
    def _page():
        from datetime import date
        from unittest.mock import MagicMock

        from vaybooks.bms.application.time_tracking_app_service import TimeTrackingAppService
        from vaybooks.bms.domain.activities.entities import ActivityConfig
        from vaybooks.bms.domain.orders.entities import (
            CustomizationItem,
            CustomizationOrder,
            OrderActivity,
        )
        from vaybooks.bms.domain.shared.enums import ActivityType
        from vaybooks.bms.ui.pages import time_tracking
        from tests.conftest import FakeOrderRepository, FakeTimeTrackingRepository

        order = CustomizationOrder(
            id="ord-zb011",
            order_number="O-ZB011",
            customer_id="cust-1",
            customer_name="QA Customer",
            phone_number="9000000001",
            order_date=date(2024, 6, 1),
            expected_delivery_date=date(2024, 7, 1),
            customization_items=[
                CustomizationItem(
                    item_id="bill-zb011",
                    bill_number="ZB011",
                    description="Test item",
                )
            ],
            order_activities=[
                OrderActivity(
                    activity_id="act-stitch",
                    activity_name="Stitching",
                    is_required=True,
                )
            ],
        )
        order_repo = FakeOrderRepository()
        order_repo.save(order)
        time_service = TimeTrackingAppService(FakeTimeTrackingRepository(), order_repo)
        order_service = MagicMock()
        order_service.get_order_detail.return_value = order
        activity_service = MagicMock()
        activity_service.list_activities.return_value = [
            ActivityConfig(activity_name="Stitching", activity_type=ActivityType.IN_HOUSE),
        ]
        services = {
            "time_tracking": time_service,
            "orders": order_service,
            "activities": activity_service,
            "workers": MagicMock(list_workers_by_activity=MagicMock(return_value=[])),
        }

        time_tracking.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("info")
    )
    captions = " ".join(getattr(el, "proto", el).body for el in at.caption)
    buttons = " ".join(getattr(el, "label", "") or "" for el in at.button)
    labels = " ".join(getattr(el, "label", "") or "" for el in at.text_input)
    tabs = " ".join(getattr(el, "label", "") or "" for el in at.get("tab"))
    page_text = f"{rendered} {captions} {buttons} {labels} {tabs}".lower()
    assert "time log" in page_text
    assert "record time" in page_text
    assert "bill number" in page_text


def test_time_tracking_page_renders_with_multiple_entries():
    def _page():
        from datetime import date
        from unittest.mock import MagicMock

        from vaybooks.bms.application.time_tracking_app_service import TimeTrackingAppService
        from vaybooks.bms.domain.activities.entities import ActivityConfig
        from vaybooks.bms.domain.orders.entities import (
            CustomizationItem,
            CustomizationOrder,
            OrderActivity,
        )
        from vaybooks.bms.domain.shared.enums import ActivityType
        from vaybooks.bms.domain.time_tracking.entities import TimeEntry
        from vaybooks.bms.ui.pages import time_tracking
        from tests.conftest import FakeOrderRepository, FakeTimeTrackingRepository

        order = CustomizationOrder(
            id="ord-zb011",
            order_number="O-ZB011",
            customer_id="cust-1",
            customer_name="QA Customer",
            phone_number="9000000001",
            order_date=date(2024, 6, 1),
            expected_delivery_date=date(2024, 7, 1),
            customization_items=[
                CustomizationItem(
                    item_id="bill-zb011",
                    bill_number="ZB011",
                    description="Test item",
                )
            ],
            order_activities=[
                OrderActivity(
                    activity_id="act-stitch",
                    activity_name="Stitching",
                    is_required=True,
                )
            ],
        )
        order_repo = FakeOrderRepository()
        order_repo.save(order)
        time_repo = FakeTimeTrackingRepository()
        bill_id = "bill-zb011"
        today = date.today()
        for entry in (
            TimeEntry(
                order_id=order.id,
                order_number=order.order_number,
                bill_id=bill_id,
                bill_number="ZB011",
                activity_id="act-stitch",
                activity_name="Stitching",
                work_date=today,
                start_time="10:00",
                end_time="14:30",
                duration_minutes=270,
            ),
            TimeEntry(
                order_id=order.id,
                order_number=order.order_number,
                bill_id=bill_id,
                bill_number="ZB011",
                activity_id="act-stitch",
                activity_name="Stitching",
                work_date=today,
                start_time="09:00",
                end_time="11:00",
                duration_minutes=120,
            ),
        ):
            time_repo.save(entry)

        time_service = TimeTrackingAppService(time_repo, order_repo)
        order_service = MagicMock()
        order_service.get_order_detail.return_value = order
        activity_service = MagicMock()
        activity_service.list_activities.return_value = [
            ActivityConfig(activity_name="Stitching", activity_type=ActivityType.IN_HOUSE),
        ]
        services = {
            "time_tracking": time_service,
            "orders": order_service,
            "activities": activity_service,
            "workers": MagicMock(list_workers_by_activity=MagicMock(return_value=[])),
        }

        time_tracking.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("info")
    )
    captions = " ".join(getattr(el, "proto", el).body for el in at.caption)
    buttons = " ".join(getattr(el, "label", "") or "" for el in at.button)
    labels = " ".join(getattr(el, "label", "") or "" for el in at.text_input)
    tabs = " ".join(getattr(el, "label", "") or "" for el in at.get("tab"))
    page_text = f"{rendered} {captions} {buttons} {labels} {tabs}"
    assert "Stitching" in page_text
    assert "4.5 hrs" in page_text
    assert "ZB011" in page_text
