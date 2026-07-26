from datetime import date

from vaybooks.bms.application.crm.activities import CrmAutoActivityService
from vaybooks.bms.application.crm.enquiries import CrmEnquiryAppService
from vaybooks.bms.application.crm.leads import CrmLeadAppService
from tests.test_crm_foundation import (
    FakeActivityRepo,
    FakeAuditRepo,
    FakeCustomer,
    FakeCustomerService,
    FakeEnquiryRepo,
    FakeLeadRepo,
)
from tests.test_sales_workflow import _sales_stack


def test_lead_to_order_to_receipt_customer_timeline():
    leads = FakeLeadRepo()
    enquiries = FakeEnquiryRepo()
    activities = FakeActivityRepo()
    customers = FakeCustomerService()
    customers._by_id["c1"] = FakeCustomer(
        customer_name="Test Customer",
        phone_number="9999999999",
        id="c1",
    )
    lead_service = CrmLeadAppService(
        leads,
        audit_repo=FakeAuditRepo(),
        activity_repo=activities,
        customer_service=customers,
        enquiry_repo=enquiries,
    )
    enquiry_service = CrmEnquiryAppService(
        enquiries,
        activity_repo=activities,
        lead_repo=leads,
    )

    lead = lead_service.create_lead(
        name="Test Customer",
        phone="9999999999",
        assigned_user_id="rep-1",
    )
    enquiry = enquiry_service.create_enquiry(
        lead_id=lead.id,
        product_interest="Kurta",
    )
    converted = lead_service.link_to_customer(lead.id, "c1")
    assert enquiries.find_by_id(enquiry.id).customer_id == "c1"

    auto = CrmAutoActivityService(activities)
    sales, _inventory, product, customer_account, cash, accounting = _sales_stack()
    sales._crm_event_sink = auto
    accounting.set_crm_event_sink(auto)
    order = sales.create_sales_order(
        customer_id="c1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": product.name,
                "qty_ordered": 1,
                "rate": 1000,
            }
        ],
    )
    receipt = accounting.create_receipt(
        cash.id,
        customer_account.id,
        500,
        "Part payment",
        date.today(),
        order.id,
    )

    timeline = activities.list_timeline(customer_id=converted.customer_id)
    types = {activity.activity_type for activity in timeline}
    assert {
        "Enquiry Created",
        "Lead Converted",
        "Order Placed",
        "Payment Received",
    }.issubset(types)
    assert any(
        activity.source_txn_id == receipt.id
        for activity in timeline
        if activity.activity_type == "Payment Received"
    )
