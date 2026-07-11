"""End-to-end purchase workflow tests."""

from datetime import date

from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.application.purchase_app_service import PurchaseAppService
from vaybooks.bms.domain.accounting.entities import Account
from vaybooks.bms.domain.shared.enums import AccountType, PurchaseOrderStatus
from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeVoucherRepository,
    make_inventory_app_service,
)


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
    )
    return purchases, inventory, product, expense, vendor_acct, cash


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
