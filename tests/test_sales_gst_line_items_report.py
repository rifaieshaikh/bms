"""Tests for Sales GST Line Items report flattening."""

from datetime import date, datetime
from types import SimpleNamespace

from vaybooks.bms.application.finance.reports.services.sales_module_report_service import (
    SalesModuleReportService,
)
from vaybooks.bms.application.sales.service import SalesAppService
from vaybooks.bms.domain.finance.accounting.entities import Account, Voucher, VoucherLine
from vaybooks.bms.domain.sales.line_items import serialize_sales_line_items
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType


class _FakeAccounting:
    def __init__(self, vouchers, accounts=None):
        self._vouchers = vouchers
        self._accounts = accounts or {}

    def list_vouchers_by_type(self, voucher_type, location_filter=None):
        return [v for v in self._vouchers if v.voucher_type == voucher_type]

    def get_account(self, account_id):
        return self._accounts.get(account_id)


class _FakeCustomerService:
    def __init__(self, customers):
        self._customers = customers

    def get_customer_detail(self, customer_id):
        return self._customers.get(customer_id)


def _gst_invoice(
    *,
    voucher_date: date,
    store_number: str,
    customer_account_id: str = "cust-acct",
    items: list[dict] | None = None,
):
    items = items or [
        {
            "product_id": "p1",
            "item_name": "Kurta",
            "description": "Kurta",
            "qty": 2,
            "rate": 500,
            "discount": 0,
            "hsn_sac": "5208",
            "taxable_amount": 1000.0,
            "cgst_amount": 90.0,
            "sgst_amount": 90.0,
            "igst_amount": 0.0,
            "utgst_amount": 0.0,
            "line_total": 1180.0,
            "gst_rate": 18.0,
        }
    ]
    note = serialize_sales_line_items(
        items,
        0.0,
        tax_summary={
            "taxable": 1000.0,
            "cgst": 90.0,
            "sgst": 90.0,
            "igst": 0.0,
            "utgst": 0.0,
            "total_tax": 180.0,
            "grand_total": 1180.0,
        },
    )
    lines = [
        VoucherLine(
            account_id=customer_account_id,
            account_name="Customer - Alice",
            debit_amount=1180.0,
            description="Customer receivable",
        ),
        VoucherLine(
            account_id="sales",
            account_name="Sales",
            credit_amount=1000.0,
            description="Sales invoice",
        ),
        VoucherLine(
            account_id="cgst",
            account_name="CGST Output",
            credit_amount=90.0,
            description="CGST output",
        ),
        VoucherLine(
            account_id="sgst",
            account_name="SGST Output",
            credit_amount=90.0,
            description="SGST output",
        ),
    ]
    return Voucher(
        voucher_number=f"V-{store_number}",
        voucher_type=VoucherType.SALES_INVOICE,
        voucher_date=datetime.combine(voucher_date, datetime.min.time()),
        description=f"Store invoice {store_number}\n{note}",
        lines=lines,
    )


def _sales_app(vouchers) -> SalesAppService:
    account = Account(
        id="cust-acct",
        account_name="Customer - Alice",
        account_type=AccountType.ASSET,
        linked_customer_id="c1",
    )
    customer = SimpleNamespace(
        gstin="27AAAAA0000A1Z5",
        state_code="27",
    )
    return SalesAppService(
        so_repo=None,
        dn_repo=None,
        return_repo=None,
        counter_repo=None,
        accounting=_FakeAccounting(vouchers, accounts={"cust-acct": account}),
        inventory=None,
        customer_service=_FakeCustomerService({"c1": customer}),
    )


def test_list_sales_gst_line_items_flattens_and_joins_gstin():
    voucher = _gst_invoice(voucher_date=date(2026, 7, 15), store_number="SI-100")
    sales = _sales_app([voucher])

    rows = sales.list_sales_gst_line_items()

    assert len(rows) == 1
    row = rows[0]
    assert row["document_type"] == "Sales Invoice"
    assert row["document_number"] == "SI-100"
    assert row["document_date"] == date(2026, 7, 15)
    assert row["party_name"] == "Customer - Alice"
    assert row["party_gstin"] == "27AAAAA0000A1Z5"
    assert row["place_of_supply"] == "Maharashtra"
    assert row["supply_type"] == "B2B"
    assert row["item_name"] == "Kurta"
    assert row["hsn_sac"] == "5208"
    assert row["taxable_amount"] == 1000.0
    assert row["gst_rate"] == 18.0
    assert row["cgst_amount"] == 90.0
    assert row["sgst_amount"] == 90.0
    assert row["line_total"] == 1180.0


def test_list_sales_gst_line_items_respects_date_range():
    vouchers = [
        _gst_invoice(voucher_date=date(2026, 6, 20), store_number="SI-JUN"),
        _gst_invoice(voucher_date=date(2026, 7, 5), store_number="SI-JUL"),
    ]
    sales = _sales_app(vouchers)

    rows = sales.list_sales_gst_line_items(date(2026, 7, 1), date(2026, 7, 31))

    assert len(rows) == 1
    assert rows[0]["document_number"] == "SI-JUL"


def test_sales_module_report_wrapper_delegates():
    class _FakeSales:
        def list_sales_gst_line_items(self, start=None, end=None):
            return [{"document_number": "SI-1", "start": start, "end": end}]

    service = SalesModuleReportService(_FakeSales())
    rows = service.sales_gst_line_items(date(2026, 7, 1), date(2026, 7, 31))
    assert rows[0]["document_number"] == "SI-1"
    assert rows[0]["start"] == date(2026, 7, 1)

    report_rows = service.sales_gst_line_items_report(
        SimpleNamespace(date_range=SimpleNamespace(start=date(2026, 7, 1), end=date(2026, 7, 10)))
    )
    assert report_rows[0]["end"] == date(2026, 7, 10)


def test_b2c_when_customer_has_no_gstin():
    voucher = _gst_invoice(voucher_date=date(2026, 7, 15), store_number="SI-B2C")
    account = Account(
        id="cust-acct",
        account_name="Customer - Walk-in",
        account_type=AccountType.ASSET,
        linked_customer_id="c2",
    )
    customer = SimpleNamespace(gstin="", state_code="27")
    sales = SalesAppService(
        so_repo=None,
        dn_repo=None,
        return_repo=None,
        counter_repo=None,
        accounting=_FakeAccounting([voucher], accounts={"cust-acct": account}),
        inventory=None,
        customer_service=_FakeCustomerService({"c2": customer}),
    )

    rows = sales.list_sales_gst_line_items()
    assert rows[0]["supply_type"] == "B2C"
    assert rows[0]["party_gstin"] == ""
