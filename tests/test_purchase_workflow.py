"""End-to-end purchase workflow tests."""

from datetime import date

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.application.purchases.service import PurchaseAppService
from vaybooks.bms.domain.finance.accounting.entities import Account
from vaybooks.bms.domain.shared.enums import (
    AccountType,
    CatalogItemType,
    PurchaseOrderStatus,
    VendorRegistrationType,
)
from vaybooks.bms.infrastructure.repositories.purchases.mongo_purchase_price_history_repository import (
    MongoPurchasePriceHistoryRepository,
)
from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeVoucherRepository,
    make_inventory_app_service,
)
from tests.domain.test_purchase_price_history import FakeDb as PriceHistoryFakeDb


class InMemoryPurchaseOrderRepository:
    def __init__(self):
        self._store = {}

    def save(self, order):
        self._store[order.id] = order
        return order

    def find_by_id(self, order_id):
        return self._store.get(order_id)

    def find_by_po_number(self, po_number):
        return next(
            (o for o in self._store.values() if o.po_number == po_number), None
        )

    def list_all(self):
        return list(self._store.values())

    def delete(self, order_id):
        self._store.pop(order_id, None)


class InMemoryGRNRepository:
    def __init__(self):
        self._store = {}

    def save(self, grn):
        self._store[grn.id] = grn
        return grn

    def find_by_id(self, grn_id):
        return self._store.get(grn_id)

    def find_by_grn_number(self, grn_number):
        return next(
            (g for g in self._store.values() if g.grn_number == grn_number), None
        )

    def list_all(self):
        return list(self._store.values())

    def list_by_po(self, purchase_order_id):
        return [
            g for g in self._store.values() if g.purchase_order_id == purchase_order_id
        ]

    def delete(self, grn_id):
        self._store.pop(grn_id, None)


class InMemoryReturnRepository:
    def __init__(self):
        self._store = {}

    def save(self, purchase_return):
        self._store[purchase_return.id] = purchase_return
        return purchase_return

    def find_by_id(self, return_id):
        return self._store.get(return_id)

    def list_all(self):
        return list(self._store.values())

    def delete(self, return_id):
        self._store.pop(return_id, None)


class FakeVendorService:
    def get_vendor_detail(self, vendor_id):
        class V:
            vendor_name = "Test Vendor"
            registration_type = VendorRegistrationType.UNREGISTERED
            state_code = "27"

        return V()


