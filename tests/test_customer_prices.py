"""Customer price history recording and lookup."""

from datetime import date, datetime

from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.sales_app_service import SalesAppService
from vaybooks.bms.domain.accounting.entities import Account
from vaybooks.bms.domain.sales.customer_prices import CustomerPriceEntry
from vaybooks.bms.domain.shared.enums import AccountType
from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeVoucherRepository,
    make_inventory_app_service,
)
from tests.test_sales_workflow import (
    FakeCustomerService,
    InMemoryDeliveryNoteRepository,
    InMemorySalesOrderRepository,
    InMemorySalesReturnRepository,
)


class FakeCustomerPriceRepository:
    def __init__(self):
        self._store = {}

    def save(self, row: CustomerPriceEntry) -> CustomerPriceEntry:
        self._store[row.id] = row
        return row

    def latest(self, customer_id: str, product_id: str):
        matches = [
            row
            for row in self._store.values()
            if row.customer_id == customer_id and row.product_id == product_id
        ]
        if not matches:
            return None
        matches.sort(
            key=lambda row: (
                row.effective_date or date.min,
                row.created_at or datetime.min,
            ),
            reverse=True,
        )
        return matches[0]

    def list_for_pair(self, customer_id: str, product_id: str, *, limit: int = 50):
        matches = [
            row
            for row in self._store.values()
            if row.customer_id == customer_id and row.product_id == product_id
        ]
        matches.sort(
            key=lambda row: (
                row.effective_date or date.min,
                row.created_at or datetime.min,
            ),
            reverse=True,
        )
        return matches[:limit]

    def list_all(self, *, limit: int = 500):
        rows = list(self._store.values())
        rows.sort(
            key=lambda row: (
                row.effective_date or date.min,
                row.created_at or datetime.min,
            ),
            reverse=True,
        )
        return rows[:limit]

    def delete_by_voucher(self, voucher_id: str) -> int:
        to_delete = [
            key
            for key, row in self._store.items()
            if row.voucher_id == voucher_id
        ]
        for key in to_delete:
            del self._store[key]
        return len(to_delete)


def _sales_with_prices():
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
        "SKU-1", "Kurta", category.id, opening_qty=50, selling_rate=200
    )
    price_repo = FakeCustomerPriceRepository()
    sales = SalesAppService(
        InMemorySalesOrderRepository(),
        InMemoryDeliveryNoteRepository(),
        InMemorySalesReturnRepository(),
        FakeCounterRepository(),
        accounting,
        inventory,
        customer_service=FakeCustomerService(),
        customer_price_repo=price_repo,
    )
    return sales, inventory, product, customer_acct, cash, price_repo


def test_first_invoice_records_customer_price():
    sales, _, product, customer_acct, cash, repo = _sales_with_prices()
    voucher = sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=250,
        discount_amount=0,
        amount_received=250,
        store_invoice_number="CP-1",
        line_items=[
            {"product_id": product.id, "qty": 1, "rate": 250, "description": "Kurta"}
        ],
    )
    assert len(repo._store) == 1
    entry = next(iter(repo._store.values()))
    assert entry.customer_id == "c1"
    assert entry.product_id == product.id
    assert entry.rate == 250
    assert entry.voucher_id == voucher.id
    assert entry.store_invoice_number == "CP-1"
    assert sales.get_customer_rate("c1", product.id) == 250


def test_same_rate_second_invoice_skips_record():
    sales, _, product, customer_acct, cash, repo = _sales_with_prices()
    sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=250,
        discount_amount=0,
        amount_received=250,
        store_invoice_number="CP-1",
        line_items=[
            {"product_id": product.id, "qty": 1, "rate": 250, "description": "Kurta"}
        ],
    )
    sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=500,
        discount_amount=0,
        amount_received=500,
        store_invoice_number="CP-2",
        line_items=[
            {"product_id": product.id, "qty": 2, "rate": 250, "description": "Kurta"}
        ],
    )
    assert len(repo._store) == 1


def test_changed_rate_appends_customer_price():
    sales, _, product, customer_acct, cash, repo = _sales_with_prices()
    sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=250,
        discount_amount=0,
        amount_received=250,
        store_invoice_number="CP-1",
        line_items=[
            {"product_id": product.id, "qty": 1, "rate": 250, "description": "Kurta"}
        ],
    )
    sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=300,
        discount_amount=0,
        amount_received=300,
        store_invoice_number="CP-2",
        line_items=[
            {"product_id": product.id, "qty": 1, "rate": 300, "description": "Kurta"}
        ],
    )
    assert len(repo._store) == 2
    assert sales.get_customer_rate("c1", product.id) == 300


def test_update_sales_invoice_reconciles_customer_prices():
    sales, _, product, customer_acct, cash, repo = _sales_with_prices()
    voucher = sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=250,
        discount_amount=0,
        amount_received=250,
        store_invoice_number="CP-1",
        line_items=[
            {"product_id": product.id, "qty": 1, "rate": 250, "description": "Kurta"}
        ],
    )
    assert len(repo._store) == 1
    sales.update_sales_invoice(
        voucher.id,
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        store_invoice_number="CP-1",
        line_items=[
            {"product_id": product.id, "qty": 1, "rate": 275, "description": "Kurta"}
        ],
        amount_received=275,
        voucher_date=date.today(),
    )
    assert len(repo._store) == 1
    entry = next(iter(repo._store.values()))
    assert entry.rate == 275
    assert entry.voucher_id == voucher.id
    assert sales.get_customer_rate("c1", product.id) == 275


def test_delete_sales_invoice_removes_customer_prices():
    sales, _, product, customer_acct, cash, repo = _sales_with_prices()
    voucher = sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=250,
        discount_amount=0,
        amount_received=250,
        store_invoice_number="CP-1",
        line_items=[
            {"product_id": product.id, "qty": 1, "rate": 250, "description": "Kurta"}
        ],
    )
    assert len(repo._store) == 1
    sales.delete_sales_invoice(voucher.id)
    assert len(repo._store) == 0
    assert sales.get_customer_rate("c1", product.id) is None


def test_get_customer_rate_prefers_history_over_selling_price():
    sales, inventory, product, customer_acct, cash, _ = _sales_with_prices()
    assert product.selling_rate == 200
    assert sales.get_customer_rate("c1", product.id) is None
    sales.create_direct_sale(
        customer_account_id=customer_acct.id,
        store_account_id=cash.id,
        gross_amount=180,
        discount_amount=0,
        amount_received=180,
        store_invoice_number="CP-1",
        line_items=[
            {"product_id": product.id, "qty": 1, "rate": 180, "description": "Kurta"}
        ],
    )
    assert sales.get_customer_rate("c1", product.id) == 180
    assert inventory.get_product(product.id).selling_rate == 200


def test_get_customer_rate_without_history_returns_none():
    sales, _, product, _, _, _ = _sales_with_prices()
    assert sales.get_customer_rate("c1", product.id) is None
    assert sales.get_customer_rate("", product.id) is None
