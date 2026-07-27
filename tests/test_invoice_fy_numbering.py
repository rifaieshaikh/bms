"""Sales invoice FY numbering and voucher financial_year tagging."""

from datetime import date

import pytest

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.purchases.service import PurchaseAppService
from vaybooks.bms.application.sales.service import SalesAppService
from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.finance.accounting.entities import Account
from vaybooks.bms.domain.finance.accounting.purchase_parsing import (
    purchase_row_from_voucher,
)
from vaybooks.bms.domain.finance.accounting.sales_parsing import sales_row_from_voucher
from vaybooks.bms.domain.shared.enums import AccountType, PartyRegistrationType, VoucherType
from vaybooks.bms.domain.shared.financial_year import (
    format_invoice_number,
    resolve_financial_year,
)
from vaybooks.bms.infrastructure.repositories.shared.mongo_business_profile_repository import (
    MongoBusinessProfileRepository,
)
from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeVoucherRepository,
    make_inventory_app_service,
)
from tests.test_purchase_workflow import (
    InMemoryGRNRepository,
    InMemoryPurchaseOrderRepository,
    InMemoryReturnRepository,
)
from tests.test_sales_workflow import (
    FakeBusinessService,
    FakeCustomerService,
    InMemoryDeliveryNoteRepository,
    InMemorySalesOrderRepository,
    InMemorySalesReturnRepository,
)


def test_resolve_financial_year_apr_mar_boundaries():
    assert resolve_financial_year(date(2026, 3, 31), 4) == "2025-26"
    assert resolve_financial_year(date(2026, 4, 1), 4) == "2026-27"
    assert resolve_financial_year(date(2026, 12, 15), 4) == "2026-27"


def test_format_invoice_number_replaces_fy_token():
    assert (
        format_invoice_number("INV/{FY}/", "2026-27", 1) == "INV/2026-27/0001"
    )
    assert (
        format_invoice_number("SI-{FY}-", "2025-26", 42) == "SI-2025-26-0042"
    )


def test_business_profile_missing_mode_defaults_external():
    repo = MongoBusinessProfileRepository.__new__(MongoBusinessProfileRepository)
    profile = repo._from_doc(
        {
            "_id": "default",
            "legal_name": "Legacy Biz",
        }
    )
    assert profile.invoice_numbering_mode == "external"
    assert profile.invoice_number_prefix == "INV/{FY}/"
    assert profile.fy_start_month == 4


def test_business_profile_new_defaults_app():
    profile = BusinessProfile(legal_name="New Biz")
    assert profile.invoice_numbering_mode == "app"


def _sales_stack(profile: BusinessProfile | None):
    accounts = FakeAccountRepository()
    customer_acct = Account(
        account_name="Customer - Test",
        account_type=AccountType.ASSET,
        linked_customer_id="c1",
    )
    sales_acct = Account(account_name="Sales", account_type=AccountType.REVENUE)
    cash = Account(
        account_name="Cash",
        account_type=AccountType.ASSET,
        is_store_account=True,
    )
    accounts.save(customer_acct)
    accounts.save(sales_acct)
    accounts.save(cash)
    accounting = AccountingAppService(
        accounts, FakeVoucherRepository(), FakeCounterRepository()
    )
    inventory = make_inventory_app_service()
    category = inventory.create_category("Ready-made")
    product = inventory.create_product(
        "SKU-1", "Kurta", category.id, opening_qty=20
    )
    counter = FakeCounterRepository()
    sales = SalesAppService(
        InMemorySalesOrderRepository(),
        InMemoryDeliveryNoteRepository(),
        InMemorySalesReturnRepository(),
        counter,
        accounting,
        inventory,
        customer_service=FakeCustomerService(),
        business_service=FakeBusinessService(profile) if profile is not None else None,
    )
    return sales, product, customer_acct, cash, counter


