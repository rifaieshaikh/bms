from datetime import date

import pytest

from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeVoucherRepository,
    make_inventory_app_service,
)
from tests.test_sales_workflow import (
    FakeBusinessService,
    FakeCustomerService,
    InMemoryDeliveryNoteRepository,
    InMemorySalesOrderRepository,
    InMemorySalesReturnRepository,
)
from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.sales.service import SalesAppService
from vaybooks.bms.domain.finance.accounting.entities import Account
from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.sales.invoice_lock import can_edit_invoice
from vaybooks.bms.domain.shared.document_customization import SalesPrintSettings
from vaybooks.bms.domain.shared.enums import (
    AccountType,
    PartyRegistrationType,
    QuotationStatus,
    SalesOrderStatus,
)
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import generate_sales_document_pdf


class InMemoryDocumentRepository:
    def __init__(self):
        self.store = {}

    def save(self, value):
        self.store[value.id] = value
        return value

    def find_by_id(self, value_id):
        return self.store.get(value_id)

    def find_by_number(self, number):
        return next(
            (
                value
                for value in self.store.values()
                if number
                in {
                    getattr(value, "estimate_number", None),
                    getattr(value, "quotation_number", None),
                }
            ),
            None,
        )

    def list_all(self):
        return list(self.store.values())

    def delete(self, value_id):
        self.store.pop(value_id, None)


def _stack(
    *,
    business: BusinessProfile | None = None,
    hsn_sac: str = "",
    gst_rate: float = 0.0,
    selling_rate: float = 100.0,
):
    accounts = FakeAccountRepository()
    customer = Account(
        account_name="Customer - Test",
        account_type=AccountType.ASSET,
        linked_customer_id="c1",
    )
    sales_account = Account(account_name="Sales", account_type=AccountType.REVENUE)
    cash = Account(
        account_name="Cash", account_type=AccountType.ASSET, is_store_account=True
    )
    for account in (customer, sales_account, cash):
        accounts.save(account)
    accounting = AccountingAppService(
        accounts, FakeVoucherRepository(), FakeCounterRepository()
    )
    inventory = make_inventory_app_service()
    category = inventory.create_category("Ready-made")
    product = inventory.create_product(
        "SKU-Q",
        "Quoted Item",
        category.id,
        opening_qty=20,
        hsn_sac=hsn_sac,
        selling_rate=selling_rate,
        gst_rate=gst_rate,
    )
    estimate_repo = InMemoryDocumentRepository()
    quotation_repo = InMemoryDocumentRepository()
    sales = SalesAppService(
        InMemorySalesOrderRepository(),
        InMemoryDeliveryNoteRepository(),
        InMemorySalesReturnRepository(),
        FakeCounterRepository(),
        accounting,
        inventory,
        customer_service=FakeCustomerService(),
        business_service=FakeBusinessService(
            business or BusinessProfile(legal_name="Test Biz")
        ),
        estimate_repo=estimate_repo,
        quotation_repo=quotation_repo,
    )
    return sales, product, cash, inventory


def _registered_business() -> BusinessProfile:
    return BusinessProfile(
        legal_name="Test Biz",
        gstin="27AAAAA0000A1Z5",
        state_code="27",
        registration_type=PartyRegistrationType.REGISTERED,
    )


def test_estimate_and_quotation_conversion_to_order():
    sales, product, _, _ = _stack()
    estimate = sales.create_estimate(
        customer_id="c1",
        estimate_date=date(2026, 7, 1),
        lines=[{"product_id": product.id, "qty": 2, "rate": 100}],
    )
    assert estimate.estimate_number.startswith("EST-")
    assert estimate.total_amount > 0

    quotation = sales.create_quotation(
        customer_id="c1",
        quotation_date=date(2026, 7, 1),
        lines=[{"product_id": product.id, "qty": 3, "rate": 100}],
        status=QuotationStatus.ACCEPTED,
    )
    order = sales.convert_quotation_to_sales_order(
        quotation.id, order_date=date(2026, 7, 2)
    )
    assert order.status == SalesOrderStatus.CONFIRMED
    assert order.lines[0].qty_ordered == 3
    assert sales.get_quotation(quotation.id).status == QuotationStatus.CONVERTED
    with pytest.raises(ValueError, match="accepted"):
        sales.convert_quotation_to_sales_order(quotation.id)


