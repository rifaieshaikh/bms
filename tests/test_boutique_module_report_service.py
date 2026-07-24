"""Tests for the Boutique module report facade."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from vaybooks.bms.application.boutique.reports.service import (
    BoutiqueModuleReportService,
)


@dataclass
class _Item:
    item_id: str


@dataclass
class _Order:
    id: str
    order_number: str
    customer_name: str
    expected_delivery_date: date
    order_status: str
    customization_items: list = field(default_factory=list)


@dataclass
class _Invoice:
    order_id: str
    bill_ids: list
    invoice_date: date
    net_amount: float
    is_cancellation: bool = False


@dataclass
class _Delivery:
    order_id: str
    bill_ids: list


class _FakeOps:
    def __init__(self, pipeline, overdue, bills_pending, activity):
        self._pipeline = pipeline
        self._overdue = overdue
        self._bills_pending = bills_pending
        self._activity = activity

    def order_pipeline_report(self, filters=None):
        return self._pipeline

    def overdue_order_report(self, filters=None):
        return self._overdue

    def bills_pending_invoice_report(self, filters=None):
        return self._bills_pending

    def activity_pending_report(self, filters=None):
        return self._activity


class _FakeLabor:
    def __init__(self, time_rows, hours):
        self._time_rows = time_rows
        self._hours = hours

    def time_tracking_report(self, filters=None):
        return self._time_rows

    def labor_hours_by_order(self, start=None, end=None):
        return self._hours


class _FakeRepo:
    def __init__(self, rows):
        self._rows = rows

    def list_all(self):
        return list(self._rows)


def _build_service():
    today = date.today()
    past = today - timedelta(days=5)

    order_a = _Order(
        id="a",
        order_number="ORD-A",
        customer_name="Asha",
        expected_delivery_date=past,
        order_status="In Progress",
        customization_items=[_Item("i1"), _Item("i2")],
    )
    order_c = _Order(
        id="c",
        order_number="ORD-C",
        customer_name="Cancelled Co",
        expected_delivery_date=past,
        order_status="Cancelled",
        customization_items=[_Item("i9")],
    )

    ops = _FakeOps(
        pipeline=[
            {"order_status": "In Progress", "order_count": 3},
            {"order_status": "Delivered", "order_count": 1},
        ],
        overdue=[{"order_number": "ORD-A"}],
        bills_pending=[{"order_number": "ORD-A", "bill_number": "B2"}],
        activity=[{"order_number": "ORD-A", "activity_name": "Stitching"}],
    )
    labor = _FakeLabor(
        time_rows=[{"order_number": "ORD-A", "duration_minutes": 300}],
        hours={"ORD-A": 5.0, "ORD-B": 2.5},
    )
    order_repo = _FakeRepo([order_a, order_c])
    invoice_repo = _FakeRepo(
        [_Invoice("a", ["i1"], today.replace(day=1), 1000.0)]
    )
    delivery_repo = _FakeRepo([_Delivery("a", ["i1"])])

    service = BoutiqueModuleReportService(
        ops, labor, order_repo, invoice_repo, delivery_repo
    )
    return service, today


def test_dashboard_summary_aggregates_kpis():
    service, today = _build_service()
    summary = service.dashboard_summary(today.replace(day=1), today)

    assert summary["open_orders"] == 3
    assert summary["overdue_orders"] == 1
    assert summary["bills_pending_invoice"] == 1
    assert summary["bills_pending_delivery"] == 1
    assert summary["invoiced_revenue"] == 1000.0
    assert summary["hours_logged"] == 7.5


def test_status_breakdown_normalizes_rows():
    service, _ = _build_service()
    rows = service.status_breakdown()
    assert {"status": "In Progress", "count": 3} in rows
    assert {"status": "Delivered", "count": 1} in rows


def test_overdue_queue_excludes_cancelled_and_carries_id():
    service, _ = _build_service()
    queue = service.overdue_queue()
    assert len(queue) == 1
    assert queue[0]["id"] == "a"
    assert queue[0]["days_overdue"] == 5


def test_bills_pending_invoice_queue_counts_uninvoiced_bills():
    service, _ = _build_service()
    queue = service.bills_pending_invoice_queue()
    assert len(queue) == 1
    assert queue[0]["id"] == "a"
    assert queue[0]["pending_bills"] == 1


def test_report_wrappers_delegate_to_backends():
    service, _ = _build_service()
    assert service.order_pipeline_report()[0]["order_status"] == "In Progress"
    assert service.overdue_order_report()[0]["order_number"] == "ORD-A"
    assert service.bills_pending_invoice_report()[0]["bill_number"] == "B2"
    assert service.activity_pending_report(None)[0]["activity_name"] == "Stitching"
    assert service.time_tracking_report(None)[0]["duration_minutes"] == 300
