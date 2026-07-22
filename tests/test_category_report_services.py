from datetime import date
from unittest.mock import MagicMock

from vaybooks.bms.application.finance.reports.service import ReportAppService
from vaybooks.bms.application.report_filters import (
    DateRange,
    ItemProfitabilityFilter,
    OrderPipelineFilter,
    PeriodSummaryFilter,
    TopCustomersFilter,
    WorkerProductivityFilter,
)
from vaybooks.bms.application.finance.reports.services.business_insights_report_service import (
    BusinessInsightsReportService,
)
from vaybooks.bms.application.finance.reports.services.labor_report_service import LaborReportService
from vaybooks.bms.application.finance.reports.services.operations_report_service import (
    OperationsReportService,
)


class _FakeRepo:
    def __init__(self, **kwargs):
        self._data = kwargs

    def get_item_profitability(self, start, end):
        return self._data.get("items", [])

    def get_time_entries(self, start, end, worker=None, activity_name=None):
        return self._data.get("time_entries", [])

    def get_orders_pipeline_snapshot(self):
        return self._data.get("pipeline", [])

    def get_bills_pending_invoice_rows(self):
        return self._data.get("bills_pending", [])

    def get_completed_orders(self, start, end, statuses):
        return self._data.get("completed_orders", [])


def test_business_insights_period_financial_summary_flattens_metrics():
    repo = MagicMock()
    repo.get_monthly_invoice_total.return_value = 1000
    repo.get_monthly_advance_total.return_value = 200
    repo.count_orders_created.return_value = 5
    repo.sum_expenses_total.return_value = 300
    repo.get_pending_activities_count.return_value = 2
    repo.get_bills_pending_invoice_count.return_value = 1
    repo.count_delivered_this_month.return_value = 3
    repo.get_time_entries.return_value = []
    repo.count_orders_by_statuses.return_value = 4
    repo.get_overdue_orders.return_value = []
    repo.get_etd_today.return_value = []
    repo.item_delivery_snapshot.return_value = {
        "not_delivered": 1,
        "awaiting": 2,
    }
    repo.count_customers_created.return_value = 0
    repo.count_distinct_customers_with_orders.return_value = 0
    repo.count_repeat_customers_with_orders.return_value = 0
    repo.count_distinct_customers_invoiced.return_value = 0
    repo.get_completed_orders.return_value = []
    repo.count_items_created.return_value = 0
    repo.count_items_delivered.return_value = 0
    repo.sum_invoice_margin.return_value = 400
    repo.sum_payment_voucher_amount.return_value = 0

    service = BusinessInsightsReportService(
        repo,
        accounting_service=MagicMock(),
        vendor_service=MagicMock(),
        customer_service=MagicMock(),
    )
    rows = service.period_financial_summary(
        PeriodSummaryFilter(
            date_range=DateRange(date(2026, 1, 1), date(2026, 1, 31))
        )
    )
    assert rows
    assert all("metric" in row and "value" in row for row in rows)


def test_business_insights_top_customers_by_revenue_rollup():
    items = [
        {
            "customer_name": "Alice",
            "order_number": "O1",
            "sell_amount": 1000,
            "margin_amount": 400,
            "in_house_hours": 10,
        },
        {
            "customer_name": "Alice",
            "order_number": "O2",
            "sell_amount": 500,
            "margin_amount": 200,
            "in_house_hours": 5,
        },
        {
            "customer_name": "Bob",
            "order_number": "O3",
            "sell_amount": 800,
            "margin_amount": 300,
            "in_house_hours": 8,
        },
    ]
    repo = MagicMock()
    repo.get_item_profitability.return_value = items
    service = BusinessInsightsReportService(
        repo,
        accounting_service=MagicMock(),
        vendor_service=MagicMock(),
        customer_service=MagicMock(),
    )
    rows = service.top_customers_by_revenue(
        TopCustomersFilter(
            date_range=DateRange(date(2026, 1, 1), date(2026, 1, 31))
        )
    )
    alice = next(r for r in rows if r["customer_name"] == "Alice")
    assert alice["order_count"] == 2
    assert alice["total_revenue"] == 1500
    assert alice["total_margin"] == 600


def test_labor_worker_productivity_rollup():
    entries = [
        {
            "worker_name": "Ravi",
            "duration_minutes": 60,
            "order_number": "O1",
        },
        {
            "worker_name": "Ravi",
            "duration_minutes": 30,
            "order_number": "O2",
        },
        {
            "worker_name": "Sita",
            "duration_minutes": 120,
            "order_number": "O3",
        },
    ]
    service = LaborReportService(_FakeRepo(time_entries=entries))
    rows = service.worker_productivity_report(
        WorkerProductivityFilter(
            date_range=DateRange(date(2026, 1, 1), date(2026, 1, 31))
        )
    )
    ravi = next(r for r in rows if r["worker_name"] == "Ravi")
    assert ravi["total_hours"] == 1.5
    assert ravi["entry_count"] == 2
    assert ravi["order_count"] == 2


def test_operations_order_pipeline_filters_status():
    rows = [
        {"order_number": "O1", "order_status": "in_progress"},
        {"order_number": "O2", "order_status": "completed"},
    ]
    service = OperationsReportService(_FakeRepo(pipeline=rows))
    filtered = service.order_pipeline_report(
        OrderPipelineFilter(statuses=["in_progress"])
    )
    assert len(filtered) == 1
    assert filtered[0]["order_number"] == "O1"


def test_report_app_service_facade_delegates():
    repo = MagicMock()
    business = MagicMock()
    profitability = MagicMock()
    operations = MagicMock()
    labor = MagicMock()
    customers = MagicMock()
    facade = ReportAppService(
        repo, business, profitability, operations, labor, customers
    )

    facade.get_period_summary(date(2026, 1, 1), date(2026, 1, 31))
    business.get_period_summary.assert_called_once()

    filters = ItemProfitabilityFilter(
        date_range=DateRange(date(2026, 1, 1), date(2026, 1, 31))
    )
    facade.item_profitability_report(filters)
    profitability.item_profitability_report.assert_called_once_with(filters)

    facade.expense_report(filters)
    business.expense_detail_report.assert_called_once()