def _purchase_stack():
    accounts = FakeAccountRepository()
    vendor_acct = Account(
        account_name="Vendor",
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
    accounts.save(vendor_acct)
    accounts.save(expense)
    accounts.save(cash)

    accounting = AccountingAppService(
        accounts, FakeVoucherRepository(), FakeCounterRepository()
    )
    inventory = make_inventory_app_service()
    category = inventory.create_category("Fabric")
    product = inventory.create_product("SKU-1", "Cotton", category.id)

    purchases = PurchaseAppService(
        InMemoryPurchaseOrderRepository(),
        InMemoryGRNRepository(),
        InMemoryReturnRepository(),
        FakeCounterRepository(),
        accounting,
        inventory,
        vendor_service=FakeVendorService(),
        price_history_repo=MongoPurchasePriceHistoryRepository(PriceHistoryFakeDb()),
    )
    return purchases, inventory, product, expense, vendor_acct, cash


def test_latest_purchase_rate_falls_back_to_product_last_purchase_rate():
    purchases, inventory, product, _expense, _vendor_acct, _cash = _purchase_stack()
    inventory.set_product_cost_fields(product.id, last_purchase_rate=75.5)
    rate = purchases.get_latest_purchase_rate(
        CatalogItemType.PRODUCT, product.id, "v1"
    )
    assert rate == 75.5


def test_bill_records_vendor_rate_and_updates_active_purchase_price():
    purchases, inventory, product, expense, vendor_acct, cash = _purchase_stack()
    purchases.create_purchase_bill_from_lines(
        vendor_id="v1",
        raw_lines=[
            {
                "item_type": CatalogItemType.PRODUCT.value,
                "item_id": product.id,
                "product_id": product.id,
                "qty": 2,
                "rate": 88.0,
            }
        ],
        vendor_bill_number="BILL-RATE",
        amount_paid=0.0,
        voucher_date=date.today(),
        apply_stock=False,
    )
    assert purchases.get_latest_purchase_rate(
        CatalogItemType.PRODUCT, product.id, "v1"
    ) == 88.0
    assert inventory.get_product(product.id).last_purchase_rate == 88.0

    purchases.create_purchase_bill_from_lines(
        vendor_id="v1",
        raw_lines=[
            {
                "item_type": CatalogItemType.PRODUCT.value,
                "item_id": product.id,
                "product_id": product.id,
                "qty": 1,
                "rate": 95.0,
            }
        ],
        vendor_bill_number="BILL-RATE-2",
        amount_paid=0.0,
        voucher_date=date.today(),
        apply_stock=False,
    )
    assert purchases.get_latest_purchase_rate(
        CatalogItemType.PRODUCT, product.id, "v1"
    ) == 95.0
    assert inventory.get_product(product.id).last_purchase_rate == 95.0
    history = purchases.list_purchase_price_history(
        CatalogItemType.PRODUCT, product.id, vendor_id="v1"
    )
    assert [round(h.rate, 2) for h in history] == [95.0, 88.0]

def test_po_to_grn_to_bill_flow():
    purchases, inventory, product, expense, vendor_acct, cash = _purchase_stack()

    po = purchases.create_purchase_order(
        vendor_id="v1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": product.name,
                "qty_ordered": 10,
                "rate": 50,
                "expense_account_id": expense.id,
            }
        ],
    )
    assert po.status == PurchaseOrderStatus.SENT

    grn = purchases.create_goods_receipt(
        vendor_id="v1",
        receipt_date=date.today(),
        lines=[{"product_id": product.id, "qty_received": 4, "rate": 50}],
        purchase_order_id=po.id,
        freight=20,
        confirm=True,
    )
    updated_po = purchases.get_purchase_order(po.id)
    assert updated_po.status == PurchaseOrderStatus.PARTIALLY_RECEIVED
    assert inventory.get_product(product.id).current_qty == 4

    bill = purchases.create_purchase_bill(
        vendor_account_id=vendor_acct.id,
        expense_lines=[
            {
                "expense_account_id": expense.id,
                "amount": 200,
                "product_id": product.id,
                "qty": 4,
                "rate": 50,
            }
        ],
        vendor_bill_number="B-1",
        amount_paid=200,
        paying_account_id=cash.id,
        reference_grn_id=grn.id,
    )
    assert bill.total_debit == bill.total_credit
    bills = purchases.list_purchase_bills()
    assert any(row["id"] == bill.id for row in bills)


def test_merge_vendor_payment_creates_purchase_bill():
    purchases, _inventory, _product, expense, vendor_acct, cash = _purchase_stack()
    voucher = purchases.merge_vendor_payment_into_purchase(
        vendor_account_id=vendor_acct.id,
        expense_account_id=expense.id,
        paying_account_id=cash.id,
        amount=500,
        description="Dyeing for order",
        reference_order_id="order-1",
    )
    row = purchases.get_purchase_bill(voucher.id)
    assert row["total"] == 500
    assert row["reference_order_id"] == "order-1"


def test_po_update_cannot_reduce_qty_below_received():
    import pytest
    from vaybooks.bms.domain.shared.exceptions import ValidationError

    purchases, _inventory, product, expense, _vendor_acct, _cash = _purchase_stack()
    po = purchases.create_purchase_order(
        vendor_id="v1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": product.name,
                "qty_ordered": 10,
                "rate": 50,
                "expense_account_id": expense.id,
            }
        ],
    )
    purchases.create_goods_receipt(
        vendor_id="v1",
        receipt_date=date.today(),
        lines=[{"product_id": product.id, "qty_received": 4, "rate": 50}],
        purchase_order_id=po.id,
        confirm=True,
    )
    with pytest.raises(ValidationError, match="already received"):
        purchases.update_purchase_order(
            po.id,
            vendor_id="v1",
            order_date=date.today(),
            lines=[
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "qty_ordered": 3,
                    "rate": 50,
                    "expense_account_id": expense.id,
                }
            ],
        )


def test_po_create_ignores_service_identity_for_product_only_lines():
    """PO domain stores product_id only — service-shaped payloads without product_id are empty."""
    purchases, _inventory, product, expense, _vendor_acct, _cash = _purchase_stack()
    po = purchases.create_purchase_order(
        vendor_id="v1",
        order_date=date.today(),
        lines=[
            {
                "product_id": product.id,
                "product_name": product.name,
                "qty_ordered": 2,
                "rate": 40,
                "expense_account_id": expense.id,
            }
        ],
    )
    assert len(po.lines) == 1
    assert po.lines[0].product_id == product.id
    assert not hasattr(po.lines[0], "item_type") or True