def test_app_mode_generates_invoice_number_and_stamps_fy():
    fy_date = date(2026, 5, 10)
    profile = BusinessProfile(
        legal_name="App Mode Biz",
        invoice_numbering_mode="app",
        invoice_number_prefix="INV/{FY}/",
        fy_start_month=4,
    )
    sales, product, customer_acct, cash, _ = _sales_stack(profile)
    voucher = sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=250,
        discount_amount=0,
        amount_received=250,
        store_invoice_number="",
        line_items=[
            {
                "product_id": product.id,
                "qty": 1,
                "rate": 250,
                "description": "Kurta",
            }
        ],
        voucher_date=fy_date,
    )
    assert voucher.financial_year == "2026-27"
    assert "Store invoice INV/2026-27/0001" in (voucher.description or "")
    row = sales_row_from_voucher(voucher)
    assert row["store_invoice_number"] == "INV/2026-27/0001"
    assert row["financial_year"] == "2026-27"

    second = sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=250,
        discount_amount=0,
        amount_received=250,
        store_invoice_number="",
        line_items=[
            {
                "product_id": product.id,
                "qty": 1,
                "rate": 250,
                "description": "Kurta",
            }
        ],
        voucher_date=fy_date,
    )
    assert "Store invoice INV/2026-27/0002" in (second.description or "")


def test_external_mode_rejects_empty_number():
    profile = BusinessProfile(
        legal_name="External Biz",
        invoice_numbering_mode="external",
    )
    sales, product, customer_acct, cash, _ = _sales_stack(profile)
    with pytest.raises(ValueError, match="Store invoice number is required"):
        sales.create_direct_sale(
            customer_account_id=customer_acct.id,
            store_account_id=cash.id,
            gross_amount=100,
            discount_amount=0,
            amount_received=100,
            store_invoice_number="  ",
            line_items=[
                {
                    "product_id": product.id,
                    "qty": 1,
                    "rate": 100,
                    "description": "Kurta",
                }
            ],
            voucher_date=date(2026, 6, 1),
        )


def test_external_mode_keeps_manual_number_and_stamps_fy():
    profile = BusinessProfile(
        legal_name="External Biz",
        invoice_numbering_mode="external",
        fy_start_month=4,
    )
    sales, product, customer_acct, cash, _ = _sales_stack(profile)
    voucher = sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=100,
        discount_amount=0,
        amount_received=100,
        store_invoice_number="POS-99",
        line_items=[
            {
                "product_id": product.id,
                "qty": 1,
                "rate": 100,
                "description": "Kurta",
            }
        ],
        voucher_date=date(2026, 3, 15),
    )
    assert voucher.financial_year == "2025-26"
    row = sales_row_from_voucher(voucher)
    assert row["store_invoice_number"] == "POS-99"


def test_preview_next_sales_invoice_number():
    profile = BusinessProfile(
        legal_name="App Mode Biz",
        invoice_numbering_mode="app",
    )
    sales, _, _, _, counter = _sales_stack(profile)
    preview = sales.preview_next_sales_invoice_number(date(2026, 4, 2))
    assert preview == "INV/2026-27/0001"
    assert counter.peek_next_value("sales_invoice_number:2026-27") == 1


def test_purchase_bill_create_stamps_fy():
    accounts = FakeAccountRepository()
    vendor = Account(
        account_name="Vendor A",
        account_type=AccountType.LIABILITY,
        linked_vendor_id="v1",
    )
    expense = Account(
        account_name="Material Purchase Expense",
        account_type=AccountType.EXPENSE,
    )
    cash = Account(
        account_name="Cash",
        account_type=AccountType.ASSET,
        is_store_account=True,
    )
    accounts.save(vendor)
    accounts.save(expense)
    accounts.save(cash)
    accounting = AccountingAppService(
        accounts, FakeVoucherRepository(), FakeCounterRepository()
    )
    inventory = make_inventory_app_service()
    profile = BusinessProfile(
        legal_name="Buy Biz",
        fy_start_month=4,
        registration_type=PartyRegistrationType.UNREGISTERED,
    )
    purchases = PurchaseAppService(
        InMemoryPurchaseOrderRepository(),
        InMemoryGRNRepository(),
        InMemoryReturnRepository(),
        FakeCounterRepository(),
        accounting,
        inventory,
        business_service=FakeBusinessService(profile),
    )
    voucher = purchases.create_purchase_bill(
        vendor_account_id=vendor.id,
        expense_lines=[
            {
                "expense_account_id": expense.id,
                "amount": 500.0,
                "line_total": 500.0,
                "taxable_amount": 500.0,
            }
        ],
        vendor_bill_number="VB-1",
        voucher_date=date(2026, 4, 5),
    )
    assert voucher.financial_year == "2026-27"
    row = purchase_row_from_voucher(voucher)
    assert row["financial_year"] == "2026-27"


