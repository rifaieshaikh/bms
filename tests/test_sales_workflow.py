"""End-to-end sales workflow tests."""

from datetime import date

from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.sales_app_service import SalesAppService
from vaybooks.bms.domain.accounting.entities import Account
from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.shared.enums import (
    AccountType,
    DeliveryNoteStatus,
    PartyRegistrationType,
    SalesOrderStatus,
    StockMovementType,
    VoucherType,
)
from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeVoucherRepository,
    make_inventory_app_service,
)


class InMemorySalesOrderRepository:
    def __init__(self):
        self._store = {}

    def save(self, order):
        self._store[order.id] = order
        return order

    def find_by_id(self, order_id):
        return self._store.get(order_id)

    def find_by_so_number(self, so_number):
        return next(
            (o for o in self._store.values() if o.so_number == so_number), None
        )

    def list_all(self):
        return list(self._store.values())

    def delete(self, order_id):
        self._store.pop(order_id, None)


class InMemoryDeliveryNoteRepository:
    def __init__(self):
        self._store = {}

    def save(self, dn):
        self._store[dn.id] = dn
        return dn

    def find_by_id(self, dn_id):
        return self._store.get(dn_id)

    def find_by_dn_number(self, dn_number):
        return next(
            (d for d in self._store.values() if d.dn_number == dn_number), None
        )

    def list_all(self):
        return list(self._store.values())

    def list_by_so(self, sales_order_id):
        return [d for d in self._store.values() if d.sales_order_id == sales_order_id]

    def delete(self, dn_id):
        self._store.pop(dn_id, None)


class InMemorySalesReturnRepository:
    def __init__(self):
        self._store = {}

    def save(self, sales_return):
        self._store[sales_return.id] = sales_return
        return sales_return

    def find_by_id(self, return_id):
        return self._store.get(return_id)

    def list_all(self):
        return list(self._store.values())

    def delete(self, return_id):
        self._store.pop(return_id, None)


class FakeCustomerService:
    def get_customer_detail(self, customer_id):
        return Customer(
            customer_name="Test Customer",
            phone_number="9999999999",
            id=customer_id or "c1",
            state_code="27",
        )


class FakeBusinessService:
    def __init__(self, profile: BusinessProfile | None = None):
        self._profile = profile or BusinessProfile(
            legal_name="Test Biz",
            gstin="27AAAAA0000A1Z5",
            state_code="27",
            registration_type=PartyRegistrationType.REGISTERED,
        )

    def get_profile(self):
        return self._profile


def _sales_stack(*, registered_business: bool = False):
    accounts = FakeAccountRepository()
    customer_acct = Account(
        account_name="Customer - Test",
        account_type=AccountType.ASSET,
        linked_customer_id="c1",
    )
    sales_acct = Account(
        account_name="Sales",
        account_type=AccountType.REVENUE,
    )
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
    product_kwargs: dict = {"opening_qty": 20}
    if registered_business:
        product_kwargs.update(hsn_sac="5208", gst_rate=18.0)
    product = inventory.create_product(
        "SKU-1", "Kurta", category.id, **product_kwargs
    )

    sales = SalesAppService(
        InMemorySalesOrderRepository(),
        InMemoryDeliveryNoteRepository(),
        InMemorySalesReturnRepository(),
        FakeCounterRepository(),
        accounting,
        inventory,
        customer_service=FakeCustomerService(),
        business_service=FakeBusinessService() if registered_business else None,
    )
    return sales, inventory, product, customer_acct, cash, accounting


def test_so_to_dn_to_invoice_flow():
    sales, inventory, product, customer_acct, cash, _ = _sales_stack()

    so = sales.create_sales_order(
        customer_id="c1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": product.name,
                "qty_ordered": 10,
                "rate": 100,
            }
        ],
    )
    assert so.status == SalesOrderStatus.CONFIRMED

    dn = sales.create_delivery_note(
        customer_id="c1",
        delivery_date=date.today(),
        lines=[{"product_id": product.id, "qty_delivered": 4, "rate": 100}],
        sales_order_id=so.id,
        confirm=True,
    )
    assert dn.status == DeliveryNoteStatus.DELIVERED
    updated_so = sales.get_sales_order(so.id)
    assert updated_so.status == SalesOrderStatus.PARTIALLY_DELIVERED
    assert inventory.get_product(product.id).current_qty == 16

    voucher = sales.create_sales_invoice_from_dn(
        dn_id=dn.id,
        store_account_id=cash.id,
        store_invoice_number="INV-1",
        amount_received=400,
    )
    assert voucher.voucher_type == VoucherType.SALES_INVOICE
    assert voucher.reference_dn_id == dn.id
    assert voucher.reference_so_id == so.id
    assert inventory.get_product(product.id).current_qty == 16

    rows = sales.list_sales_invoices()
    assert any(row["id"] == voucher.id for row in rows)


def test_direct_sale_deducts_stock():
    sales, inventory, product, customer_acct, cash, _ = _sales_stack()

    sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=500,
        discount_amount=0,
        amount_received=500,
        store_invoice_number="POS-1",
        line_items=[
            {"product_id": product.id, "qty": 2, "rate": 250, "description": "Kurta"}
        ],
    )
    assert inventory.get_product(product.id).current_qty == 18


def test_sales_return_restores_stock():
    sales, inventory, product, customer_acct, cash, _ = _sales_stack()

    sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=300,
        discount_amount=0,
        amount_received=300,
        store_invoice_number="POS-2",
        line_items=[
            {"product_id": product.id, "qty": 3, "rate": 100, "description": "Kurta"}
        ],
    )
    assert inventory.get_product(product.id).current_qty == 17

    ret = sales.create_sales_return(
        customer_id="c1",
        return_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": product.name,
                "qty": 1,
                "rate": 100,
            }
        ],
        amount_refunded=100,
        refund_account_id=cash.id,
    )
    assert ret.voucher_id
    assert inventory.get_product(product.id).current_qty == 18
    ledger = inventory.get_product_ledger(product.id)
    return_rows = [
        r for r in ledger if r["movement_type"] == StockMovementType.SALES_RETURN.value
    ]
    assert len(return_rows) == 1


def test_registered_business_invoice_posts_output_gst():
    from vaybooks.bms.domain.shared.india import (
        CGST_OUTPUT_ACCOUNT_NAME,
        IGST_OUTPUT_ACCOUNT_NAME,
        SGST_OUTPUT_ACCOUNT_NAME,
    )

    sales, inventory, product, customer_acct, cash, accounting = _sales_stack(
        registered_business=True
    )
    for name in (
        CGST_OUTPUT_ACCOUNT_NAME,
        SGST_OUTPUT_ACCOUNT_NAME,
        IGST_OUTPUT_ACCOUNT_NAME,
    ):
        accounting._account_repo.save(
            Account(account_name=name, account_type=AccountType.LIABILITY)
        )

    voucher = sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=0,
        discount_amount=0,
        amount_received=1180,
        store_invoice_number="GST-1",
        line_items=[
            {
                "product_id": product.id,
                "qty": 1,
                "rate": 1000,
                "description": "Kurta",
            }
        ],
    )

    sales_line = next(
        line for line in voucher.lines if line.description == "Sales invoice"
    )
    assert sales_line.credit_amount == 1000.0
    cgst_line = next(
        line for line in voucher.lines if line.description == "CGST output"
    )
    assert cgst_line.credit_amount == 90.0
    customer_line = voucher.lines[0]
    assert customer_line.debit_amount == 1180.0
