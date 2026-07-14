"""Fixture records and expected filter/sort outcomes for list schema tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from types import SimpleNamespace

from vaybooks.bms.domain.accounting.entities import Account, Voucher, VoucherLine
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.shared.enums import (
    AccountType,
    ActivityCategory,
    ActivityType,
    CustomizationItemStatus,
    OrderStatus,
    PartyRegistrationType,
    StockMovementType,
    StockReferenceType,
    VoucherType,
)
from vaybooks.bms.domain.vendors.entities import Vendor


def _dt(y, m, d, h=0):
    return datetime(y, m, d, h)


def _customers():
    c1 = Customer(
        id="c1",
        customer_name="Alpha Customer",
        phone_number="9000000001",
        alternate_phone_number="9000000011",
        gstin="27AAAAA0000A1Z5",
        registration_type=PartyRegistrationType.REGISTERED,
        created_at=_dt(2026, 1, 1),
    )
    c2 = Customer(
        id="c2",
        customer_name="Beta Customer",
        phone_number="9000000002",
        created_at=_dt(2026, 2, 1),
    )
    setattr(c1, "order_count", 2)
    setattr(c2, "order_count", 0)
    return [c1, c2]


def _vendors():
    v1 = Vendor(
        id="v1",
        vendor_name="Alpha Vendor",
        phone_number="9100000001",
        created_at=_dt(2026, 1, 1),
    )
    v2 = Vendor(
        id="v2",
        vendor_name="Beta Vendor",
        phone_number="9100000002",
        created_at=_dt(2026, 2, 1),
    )
    setattr(v1, "current_balance", 100.0)
    setattr(v2, "current_balance", -50.0)
    return [v1, v2]


def _orders():
    return [
        SimpleNamespace(
            order_number="ZO1",
            customer_name="Alpha Customer",
            phone_number="9000000001",
            order_status=OrderStatus.IN_PROGRESS,
            order_date=date(2026, 7, 1),
            expected_delivery_date=date(2026, 7, 10),
            advance_amount=100.0,
            created_at=_dt(2026, 7, 1),
            customization_items=[SimpleNamespace(bill_number="ZB01")],
        ),
        SimpleNamespace(
            order_number="ZO2",
            customer_name="Beta Customer",
            phone_number="9000000002",
            order_status=OrderStatus.COMPLETED,
            order_date=date(2026, 7, 5),
            expected_delivery_date=date(2026, 7, 15),
            advance_amount=0.0,
            created_at=_dt(2026, 7, 5),
            customization_items=[],
        ),
    ]


def _items():
    return [
        SimpleNamespace(
            bill_number="ZB01",
            description="Blouse",
            order_number="ZO1",
            customer_name="Alpha Customer",
            phone_number="9000000001",
            item_status=CustomizationItemStatus.IN_PROGRESS,
            order_status=OrderStatus.IN_PROGRESS,
            mph_snapshot_at=_dt(2026, 7, 1),
            margin_per_hour=500.0,
        ),
        SimpleNamespace(
            bill_number="ZB02",
            description="Saree",
            order_number="ZO2",
            customer_name="Beta Customer",
            phone_number="9000000002",
            item_status=CustomizationItemStatus.COMPLETED,
            order_status=OrderStatus.COMPLETED,
            mph_snapshot_at=None,
            margin_per_hour=100.0,
        ),
    ]


def _time_entries():
    return [
        SimpleNamespace(
            work_date=date(2026, 7, 1),
            bill_number="ZB01",
            order_number="ZO1",
            worker_name="Ravi",
            activity_name="Stitching",
            created_at=_dt(2026, 7, 1),
            duration_minutes=120,
        ),
        SimpleNamespace(
            work_date=date(2026, 7, 5),
            bill_number="ZB02",
            order_number="ZO2",
            worker_name="Meera",
            activity_name="Embroidery",
            created_at=_dt(2026, 7, 5),
            duration_minutes=60,
        ),
    ]


def _accounts():
    return [
        Account(
            id="a1",
            account_name="Cash",
            account_type=AccountType.ASSET,
            is_store_account=True,
            is_active=True,
            current_balance=1000.0,
            created_at=_dt(2026, 1, 1),
        ),
        Account(
            id="a2",
            account_name="Customer - Alpha",
            account_type=AccountType.ASSET,
            linked_customer_id="c1",
            is_active=True,
            current_balance=500.0,
            created_at=_dt(2026, 2, 1),
        ),
    ]


def _voucher(vnum, vtype, vdate, desc, lines, **kwargs):
    return Voucher(
        voucher_number=vnum,
        voucher_type=vtype,
        voucher_date=vdate,
        description=desc,
        lines=lines,
        **kwargs,
    )


def _vouchers():
    line = VoucherLine(account_id="a1", account_name="Cash", debit_amount=100.0)
    return [
        _voucher("V001", VoucherType.JOURNAL, _dt(2026, 7, 1), "Entry A", [line]),
        _voucher("V002", VoucherType.JOURNAL, _dt(2026, 7, 5), "Entry B", [line]),
    ]


def _receipts():
    dr = VoucherLine(account_id="a1", account_name="Cash", debit_amount=200.0)
    cr = VoucherLine(account_id="a2", account_name="Customer", credit_amount=200.0)
    return [
        _voucher("R001", VoucherType.RECEIPT, _dt(2026, 7, 1), "Receipt A", [dr, cr]),
    ]


def _payments():
    dr = VoucherLine(account_id="v-acc", account_name="Vendor", debit_amount=300.0)
    cr = VoucherLine(account_id="a1", account_name="Cash", credit_amount=300.0)
    return [
        _voucher(
            "P001",
            VoucherType.PAYMENT,
            _dt(2026, 7, 1),
            "Payment A",
            [dr, cr],
            reference_service_id="svc1",
        ),
    ]


def _accounting_invoices():
    dr = VoucherLine(account_id="a2", account_name="Customer", debit_amount=400.0)
    cr = VoucherLine(account_id="sales", account_name="Sales", credit_amount=400.0)
    return [
        _voucher("I001", VoucherType.CUSTOMIZATION_INVOICE, _dt(2026, 7, 1), "Invoice A", [dr, cr]),
    ]


def _store_sales():
    return [
        {
            "store_invoice_number": "S001",
            "party_name": "Walk-in",
            "sale_date": date(2026, 7, 1),
            "customer_account_id": "a2",
            "gross": 1000.0,
            "collected": 1000.0,
        },
        {
            "store_invoice_number": "S002",
            "party_name": "Guest",
            "sale_date": date(2026, 7, 5),
            "customer_account_id": None,
            "gross": 500.0,
            "collected": 500.0,
        },
    ]


def _journal():
    return _vouchers()


def _trial_balance():
    return [
        {"account_name": "Cash", "account_type": AccountType.ASSET, "balance": 1000.0},
        {"account_name": "Sales", "account_type": AccountType.REVENUE, "balance": 500.0},
    ]


def _activities():
    return [
        SimpleNamespace(
            activity_name="Stitching",
            activity_category=ActivityCategory.IN_HOUSE_SERVICE,
            activity_type=ActivityType.IN_HOUSE,
            is_active=True,
            requires_time_tracking=True,
            created_at=_dt(2026, 1, 1),
        ),
        SimpleNamespace(
            activity_name="Embroidery",
            activity_category=ActivityCategory.OUTSOURCED_SERVICE,
            activity_type=ActivityType.OUTSOURCED,
            is_active=False,
            requires_time_tracking=False,
            created_at=_dt(2026, 2, 1),
        ),
    ]


def _services():
    return [
        SimpleNamespace(
            id="svc1",
            service_name="Dry Cleaning",
            expense_account_id="exp1",
            is_active=True,
            created_at=_dt(2026, 1, 1),
        ),
        SimpleNamespace(
            id="svc2",
            service_name="Transport",
            expense_account_id="exp2",
            is_active=False,
            created_at=_dt(2026, 2, 1),
        ),
    ]


def _inventory_categories():
    return [
        SimpleNamespace(
            id="cat1",
            name="Fabric",
            description="Woven materials",
            path="Fabric",
            product_count=1,
            is_active=True,
            created_at=_dt(2026, 1, 1),
        ),
        SimpleNamespace(
            id="cat2",
            name="Accessories",
            description="",
            path="Accessories",
            product_count=0,
            is_active=False,
            created_at=_dt(2026, 2, 1),
        ),
    ]


def _inventory_products():
    return [
        SimpleNamespace(
            id="p1",
            sku="SKU-1",
            name="Cotton",
            category_ids=["cat1"],
            is_active=True,
            current_qty=10.0,
            created_at=_dt(2026, 1, 1),
        ),
        SimpleNamespace(
            id="p2",
            sku="SKU-2",
            name="Silk",
            category_ids=["cat2"],
            is_active=False,
            current_qty=5.0,
            created_at=_dt(2026, 2, 1),
        ),
    ]


def _inventory_stock():
    return _inventory_products()


def _inventory_stock_ledger():
    return [
        {
            "movement_date": date(2026, 7, 1),
            "product_id": "p1",
            "product_name": "Cotton",
            "category_id": "cat1",
            "movement_type": StockMovementType.RECEIVE.value,
            "reference_type": StockReferenceType.PURCHASE.value,
        },
        {
            "movement_date": date(2026, 7, 5),
            "product_id": "p2",
            "product_name": "Silk",
            "category_id": "cat2",
            "movement_type": StockMovementType.ISSUE.value,
            "reference_type": StockReferenceType.MANUAL.value,
        },
    ]


FIXTURES = {
    "orders": _orders(),
    "items": _items(),
    "customers": _customers(),
    "vendors": _vendors(),
    "time": _time_entries(),
    "accounts": _accounts(),
    "vouchers": _vouchers(),
    "receipts": _receipts(),
    "payments": _payments(),
    "accounting_invoices": _accounting_invoices(),
    "store_sales": _store_sales(),
    "journal": _journal(),
    "trial_balance": _trial_balance(),
    "activities": _activities(),
    "services": _services(),
    "inventory_categories": _inventory_categories(),
    "inventory_products": _inventory_products(),
    "inventory_stock": _inventory_stock(),
    "inventory_stock_ledger": _inventory_stock_ledger(),
}

# (entity_key, field_key, value, expected_count)
FILTER_POSITIVE = [
    ("customers", "customer_name", "Alpha Customer", 1),
    ("customers", "customer_name", "alpha", 1),
    ("customers", "customer_name", "^Alpha", 1),
    ("customers", "phone_number", "9000000001", 1),
    ("customers", "phone_number", r"9000000001$", 1),
    ("customers", "gstin", "27AAAAA0000A1Z5", 1),
    ("customers", "gstin", "aaaaa", 1),
    ("customers", "registration_type", PartyRegistrationType.REGISTERED.value, 1),
    ("customers", "has_orders", "with", 1),
    ("vendors", "vendor_name", "Alpha Vendor", 1),
    ("vendors", "vendor_name", "vendor$", 2),
    ("vendors", "phone_number", r"^9100", 2),
    ("vendors", "balance_state", "dr", 1),
    ("orders", "order_number", "ZO1", 1),
    ("orders", "customer_name", "Alpha Customer", 1),
    ("orders", "statuses", [OrderStatus.IN_PROGRESS.value], 1),
    ("orders", "has_advance", True, 1),
    ("items", "bill_number", "ZB01", 1),
    ("items", "mph_state", "set", 1),
    ("items", "min_mph", 200.0, 1),
    ("accounts", "account_name", "Cash", 1),
    ("accounts", "types", [AccountType.ASSET.value], 2),
    ("accounts", "active_only", True, 2),
    ("accounts", "store_filter", "yes", 1),
    ("accounts", "linked", "customer", 1),
    ("vouchers", "voucher_number", "V001", 1),
    ("vouchers", "types", [VoucherType.JOURNAL.value], 2),
    ("vouchers", "min_amount", 50.0, 2),
    ("store_sales", "store_invoice_number", "S001", 1),
    ("store_sales", "party_name", "Walk-in", 1),
    ("store_sales", "min_gross", 600.0, 1),
    ("trial_balance", "account_name", "Cash", 1),
    ("activities", "activity_name", "Stitching", 1),
    ("activities", "active_only", True, 1),
    ("activities", "time_tracking", "yes", 1),
    ("services", "service_name", "Dry Cleaning", 1),
    ("services", "active_only", True, 1),
    ("inventory_categories", "name", "Fabric", 1),
    ("inventory_categories", "active_only", True, 1),
    ("inventory_products", "sku", "SKU-1", 1),
    ("inventory_products", "category_id", "cat1", 1),
    ("inventory_stock_ledger", "movement_type", StockMovementType.RECEIVE.value, 1),
    ("inventory_stock_ledger", "reference_type", StockReferenceType.PURCHASE.value, 1),
]

FILTER_NEGATIVE = [
    ("customers", "customer_name", "NoSuchCustomer", 0),
    ("customers", "customer_name", "[", 0),  # invalid regex
    ("customers", "phone_number", "9999999999", 0),
    ("vendors", "vendor_name", "NoSuchVendor", 0),
    ("orders", "order_number", "ZO", 0),
    ("items", "bill_number", "ZB", 0),
    ("accounts", "account_name", "Cas", 0),
    ("vouchers", "voucher_number", "V00", 0),
    ("store_sales", "party_name", "Walk", 0),
    ("inventory_products", "sku", "SKU", 2),
    ("inventory_categories", "name", "Fab", 1),
]

SORT_CASES = [
    ("customers", "customer_name", False, "Alpha Customer"),
    ("customers", "customer_name", True, "Beta Customer"),
    ("vendors", "vendor_name", False, "Alpha Vendor"),
    ("orders", "order_number", False, "ZO1"),
    ("items", "bill_number", False, "ZB01"),
    ("accounts", "account_name", False, "Cash"),
    ("vouchers", "voucher_number", False, "V001"),
    ("trial_balance", "account_name", False, "Cash"),
    ("inventory_products", "sku", False, "SKU-1"),
    ("inventory_categories", "name", False, "Accessories"),
]
