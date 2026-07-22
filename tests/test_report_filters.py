from datetime import date, datetime
from unittest.mock import MagicMock

from vaybooks.bms.application.report_filters import (
    DateRange,
    ItemProfitabilityFilter,
    OrderMphFilter,
)
from vaybooks.bms.application.finance.reports.services.profitability_report_service import (
    ProfitabilityReportService,
)
from vaybooks.bms.infrastructure.db.bson_utils import as_date


class _FakeProfitabilityRepo:
    def __init__(self, items):
        self._items = items
        self.last_range = None

    def get_item_profitability(self, start, end):
        self.last_range = (start, end)
        return self._items


def test_as_date_normalizes_datetime():
    dt = datetime(2026, 1, 15, 14, 30)
    assert as_date(dt) == date(2026, 1, 15)


def test_mph_report_rolls_up_by_order():
    items = [
        {
            "order_number": "ORD-1",
            "customer_name": "Alice",
            "margin_amount": 1000.0,
            "in_house_hours": 10.0,
            "delivered_on": date(2026, 1, 5),
        },
        {
            "order_number": "ORD-1",
            "customer_name": "Alice",
            "margin_amount": 500.0,
            "in_house_hours": 5.0,
            "delivered_on": date(2026, 1, 10),
        },
        {
            "order_number": "ORD-2",
            "customer_name": "Bob",
            "margin_amount": 300.0,
            "in_house_hours": 0.0,
            "delivered_on": date(2026, 1, 3),
        },
    ]
    repo = _FakeProfitabilityRepo(items)
    service = ProfitabilityReportService(repo)
    filters = OrderMphFilter(
        date_range=DateRange(date(2026, 1, 1), date(2026, 1, 31)),
    )
    rows = service.mph_report(filters)
    assert len(rows) == 2
    ord1 = next(r for r in rows if r["order_number"] == "ORD-1")
    assert ord1["item_count"] == 2
    assert ord1["total_margin"] == 1500.0
    assert ord1["total_hours"] == 15.0
    assert ord1["margin_per_hour"] == 100.0
    assert ord1["delivered_through"] == date(2026, 1, 10)
    ord2 = next(r for r in rows if r["order_number"] == "ORD-2")
    assert ord2["margin_per_hour"] is None


def test_item_profitability_passes_date_range_to_repo():
    repo = _FakeProfitabilityRepo([])
    service = ProfitabilityReportService(repo)
    start, end = date(2026, 3, 1), date(2026, 3, 15)
    service.item_profitability_report(
        ItemProfitabilityFilter(date_range=DateRange(start, end))
    )
    assert repo.last_range == (start, end)


def test_mph_report_min_mph_filter():
    items = [
        {
            "order_number": "ORD-1",
            "customer_name": "Alice",
            "margin_amount": 100.0,
            "in_house_hours": 10.0,
            "delivered_on": date(2026, 1, 1),
        },
        {
            "order_number": "ORD-2",
            "customer_name": "Bob",
            "margin_amount": 1000.0,
            "in_house_hours": 10.0,
            "delivered_on": date(2026, 1, 1),
        },
    ]
    service = ProfitabilityReportService(_FakeProfitabilityRepo(items))
    rows = service.mph_report(
        OrderMphFilter(
            date_range=DateRange(date(2026, 1, 1), date(2026, 1, 31)),
            min_mph=50.0,
        )
    )
    assert len(rows) == 1
    assert rows[0]["order_number"] == "ORD-2"


def test_mph_report_min_mph_inclusive_at_boundary():
    items = [
        {
            "order_number": "ORD-150",
            "customer_name": "Kavya",
            "margin_amount": 1500.0,
            "in_house_hours": 10.0,
            "delivered_on": date(2026, 1, 1),
        },
        {
            "order_number": "ORD-149",
            "customer_name": "Meera",
            "margin_amount": 1490.0,
            "in_house_hours": 10.0,
            "delivered_on": date(2026, 1, 1),
        },
    ]
    service = ProfitabilityReportService(_FakeProfitabilityRepo(items))
    rows = service.mph_report(
        OrderMphFilter(
            date_range=DateRange(date(2026, 1, 1), date(2026, 1, 31)),
            min_mph=150.0,
        )
    )
    assert len(rows) == 1
    assert rows[0]["order_number"] == "ORD-150"
    assert rows[0]["margin_per_hour"] == 150.0