def test_registered_estimate_snapshots_gst_components():
    sales, product, _, _ = _stack(
        business=_registered_business(),
        hsn_sac="5208",
        gst_rate=18,
    )

    estimate = sales.create_estimate(
        customer_id="c1",
        estimate_date=date(2026, 7, 1),
        lines=[{"product_id": product.id, "qty": 2, "rate": 100}],
    )

    line = estimate.lines[0]
    assert line.hsn_sac == "5208"
    assert line.gst_rate == 18
    assert line.taxable_amount == 200
    assert line.cgst_amount == 18
    assert line.sgst_amount == 18
    assert estimate.tax_summary["grand_total"] == 236


def test_registered_estimate_requires_hsn_sac():
    sales, product, _, _ = _stack(
        business=_registered_business(),
        gst_rate=18,
    )

    with pytest.raises(ValueError, match="HSN/SAC is required"):
        sales.create_estimate(
            customer_id="c1",
            estimate_date=date(2026, 7, 1),
            lines=[{"product_id": product.id, "qty": 1, "rate": 100}],
        )


def test_registered_estimate_requires_selling_price():
    sales, product, _, _ = _stack(
        business=_registered_business(),
        hsn_sac="5208",
        gst_rate=18,
    )

    with pytest.raises(ValueError, match="Selling price is required"):
        sales.create_estimate(
            customer_id="c1",
            estimate_date=date(2026, 7, 1),
            lines=[{"product_id": product.id, "qty": 1, "rate": -1}],
        )


def test_registered_estimate_requires_gst_rate_configuration():
    sales, product, _, inventory = _stack(
        business=_registered_business(),
        hsn_sac="5208",
        gst_rate=0,
    )
    inventory.list_gst_rate_history = lambda _product_id: []

    with pytest.raises(ValueError, match="GST rate configuration is required"):
        sales.create_estimate(
            customer_id="c1",
            estimate_date=date(2026, 7, 1),
            lines=[{"product_id": product.id, "qty": 1, "rate": 100}],
        )


def test_sales_order_can_convert_directly_to_invoice():
    sales, product, cash, inventory = _stack()
    order = sales.create_sales_order(
        customer_id="c1",
        order_date=date.today(),
        lines=[{"product_id": product.id, "qty": 2, "rate": 100}],
    )
    voucher = sales.convert_sales_order_to_invoice(
        order.id,
        store_account_id=cash.id,
        store_invoice_number="DIRECT-1",
        amount_received=200,
    )
    assert voucher.reference_so_id == order.id
    assert sales.get_sales_order(order.id).lines[0].qty_invoiced == 2
    assert inventory.get_product(product.id).current_qty == 18
    with pytest.raises(ValueError, match="fully invoiced"):
        sales.convert_sales_order_to_invoice(
            order.id,
            store_account_id=cash.id,
            store_invoice_number="DIRECT-2",
        )
    sales.delete_sales_invoice(voucher.id)
    assert sales.get_sales_order(order.id).lines[0].qty_invoiced == 0
    assert inventory.get_product(product.id).current_qty == 20


def test_invoice_month_lock_uses_calendar_month():
    assert can_edit_invoice(date(2026, 7, 1), date(2026, 7, 31))
    assert not can_edit_invoice(date(2026, 7, 31), date(2026, 8, 1))
    assert not can_edit_invoice(date(2025, 12, 31), date(2026, 1, 1))


@pytest.mark.parametrize("paper", ["A4", "80mm", "58mm"])
def test_estimate_pdf_supports_regular_and_thermal_paper(paper):
    sales, product, _, _ = _stack()
    estimate = sales.create_estimate(
        customer_id="c1",
        estimate_date=date(2026, 7, 1),
        lines=[{"product_id": product.id, "qty": 2, "rate": 100}],
    )
    pdf = generate_sales_document_pdf(
        "estimate",
        estimate,
        BusinessProfile(legal_name="Test Business"),
        SalesPrintSettings(paper_size=paper),
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
