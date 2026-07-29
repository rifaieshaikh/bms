from datetime import date, datetime, timedelta
from types import SimpleNamespace

from vaybooks.bms.application.crm.dashboard import CrmDashboardAppService
from vaybooks.bms.application.crm.reports import CrmReportFilters, CrmReportService
from vaybooks.bms.domain.crm.entities import CrmActivity, CrmLead
from tests.test_crm_foundation import (
    FakeActivityRepo,
    FakeCustomer,
    FakeCustomerService,
    FakeEnquiryRepo,
    FakeLeadRepo,
)


class FakeSales:
    def __init__(self, orders):
        self.orders = orders

    def list_sales_orders(self):
        return list(self.orders)


class FakeAccounting:
    def __init__(self, balances):
        self.balances = balances

    def customer_balances_by_customer(self):
        return dict(self.balances)


def _order(customer_id: str, when: date, amount: float, qty: float = 1):
    return SimpleNamespace(
        id=f"so-{customer_id}-{when}",
        customer_id=customer_id,
        customer_name="Acme",
        order_date=when,
        total_amount=amount,
        location_name="Main",
        branch="",
        lines=[SimpleNamespace(qty_ordered=qty)],
    )


def test_order_and_outstanding_reports_use_live_transaction_data():
    leads = FakeLeadRepo()
    customers = FakeCustomerService()
    customer = FakeCustomer("Acme", "9876543210", assigned_user_name="Rep")
    customers._by_id[customer.id] = customer
    orders = [
        _order(customer.id, date.today(), 1000, 2),
        _order(customer.id, date.today(), 500, 1),
    ]
    reports = CrmReportService(
        leads,
        enquiry_repo=FakeEnquiryRepo(),
        activity_repo=FakeActivityRepo(),
        customer_service=customers,
        sales_service=FakeSales(orders),
        accounting_service=FakeAccounting({customer.id: 750}),
    )

    ordered = reports.run_report(
        "customers_with_orders",
        CrmReportFilters(
            date_from=datetime.combine(date.today(), datetime.min.time()),
            date_to=datetime.combine(date.today(), datetime.max.time()),
        ),
    )
    assert ordered.rows[0]["order_count"] == 2
    assert ordered.rows[0]["quantity"] == 3
    assert ordered.rows[0]["sales_value"] == 1500

    outstanding = reports.run_report(
        "customers_with_outstanding_balance_and_no_collection_activity"
    )
    assert outstanding.rows == [
        {
            "customer_id": customer.id,
            "customer_name": "Acme",
            "assigned_user": "Rep",
            "outstanding_balance": 750.0,
        }
    ]


def test_dashboard_exposes_attention_and_transaction_metrics():
    leads = FakeLeadRepo()
    lead = CrmLead(
        name="Priority prospect",
        priority="High",
        customer_id="customer-1",
        status="Converted",
        converted_at=datetime.utcnow(),
    )
    leads.save(lead)
    activities = FakeActivityRepo()
    activities.save(
        CrmActivity(
            activity_type="Called",
            customer_id="customer-1",
            assigned_user_id="rep-1",
            activity_at=datetime.utcnow() - timedelta(days=1),
            status="Completed",
            origin="Manual",
        )
    )
    from vaybooks.bms.domain.shared.date_utils import utc_now

    service = CrmDashboardAppService(
        leads,
        enquiry_repo=FakeEnquiryRepo(),
        activity_repo=activities,
        sales_service=FakeSales(
            [_order("customer-1", utc_now().date(), 1000)]
        ),
        accounting_service=FakeAccounting({"customer-1": 400}),
    )
    snapshot = service.snapshot()
    assert snapshot.leads_converted_in_period == 1
    assert snapshot.orders_generated_from_crm_leads == 1
    assert snapshot.customers_with_outstanding_balances[0][
        "outstanding_balance"
    ] == 400
