from datetime import date

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.domain.finance.accounting.entities import Account
from vaybooks.bms.domain.shared.enums import AccountType
from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeVoucherRepository,
)
from tests.test_sales_workflow import _sales_stack


class EventSink:
    def __init__(self):
        self.events = []

    def record_source_event(self, *, event_type, **payload):
        self.events.append((event_type, payload))


def test_posted_receipt_and_void_publish_source_linked_events():
    accounts = FakeAccountRepository()
    cash = accounts.save(
        Account(account_name="Cash", account_type=AccountType.ASSET)
    )
    customer = accounts.save(
        Account(
            account_name="Customer - A",
            account_type=AccountType.ASSET,
            linked_customer_id="customer-1",
        )
    )
    sink = EventSink()
    service = AccountingAppService(
        accounts,
        FakeVoucherRepository(),
        FakeCounterRepository(),
        crm_event_sink=sink,
    )

    receipt = service.create_receipt(
        cash.id,
        customer.id,
        1250,
        "Collection follow-up",
        date.today(),
    )
    assert sink.events[-1][0] == "payment_received"
    assert sink.events[-1][1]["source_id"] == receipt.id
    assert sink.events[-1][1]["customer_id"] == "customer-1"
    assert sink.events[-1][1]["amount"] == 1250

    service.void_voucher(receipt.id)
    assert sink.events[-1][0] == "source_reversed"
    assert sink.events[-1][1]["source_id"] == receipt.id


def test_confirmed_order_and_cancellation_publish_crm_events():
    sales, _inventory, product, _customer_account, _cash, _accounting = (
        _sales_stack()
    )
    sink = EventSink()
    sales._crm_event_sink = sink

    order = sales.create_sales_order(
        customer_id="c1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": product.name,
                "qty_ordered": 2,
                "rate": 500,
            }
        ],
    )
    assert sink.events[-1][0] == "order_placed"
    assert sink.events[-1][1]["source_id"] == order.id

    sales.cancel_sales_order(order.id)
    assert sink.events[-1][0] == "source_reversed"
    assert sink.events[-1][1]["source_id"] == order.id


def test_posted_sales_invoice_and_reversal_publish_crm_events():
    sales, _inventory, product, _customer_account, cash, accounting = (
        _sales_stack()
    )
    sink = EventSink()
    sales._crm_event_sink = sink
    accounting.set_crm_event_sink(sink)
    order = sales.create_sales_order(
        customer_id="c1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": product.name,
                "qty_ordered": 1,
                "rate": 500,
            }
        ],
    )
    delivery = sales.create_delivery_note(
        customer_id="c1",
        delivery_date=date.today(),
        lines=[{"product_id": product.id, "qty_delivered": 1, "rate": 500}],
        sales_order_id=order.id,
        confirm=True,
    )
    invoice = sales.create_sales_invoice_from_dn(
        dn_id=delivery.id,
        store_account_id=cash.id,
        store_invoice_number="INV-CRM-1",
    )
    assert sink.events[-1][0] == "invoice_created"
    assert sink.events[-1][1]["source_id"] == invoice.id
    assert sink.events[-1][1]["customer_id"] == "c1"

    accounting.void_voucher(invoice.id)
    assert sink.events[-1][0] == "source_reversed"
    assert sink.events[-1][1]["source_id"] == invoice.id
