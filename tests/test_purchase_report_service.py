"""Tests for purchase report overview helpers."""

from datetime import date

from vaybooks.bms.application.finance.reports.services.purchase_report_service import (
    PurchaseReportService,
)
from vaybooks.bms.domain.purchases.entities import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReturn,
    PurchaseReturnLine,
)
from vaybooks.bms.domain.shared.enums import PurchaseOrderStatus


class _FakePurchases:
    def __init__(self, *, orders=None, bills=None, returns=None):
        self._orders = orders or []
        self._bills = bills or []
        self._returns = returns or []

    def list_purchase_orders(self):
        return list(self._orders)

    def list_purchase_bills(self):
        return list(self._bills)

    def list_purchase_returns(self):
        return list(self._returns)


def _po(
    *,
    status=PurchaseOrderStatus.SENT,
    expected_date=None,
    qty_ordered=10.0,
    qty_received=0.0,
    vendor_name="Vendor A",
    po_number="PO-1",
):
    return PurchaseOrder(
        id="po1",
        po_number=po_number,
        vendor_id="v1",
        vendor_name=vendor_name,
        order_date=date(2026, 7, 1),
        expected_date=expected_date,
        status=status,
        lines=[
            PurchaseOrderLine(
                product_id="p1",
                product_name="Item",
                qty_ordered=qty_ordered,
                qty_received=qty_received,
                rate=100.0,
            )
        ],
    )


def test_dashboard_summary_respects_date_range():
    purchases = _FakePurchases(
        orders=[_po()],
        bills=[
            {"bill_date": date(2026, 7, 5), "total": 500.0, "vendor_name": "Vendor A"},
            {"bill_date": date(2026, 6, 20), "total": 200.0, "vendor_name": "Vendor A"},
        ],
        returns=[
            PurchaseReturn(
                return_number="PR-1",
                vendor_id="v1",
                vendor_name="Vendor A",
                return_date=date(2026, 7, 8),
                lines=[PurchaseReturnLine(product_id="p1", qty=1, rate=50.0)],
            )
        ],
    )
    service = PurchaseReportService(purchases)
    summary = service.dashboard_summary(date(2026, 7, 1), date(2026, 7, 31))

    assert summary["open_po_count"] == 1
    assert summary["pending_grn_qty"] == 10.0
    assert summary["purchases_this_month"] == 500.0
    assert summary["returns_this_month"] == 50.0


def test_dashboard_summary_empty_data():
    service = PurchaseReportService(_FakePurchases())
    summary = service.dashboard_summary(date(2026, 7, 1), date(2026, 7, 31))
    assert summary == {
        "open_po_count": 0,
        "pending_grn_qty": 0.0,
        "purchases_this_month": 0.0,
        "returns_this_month": 0.0,
    }


def test_overdue_po_count():
    purchases = _FakePurchases(
        orders=[
            _po(expected_date=date(2020, 1, 1), po_number="PO-OLD"),
            _po(
                expected_date=date(2099, 1, 1),
                po_number="PO-FUTURE",
                status=PurchaseOrderStatus.SENT,
            ),
            _po(
                expected_date=date(2020, 1, 1),
                status=PurchaseOrderStatus.RECEIVED,
                qty_received=10.0,
                po_number="PO-DONE",
            ),
        ]
    )
    # Give distinct ids so pipeline rows stay unique
    purchases._orders[1].id = "po2"
    purchases._orders[2].id = "po3"
    service = PurchaseReportService(purchases)
    assert service.overdue_po_count() == 1


def test_spend_time_series_day_and_week_grain():
    purchases = _FakePurchases(
        bills=[
            {"bill_date": date(2026, 7, 1), "total": 100.0},
            {"bill_date": date(2026, 7, 1), "total": 50.0},
            {"bill_date": date(2026, 7, 8), "total": 200.0},
        ]
    )
    service = PurchaseReportService(purchases)
    by_day = service.spend_time_series(date(2026, 7, 1), date(2026, 7, 31), grain="day")
    assert by_day == [
        {"period": "2026-07-01", "amount": 150.0},
        {"period": "2026-07-08", "amount": 200.0},
    ]

    by_week = service.spend_time_series(date(2026, 7, 1), date(2026, 7, 31), grain="week")
    # 2026-07-01 is Wednesday → week starts 2026-06-29
    assert by_week[0]["period"] == "2026-06-29"
    assert by_week[0]["amount"] == 150.0


def test_po_status_breakdown_excludes_closed_cancelled():
    purchases = _FakePurchases(
        orders=[
            _po(status=PurchaseOrderStatus.DRAFT, po_number="PO-D"),
            _po(status=PurchaseOrderStatus.SENT, po_number="PO-S"),
            _po(status=PurchaseOrderStatus.CANCELLED, po_number="PO-C"),
            _po(status=PurchaseOrderStatus.CLOSED, po_number="PO-CL"),
        ]
    )
    for i, po in enumerate(purchases._orders):
        po.id = f"po{i}"
    service = PurchaseReportService(purchases)
    rows = {r["status"]: r["count"] for r in service.po_status_breakdown()}
    assert rows == {"Draft": 1, "Sent": 1}


def test_grn_pending_by_vendor_limit():
    orders = []
    for i in range(3):
        po = _po(
            vendor_name=f"Vendor {i}",
            po_number=f"PO-{i}",
            qty_ordered=float(i + 1),
            qty_received=0.0,
        )
        po.id = f"po{i}"
        orders.append(po)
    service = PurchaseReportService(_FakePurchases(orders=orders))
    rows = service.grn_pending_by_vendor(limit=2)
    assert len(rows) == 2
    assert rows[0]["vendor_name"] == "Vendor 2"
    assert rows[0]["qty_pending"] == 3.0
    assert rows[1]["vendor_name"] == "Vendor 1"


def test_purchases_vs_returns_series():
    purchases = _FakePurchases(
        bills=[
            {"bill_date": date(2026, 7, 5), "total": 1000.0},
            {"bill_date": date(2026, 6, 5), "total": 400.0},
        ],
        returns=[
            PurchaseReturn(
                return_number="PR-1",
                vendor_id="v1",
                return_date=date(2026, 7, 10),
                lines=[PurchaseReturnLine(product_id="p1", qty=1, rate=100.0)],
            )
        ],
    )
    service = PurchaseReportService(purchases)
    rows = service.purchases_vs_returns_series(date(2026, 6, 1), date(2026, 7, 31))
    by_period = {r["period"]: r for r in rows}
    assert by_period["2026-06"]["purchases"] == 400.0
    assert by_period["2026-06"]["returns"] == 0.0
    assert by_period["2026-07"]["purchases"] == 1000.0
    assert by_period["2026-07"]["returns"] == 100.0