def test_sales_row_derives_fy_when_voucher_blank():
    from vaybooks.bms.domain.finance.accounting.entities import Voucher, VoucherLine
    from vaybooks.bms.domain.shared.enums import VoucherType

    voucher = Voucher(
        voucher_number="VCH-1",
        voucher_type=VoucherType.SALES_INVOICE,
        voucher_date=date(2026, 4, 1),
        description="Store invoice LEGACY-1",
        financial_year="",
        lines=[
            VoucherLine(
                account_id="c1",
                account_name="Customer",
                debit_amount=100,
                credit_amount=0,
                description="Customer receivable",
            ),
            VoucherLine(
                account_id="s1",
                account_name="Sales",
                debit_amount=0,
                credit_amount=100,
                description="Sales",
            ),
        ],
    )
    row = sales_row_from_voucher(voucher)
    assert row["financial_year"] == "2026-27"


def test_accounting_auto_stamps_fy_on_boutique_sales_invoice():
    from vaybooks.bms.domain.shared.enums import VoucherType

    accounts = FakeAccountRepository()
    customer = Account(
        account_name="Customer - Test",
        account_type=AccountType.ASSET,
        linked_customer_id="c1",
    )
    income = Account(
        account_name="Customization", account_type=AccountType.REVENUE
    )
    accounts.save(customer)
    accounts.save(income)
    profile = BusinessProfile(legal_name="Biz", fy_start_month=4)
    accounting = AccountingAppService(
        accounts, FakeVoucherRepository(), FakeCounterRepository()
    )
    accounting.set_business_service(FakeBusinessService(profile))
    voucher = accounting.create_sales_invoice(
        customer.id,
        income.id,
        amount=1000,
        description="Invoice INV-1 - O-1",
        voucher_date=date(2026, 3, 20),
        voucher_type=VoucherType.CUSTOMIZATION_INVOICE,
    )
    assert voucher.financial_year == "2025-26"


def test_boutique_generate_invoice_stamps_fy():
    from vaybooks.bms.application.boutique.invoices.service import InvoiceAppService
    from vaybooks.bms.domain.boutique.orders.entities import (
        CustomizationItem,
        CustomizationOrder,
    )
    from vaybooks.bms.domain.shared.enums import OrderStatus
    from tests.conftest import FakeExpenseRepository, FakeInvoiceRepository, FakeOrderRepository

    accounts = FakeAccountRepository()
    customer = Account(
        account_name="Customer - Test",
        account_type=AccountType.ASSET,
        linked_customer_id="cust-1",
    )
    income = Account(
        account_name="Customization", account_type=AccountType.REVENUE
    )
    accounts.save(customer)
    accounts.save(income)
    accounting = AccountingAppService(
        accounts, FakeVoucherRepository(), FakeCounterRepository()
    )
    accounting.set_business_service(
        FakeBusinessService(BusinessProfile(legal_name="Biz", fy_start_month=4))
    )
    order_repo = FakeOrderRepository()
    order = CustomizationOrder(
        id="O-1",
        order_number="O-1",
        customer_id="cust-1",
        customer_name="Test",
        phone_number="9999999999",
        order_date=date(2026, 5, 1),
        expected_delivery_date=date(2026, 5, 10),
        order_status=OrderStatus.IN_PROGRESS,
        customization_items=[
            CustomizationItem(
                item_id="bill-1",
                bill_number="B1",
                description="Blouse",
                sell_amount=1000.0,
            )
        ],
    )
    order_repo.save(order)
    invoices = InvoiceAppService(
        FakeInvoiceRepository(),
        order_repo,
        FakeExpenseRepository(),
        FakeCounterRepository(),
        accounting_service=accounting,
    )
    invoice = invoices.record_invoice(
        order_id=order.id,
        invoice_number="BINV-1",
        bill_ids=["bill-1"],
        invoice_amount=1000.0,
        invoice_date=date(2026, 5, 2),
        post_entry=False,
    )
    assert invoice.financial_year == "2026-27"

    # Linked voucher path stamps FY via AccountingAppService auto-apply.
    voucher = accounting.create_sales_invoice(
        customer.id,
        income.id,
        amount=1000,
        description=f"Invoice {invoice.invoice_number} - {order.order_number}",
        voucher_date=invoice.invoice_date,
        reference_order_id=order.id,
        reference_invoice_id=invoice.id,
        voucher_type=VoucherType.CUSTOMIZATION_INVOICE,
    )
    assert voucher.financial_year == "2026-27"

