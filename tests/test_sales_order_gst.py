"""Sales order rate defaulting, B2B/B2C classification, and GST snapshot."""

from datetime import date

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.sales.service import SalesAppService
from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.parties.customers.entities import Customer
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeVoucherRepository,
    make_inventory_app_service,
)
from tests.test_sales_workflow import (
    FakeBusinessService,
    InMemoryDeliveryNoteRepository,
    InMemorySalesOrderRepository,
    InMemorySalesReturnRepository,
)


class StubCustomerService:
    def __init__(self, customer: Customer):
        self._customer = customer

    def get_customer_detail(self, customer_id):
        return self._customer


def _make_customer(**kwargs) -> Customer:
    defaults = dict(customer_name="Cust", phone_number="9999999999", id="c1")
    defaults.update(kwargs)
    return Customer(**defaults)


def _make_sales(customer: Customer, business: BusinessProfile | None):
    accounting = AccountingAppService(
        FakeAccountRepository(), FakeVoucherRepository(), FakeCounterRepository()
    )
    inventory = make_inventory_app_service()
    category = inventory.create_category("Ready-made")
    product = inventory.create_product(
        "SKU-1",
        "Kurta",
        category.id,
        opening_qty=50,
        hsn_sac="5208",
        selling_rate=500.0,
        mrp=600.0,
        gst_rate=18.0,
    )
    sales = SalesAppService(
        InMemorySalesOrderRepository(),
        InMemoryDeliveryNoteRepository(),
        InMemorySalesReturnRepository(),
        FakeCounterRepository(),
        accounting,
        inventory,
        customer_service=StubCustomerService(customer),
        business_service=FakeBusinessService(business) if business else None,
    )
    return sales, product


def _registered_business(state_code: str = "27") -> BusinessProfile:
    return BusinessProfile(
        legal_name="Biz",
        gstin=f"{state_code}AAAAA0000A1Z5",
        state_code=state_code,
        registration_type=PartyRegistrationType.REGISTERED,
    )


def _composition_business(
    state_code: str = "27", rate: float = 1.0
) -> BusinessProfile:
    return BusinessProfile(
        legal_name="Composition Biz",
        gstin=f"{state_code}AAAAA0000A1Z5",
        state_code=state_code,
        registration_type=PartyRegistrationType.COMPOSITION,
        composition_tax_rate=rate,
    )


def _create_so(sales, product, rate: float = 0.0):
    return sales.create_sales_order(
        customer_id="c1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": "",
                "qty_ordered": 2,
                "rate": rate,
            }
        ],
    )


def test_rate_defaults_to_product_selling_rate():
    customer = _make_customer(state_code="27")
    sales, product = _make_sales(customer, _registered_business("27"))
    so = _create_so(sales, product, rate=0.0)
    assert so.lines[0].rate == 500.0
    assert so.lines[0].product_name == "Kurta"
    assert so.lines[0].hsn_sac == "5208"


def test_b2c_same_state_charges_cgst_sgst():
    customer = _make_customer(state_code="27")  # unregistered
    sales, product = _make_sales(customer, _registered_business("27"))
    so = _create_so(sales, product, rate=100.0)
    line = so.lines[0]
    assert so.supply_type == "B2C"
    assert line.taxable_amount == 200.0
    assert line.cgst_amount == 18.0
    assert line.sgst_amount == 18.0
    assert line.igst_amount == 0.0
    assert line.line_total == 236.0
    assert so.tax_summary["total_tax"] == 36.0


def test_b2c_without_customer_state_uses_business_state():
    customer = _make_customer(state_code="")  # walk-in, no state
    sales, product = _make_sales(customer, _registered_business("27"))
    so = _create_so(sales, product, rate=100.0)
    line = so.lines[0]
    assert so.supply_type == "B2C"
    assert line.cgst_amount == 18.0
    assert line.sgst_amount == 18.0
    assert line.igst_amount == 0.0


def test_b2b_inter_state_charges_igst():
    customer = _make_customer(
        state_code="29",
        gstin="29BBBBB0000B1Z5",
        registration_type=PartyRegistrationType.REGISTERED,
    )
    sales, product = _make_sales(customer, _registered_business("27"))
    so = _create_so(sales, product, rate=100.0)
    line = so.lines[0]
    assert so.supply_type == "B2B"
    assert line.igst_amount == 36.0
    assert line.cgst_amount == 0.0
    assert line.sgst_amount == 0.0
    assert line.line_total == 236.0


