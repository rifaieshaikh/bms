"""Tests for AR aging helpers and Customer Outstanding buckets."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from vaybooks.bms.application.finance.reports.services.aging import (
    aging_bucket_index,
    aging_bucket_labels,
    allocate_balance_to_aging_buckets,
    normalize_aging_bucket_days,
)
from vaybooks.bms.application.finance.reports.services.business_insights_report_service import (
    BusinessInsightsReportService,
)
from vaybooks.bms.application.report_filters import OutstandingFilter
from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.common.report_filters import build_outstanding_filter


def test_normalize_aging_bucket_days_parses_and_sorts():
    assert normalize_aging_bucket_days("90, 30, 60") == [30, 60, 90]
    assert normalize_aging_bucket_days("15;45") == [15, 45]
    assert normalize_aging_bucket_days("") == [30, 60, 90]
    assert normalize_aging_bucket_days([0, -5, 30, 30]) == [30]


def test_aging_bucket_labels_and_index():
    cutoffs = [30, 60, 90]
    assert aging_bucket_labels(cutoffs) == ["0-30", "31-60", "61-90", "90+"]
    assert aging_bucket_index(0, cutoffs) == 0
    assert aging_bucket_index(30, cutoffs) == 0
    assert aging_bucket_index(31, cutoffs) == 1
    assert aging_bucket_index(90, cutoffs) == 2
    assert aging_bucket_index(91, cutoffs) == 3


def test_allocate_fifo_payment_to_oldest_invoices():
    as_of = date(2026, 7, 26)
    invoices = [
        {"invoice_date": date(2026, 4, 1), "outstanding": 100.0},  # 116 days
        {"invoice_date": date(2026, 7, 10), "outstanding": 100.0},  # 16 days
    ]
    # Ledger 150 → assume ₹50 paid against oldest invoice.
    buckets, oldest = allocate_balance_to_aging_buckets(
        150.0, invoices, as_of=as_of, cutoffs=[30, 60, 90]
    )
    assert buckets["0-30"] == 100.0
    assert buckets["90+"] == 50.0
    assert buckets["31-60"] == 0.0
    assert buckets["61-90"] == 0.0
    assert oldest == 116
    assert round(sum(buckets.values()), 2) == 150.0


def test_allocate_surplus_without_invoices_goes_to_oldest_bucket():
    buckets, oldest = allocate_balance_to_aging_buckets(
        500.0, [], as_of=date(2026, 7, 26), cutoffs=[30, 60, 90]
    )
    assert buckets["90+"] == 500.0
    assert oldest == 91


def test_build_outstanding_filter_reads_aging_fields():
    result = build_outstanding_filter(
        {
            "as_of": date(2026, 7, 1),
            "bucket_days": "15, 45, 90",
            "min_balance": 100,
            "search": "Alice",
        }
    )
    assert result.as_of_date == date(2026, 7, 1)
    assert result.bucket_days == [15, 45, 90]
    assert result.min_balance == 100.0
    assert result.search == "alice"


def _sales_invoice(*, voucher_id, account_id, gross, collected, voucher_date):
    return SimpleNamespace(
        id=voucher_id,
        voucher_type=VoucherType.SALES_INVOICE,
        voucher_date=voucher_date,
        voucher_number=voucher_id,
        description=f"Store invoice {voucher_id}",
        lines=[
            SimpleNamespace(
                account_id=account_id,
                account_name="Customer A",
                debit_amount=gross - collected,
                credit_amount=0,
                description="Customer receivable",
            ),
            SimpleNamespace(
                account_id="sales",
                account_name="Sales",
                debit_amount=0,
                credit_amount=gross,
                description="Sales invoice",
            ),
            SimpleNamespace(
                account_id="cash",
                account_name="Cash",
                debit_amount=collected,
                credit_amount=0,
                description="Cash/Bank received",
            ),
        ],
    )


def test_customer_outstanding_report_includes_aging_buckets():
    as_of = date(2026, 7, 26)
    account = SimpleNamespace(
        id="acc-1",
        account_name="Customer - Alice",
        linked_customer_id="cust-1",
        linked_vendor_id=None,
        current_balance=150.0,
    )
    vouchers = [
        _sales_invoice(
            voucher_id="SI-OLD",
            account_id="acc-1",
            gross=100.0,
            collected=0.0,
            voucher_date=datetime(2026, 4, 1),
        ),
        _sales_invoice(
            voucher_id="SI-NEW",
            account_id="acc-1",
            gross=100.0,
            collected=0.0,
            voucher_date=datetime(2026, 7, 10),
        ),
    ]

    accounting = MagicMock()
    accounting.list_accounts.return_value = [account]
    accounting.list_vouchers_by_types.return_value = vouchers
    accounting.get_discount_account.return_value = None

    customers = MagicMock()
    customers.list_all_customers.return_value = [
        SimpleNamespace(id="cust-1", customer_name="Alice")
    ]

    service = BusinessInsightsReportService(
        report_repo=MagicMock(),
        accounting_service=accounting,
        vendor_service=MagicMock(),
        customer_service=customers,
    )
    rows = service.customer_outstanding_report(
        OutstandingFilter(as_of_date=as_of, bucket_days=[30, 60, 90])
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["customer_name"] == "Alice"
    assert row["balance_due"] == 150.0
    # Full faces sum to 200 but ledger is 150 → ₹50 settled on oldest.
    assert row["0-30"] == 100.0
    assert row["90+"] == 50.0
    assert row["oldest_days"] == (as_of - date(2026, 4, 1)).days