def test_production_journal_gets_fy():
    accounts = FakeAccountRepository()
    wip = Account(account_name="WIP", account_type=AccountType.ASSET)
    raw = Account(account_name="Raw Materials", account_type=AccountType.ASSET)
    accounts.save(wip)
    accounts.save(raw)
    accounting = AccountingAppService(
        accounts, FakeVoucherRepository(), FakeCounterRepository()
    )
    accounting.set_business_service(
        FakeBusinessService(BusinessProfile(legal_name="Biz", fy_start_month=4))
    )
    voucher = accounting.create_journal_entry(
        description="Production batch",
        lines=[
            {
                "account_id": wip.id,
                "account_name": wip.account_name,
                "debit_amount": 100,
                "credit_amount": 0,
                "description": "WIP",
            },
            {
                "account_id": raw.id,
                "account_name": raw.account_name,
                "debit_amount": 0,
                "credit_amount": 100,
                "description": "Raw",
            },
        ],
        voucher_date=date(2026, 4, 10),
    )
    assert voucher.financial_year == "2026-27"


def test_project_ra_and_proforma_stamp_fy():
    from vaybooks.bms.application.projects.billing.service import ProjectBillingAppService
    from vaybooks.bms.domain.projects.entities import Project
    from vaybooks.bms.domain.shared.enums import ProjectStatus

    class FakeProjectRepo:
        def __init__(self, project):
            self._project = project

        def find_by_id(self, project_id):
            return self._project if self._project.id == project_id else None

    class FakeRARepo:
        def __init__(self):
            self._store = {}

        def save(self, ra):
            self._store[ra.id] = ra
            return ra

        def list_by_project(self, project_id):
            return [r for r in self._store.values() if r.project_id == project_id]

    class FakeProformaRepo:
        def __init__(self):
            self._store = {}

        def save(self, proforma):
            self._store[proforma.id] = proforma
            return proforma

        def list_by_project(self, project_id):
            return [p for p in self._store.values() if p.project_id == project_id]

    project = Project(
        id="prj-1",
        project_number="PRJ-1",
        name="Tower",
        customer_id="c1",
        customer_name="Client",
        status=ProjectStatus.ACTIVE,
    )
    accounting = AccountingAppService(
        FakeAccountRepository(), FakeVoucherRepository(), FakeCounterRepository()
    )
    accounting.set_business_service(
        FakeBusinessService(BusinessProfile(legal_name="Biz", fy_start_month=4))
    )
    billing = ProjectBillingAppService(
        FakeProjectRepo(project),
        work_order_repo=None,
        counter_repo=FakeCounterRepository(),
        accounting_service=accounting,
        ra_repo=FakeRARepo(),
        proforma_repo=FakeProformaRepo(),
    )
    ra = billing.create_ra_bill(
        project.id, claim_amount=5000, ra_date=date(2026, 4, 15)
    )
    assert ra.financial_year == "2026-27"
    proforma = billing.create_proforma(
        project.id,
        proforma_date=date(2026, 3, 1),
        amount=2000,
        description="Advance bill",
    )
    assert proforma.financial_year == "2025-26"