def test_b2b_same_state_charges_cgst_sgst():
    customer = _make_customer(
        state_code="27",
        gstin="27BBBBB0000B1Z5",
        registration_type=PartyRegistrationType.REGISTERED,
    )
    sales, product = _make_sales(customer, _registered_business("27"))
    so = _create_so(sales, product, rate=100.0)
    line = so.lines[0]
    assert so.supply_type == "B2B"
    assert line.cgst_amount == 18.0
    assert line.sgst_amount == 18.0
    assert line.igst_amount == 0.0


def test_union_territory_charges_cgst_utgst():
    customer = _make_customer(state_code="04")
    sales, product = _make_sales(customer, _registered_business("04"))
    so = _create_so(sales, product, rate=100.0)
    line = so.lines[0]
    assert line.cgst_amount == 18.0
    assert line.utgst_amount == 18.0
    assert line.sgst_amount == 0.0
    assert line.igst_amount == 0.0


def test_unregistered_business_charges_no_gst():
    customer = _make_customer(state_code="27")
    sales, product = _make_sales(customer, None)
    so = _create_so(sales, product, rate=100.0)
    line = so.lines[0]
    assert line.total_tax == 0.0
    assert line.line_total == 200.0
    assert so.tax_summary["total_tax"] == 0.0


def test_composition_business_uses_configured_rate_instead_of_product_rate():
    customer = _make_customer(state_code="27")
    sales, product = _make_sales(
        customer, _composition_business("27", rate=1.0)
    )
    so = _create_so(sales, product, rate=100.0)
    line = so.lines[0]
    assert line.gst_rate == 1.0
    assert line.taxable_amount == 200.0
    assert line.cgst_amount == 1.0
    assert line.sgst_amount == 1.0
    assert line.igst_amount == 0.0
    assert line.line_total == 202.0


def test_composition_business_uses_configured_interstate_igst():
    customer = _make_customer(state_code="29")
    sales, product = _make_sales(
        customer, _composition_business("27", rate=2.0)
    )
    so = _create_so(sales, product, rate=100.0)
    line = so.lines[0]
    assert line.gst_rate == 2.0
    assert line.igst_amount == 4.0
    assert line.cgst_amount == 0.0
    assert line.sgst_amount == 0.0


def test_so_line_discount_reduces_taxable_before_gst():
    customer = _make_customer(state_code="27")
    sales, product = _make_sales(customer, _registered_business("27"))
    so = sales.create_sales_order(
        customer_id="c1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": "",
                "qty_ordered": 2,
                "rate": 100.0,
                "discount": 20.0,
                "discount_mode": "flat",
                "discount_input": 20.0,
            }
        ],
    )
    line = so.lines[0]
    assert line.discount == 20.0
    assert line.taxable_amount == 180.0
    assert line.cgst_amount == 16.2
    assert line.sgst_amount == 16.2


def test_convert_sales_order_to_invoice_carries_line_discount(monkeypatch):
    customer = _make_customer(state_code="27")
    sales, product = _make_sales(customer, _registered_business("27"))
    so = sales.create_sales_order(
        customer_id="c1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "qty_ordered": 1,
                "rate": 200.0,
                "discount": 25.0,
                "discount_mode": "flat",
                "discount_input": 25.0,
            }
        ],
    )

    captured: dict = {}

    def _fake_create_sales_invoice(**kwargs):
        captured.update(kwargs)
        return type("V", (), {"id": "v1", "voucher_number": "SI-1"})()

    monkeypatch.setattr(sales, "create_sales_invoice", _fake_create_sales_invoice)
    monkeypatch.setattr(
        sales._accounting,
        "get_customer_account",
        lambda customer_id: type("A", (), {"id": "acct1"})(),
    )

    sales.convert_sales_order_to_invoice(
        so.id,
        store_account_id="store1",
        store_invoice_number="INV-1",
    )
    lines = captured.get("line_items") or []
    assert len(lines) == 1
    assert lines[0]["discount"] == 25.0
    assert lines[0]["discount_input"] == 25.0
    assert lines[0]["rate"] == 200.0
