"""Tests for migration mapping, profiles, and import runners."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.customer_app_service import CustomerAppService
from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.application.migration.mapping import (
    apply_saved_profile,
    missing_required,
    suggest_mapping,
)
from vaybooks.bms.application.migration.parser import load_upload
from vaybooks.bms.application.migration.schemas import (
    DuplicatePolicy,
    ImportEntityType,
)
from vaybooks.bms.application.migration_app_service import MigrationAppService
from vaybooks.bms.application.vendor_app_service import VendorAppService
from vaybooks.bms.domain.migration.entities import ImportMappingProfile
from vaybooks.bms.domain.vendors.entities import Vendor
from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeCustomerRepository,
    FakeInventoryProductRepository,
    FakeProductCategoryRepository,
    FakeProductUnitRepository,
    FakeStockMovementRepository,
    FakeVoucherRepository,
)

FIXTURES = Path(__file__).parent / "fixtures" / "migration"


class FakeVendorRepository:
    def __init__(self):
        self._store = {}

    def save(self, vendor: Vendor) -> Vendor:
        self._store[vendor.id] = vendor
        return vendor

    def find_by_id(self, vendor_id: str):
        return self._store.get(vendor_id)

    def find_by_phone(self, phone: str):
        phone = (phone or "").strip()
        for v in self._store.values():
            if v.phone_number == phone:
                return v
        return None

    def find_by_gstin(self, gstin: str):
        gstin = (gstin or "").strip().upper()
        for v in self._store.values():
            if (v.gstin or "").strip().upper() == gstin:
                return v
        return None

    def search(self, query: str):
        return list(self._store.values())

    def list_all(self):
        return list(self._store.values())


class FakeImportMappingProfileRepository:
    def __init__(self):
        self._store = {}

    def save(self, profile: ImportMappingProfile) -> ImportMappingProfile:
        self._store[profile.id] = profile
        return profile

    def find_by_id(self, profile_id: str):
        return self._store.get(profile_id)

    def find_by_entity_and_name(self, entity_type: str, name: str):
        name = name.strip()
        for profile in self._store.values():
            if profile.entity_type == entity_type and profile.name == name:
                return profile
        return None

    def list_by_entity(self, entity_type: str):
        return sorted(
            [p for p in self._store.values() if p.entity_type == entity_type],
            key=lambda p: p.name,
        )

    def delete(self, profile_id: str) -> None:
        self._store.pop(profile_id, None)


def make_migration_service():
    account_repo = FakeAccountRepository()
    voucher_repo = FakeVoucherRepository()
    counter_repo = FakeCounterRepository()
    customer_repo = FakeCustomerRepository()
    vendor_repo = FakeVendorRepository()
    category_repo = FakeProductCategoryRepository()
    product_repo = FakeInventoryProductRepository()
    movement_repo = FakeStockMovementRepository()
    unit_repo = FakeProductUnitRepository()

    accounting = AccountingAppService(account_repo, voucher_repo, counter_repo)
    customers = CustomerAppService(customer_repo, account_repo)
    vendors = VendorAppService(vendor_repo, account_repo)
    inventory = InventoryAppService(
        category_repo, product_repo, movement_repo, unit_repo
    )
    migration = MigrationAppService(
        FakeImportMappingProfileRepository(),
        customers,
        vendors,
        inventory,
        accounting,
    )
    return migration, inventory, customers, accounting, account_repo, movement_repo


def test_suggest_mapping_alien_customer_headers():
    cols = ["Party Name", "Mobile", "Op. Balance", "City", "State"]
    mapping = suggest_mapping(ImportEntityType.CUSTOMERS, cols)
    assert mapping["customer_name"] == "Party Name"
    assert mapping["phone_number"] == "Mobile"
    assert mapping["opening_balance"] == "Op. Balance"
    assert missing_required(ImportEntityType.CUSTOMERS, mapping) == []


def test_apply_saved_profile_warns_on_missing_columns():
    base = suggest_mapping(
        ImportEntityType.CUSTOMERS, ["Party Name", "Mobile", "City"]
    )
    profile = {
        "customer_name": "Party Name",
        "phone_number": "Mobile",
        "opening_balance": "Op. Balance",
    }
    mapping, warnings = apply_saved_profile(
        base, ["Party Name", "Mobile", "City"], profile
    )
    assert mapping["customer_name"] == "Party Name"
    assert mapping["phone_number"] == "Mobile"
    assert any("Op. Balance" in w for w in warnings)


def test_parse_alien_customer_csv():
    raw = (FIXTURES / "customers_alien_headers.csv").read_bytes()
    df = load_upload(raw, "customers_alien_headers.csv")
    assert list(df.columns) == [
        "Party Name",
        "Mobile",
        "Op. Balance",
        "City",
        "State",
    ]
    assert len(df) == 2


def test_save_and_reuse_mapping_profile():
    migration, *_ = make_migration_service()
    mapping = {
        "customer_name": "Party Name",
        "phone_number": "Mobile",
        "opening_balance": "Op. Balance",
    }
    saved = migration.save_mapping_profile(
        ImportEntityType.CUSTOMERS, "Old ERP", mapping
    )
    assert saved.name == "Old ERP"
    listed = migration.list_mapping_profiles(ImportEntityType.CUSTOMERS)
    assert len(listed) == 1
    again = migration.save_mapping_profile(
        ImportEntityType.CUSTOMERS,
        "Old ERP",
        {**mapping, "city": "City"},
    )
    assert again.id == saved.id
    assert again.mapping["city"] == "City"


def test_import_categories_products_customers_with_opening():
    migration, inventory, customers, accounting, account_repo, movement_repo = (
        make_migration_service()
    )

    cat_df = load_upload(
        (FIXTURES / "categories_alien_headers.csv").read_bytes(),
        "categories_alien_headers.csv",
    )
    cat_mapping = suggest_mapping(
        ImportEntityType.CATEGORIES, list(cat_df.columns)
    )
    # Aliases: Category Name -> name, Parent -> parent_name
    assert cat_mapping["name"] == "Category Name"
    cat_result = migration.run_import(
        ImportEntityType.CATEGORIES, cat_df, cat_mapping, DuplicatePolicy.SKIP
    )
    assert cat_result.created == 2
    assert cat_result.failed == 0
    categories = inventory.list_categories(active_only=False)
    assert len(categories) == 2

    prod_df = load_upload(
        (FIXTURES / "products_alien_headers.csv").read_bytes(),
        "products_alien_headers.csv",
    )
    prod_mapping = suggest_mapping(ImportEntityType.PRODUCTS, list(prod_df.columns))
    assert prod_mapping["sku"] == "Item Code"
    assert prod_mapping["opening_qty"] == "Op Qty"
    prod_result = migration.run_import(
        ImportEntityType.PRODUCTS, prod_df, prod_mapping, DuplicatePolicy.SKIP
    )
    assert prod_result.created == 1
    product = inventory.find_product_by_sku("SKU-100")
    assert product is not None
    assert product.opening_qty == 5
    assert product.current_qty == 5
    movements = movement_repo.list_by_product(product.id)
    assert any("Opening stock" in (m.notes or "") for m in movements)

    cust_df = load_upload(
        (FIXTURES / "customers_alien_headers.csv").read_bytes(),
        "customers_alien_headers.csv",
    )
    cust_mapping = suggest_mapping(
        ImportEntityType.CUSTOMERS, list(cust_df.columns)
    )
    cust_result = migration.run_import(
        ImportEntityType.CUSTOMERS, cust_df, cust_mapping, DuplicatePolicy.SKIP
    )
    assert cust_result.created == 2
    assert cust_result.failed == 0
    customer = customers.lookup_customer_by_phone("9876543210")
    assert customer is not None
    account = account_repo.find_customer_account(customer.id)
    assert account is not None
    assert account.opening_balance == 1500
    assert account.current_balance == 1500


def test_duplicate_skip_policy():
    migration, inventory, *_ = make_migration_service()
    cat_df = pd.DataFrame(
        [{"name": "Apparel", "parent_name": "", "description": "", "is_active": "true"}]
    )
    mapping = {
        "name": "name",
        "parent_name": "parent_name",
        "description": "description",
        "is_active": "is_active",
    }
    first = migration.run_import(
        ImportEntityType.CATEGORIES, cat_df, mapping, DuplicatePolicy.SKIP
    )
    second = migration.run_import(
        ImportEntityType.CATEGORIES, cat_df, mapping, DuplicatePolicy.SKIP
    )
    assert first.created == 1
    assert second.skipped == 1
    assert len(inventory.list_categories(active_only=False)) == 1


def test_set_opening_balance_rejects_when_vouchers_exist():
    migration, _, customers, accounting, account_repo, _ = make_migration_service()
    from vaybooks.bms.domain.customers.entities import CustomerInput
    from vaybooks.bms.domain.accounting.entities import Voucher, VoucherLine
    from vaybooks.bms.domain.shared.enums import VoucherType
    from datetime import date

    customer = customers.create_customer(
        CustomerInput(customer_name="X", phone_number="9876501234")
    )
    account = account_repo.find_customer_account(customer.id)
    accounting.set_opening_balance(account.id, 100)
    voucher = Voucher(
        voucher_number="VCH-1",
        voucher_type=VoucherType.JOURNAL,
        voucher_date=date.today(),
        description="test",
        lines=[
            VoucherLine(
                account_id=account.id,
                account_name=account.account_name,
                debit_amount=10,
                credit_amount=0,
            ),
            VoucherLine(
                account_id=account.id,
                account_name=account.account_name,
                debit_amount=0,
                credit_amount=10,
            ),
        ],
    )
    # Save via voucher repo on accounting service
    accounting._voucher_repo.save(voucher)
    with pytest.raises(ValueError, match="transactions"):
        accounting.set_opening_balance(account.id, 200)
