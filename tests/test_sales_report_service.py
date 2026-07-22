"""Tests for store sales reporting."""

from datetime import date, datetime

from vaybooks.bms.application.finance.reports.services.sales_report_service import SalesReportService
from vaybooks.bms.domain.shared.enums import VoucherType


class _FakeSalesRepo:
    def __init__(self, vouchers):
        self._vouchers = vouchers

    def list_sales_vouchers(self, start, end, limit=100):
        return self._vouchers


def _sales_voucher(gross, collected, discount=0.0, voucher_number="SI-1"):
    lines = [
        {
            "account_name": "Customer - A",
            "description": "Sales invoice",
            "credit_amount": gross,
            "debit_amount": 0,
        },
        {
            "account_name": "Cash",
            "description": "Cash/Bank received",
            "debit_amount": collected,
            "credit_amount": 0,
        },
    ]
    if discount > 0:
        lines.insert(
            1,
            {
                "account_name": "Discount",
                "description": "Discount allowed",
                "debit_amount": discount,
                "credit_amount": 0,
            },
        )
    return {
        "_id": voucher_number,
        "voucher_number": voucher_number,
        "voucher_type": VoucherType.SALES_INVOICE.value,
        "voucher_date": datetime(2026, 7, 10),
        "description": f"Store invoice {voucher_number}",
        "lines": lines,
    }


def test_sales_summary_aggregates_totals():
    repo = _FakeSalesRepo(
        [
            _sales_voucher(1000, 1000),
            _sales_voucher(500, 300, discount=50),
        ]
    )
    service = SalesReportService(repo)
    summary = service.get_sales_summary(date(2026, 7, 1), date(2026, 7, 31))

    assert summary["count"] == 2
    assert summary["gross"] == 1500.0
    assert summary["discount"] == 50.0
    assert summary["net"] == 1450.0
    assert summary["collected"] == 1300.0
    assert summary["outstanding"] == 150.0
    assert summary["avg_sale"] == 750.0
    assert len(summary["recent"]) == 2
