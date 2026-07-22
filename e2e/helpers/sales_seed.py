"""Programmatic sales fixtures for Playwright E2E (customer, stock, cash invoice)."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.parties.customers.service import CustomerAppService
from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.application.sales.service import SalesAppService
from vaybooks.bms.domain.parties.customers.entities import CustomerInput
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.domain.inventory.rate_history_service import ProductRateHistoryService
from vaybooks.bms.infrastructure.db.connection import get_database_from_uri
from vaybooks.bms.infrastructure.repositories.finance.mongo_accounting_repository import (
    MongoAccountRepository,
    MongoVoucherRepository,
)
from vaybooks.bms.infrastructure.repositories.finance.mongo_counter_repository import (
    MongoCounterRepository,
)
from vaybooks.bms.infrastructure.repositories.sales.mongo_customer_price_repository import (
    MongoCustomerPriceRepository,
)
from vaybooks.bms.infrastructure.repositories.parties.mongo_customer_repository import (
    MongoCustomerRepository,
)
from vaybooks.bms.infrastructure.repositories.inventory.mongo_inventory_repository import (
    MongoInventoryProductRepository,
    MongoProductCategoryRepository,
    MongoProductFieldDefinitionRepository,
    MongoProductUnitRepository,
    MongoStockMovementRepository,
)
from vaybooks.bms.infrastructure.repositories.inventory.mongo_product_rate_history_repository import (
    MongoProductRateHistoryRepository,
)
from vaybooks.bms.infrastructure.repositories.sales.mongo_sales_repository import (
    MongoDeliveryNoteRepository,
    MongoEstimateRepository,
    MongoQuotationRepository,
    MongoSalesOrderRepository,
    MongoSalesReturnRepository,
)

BMS_ROOT = Path(__file__).resolve().parents[2]


def _read_secrets() -> dict[str, str]:
    secrets_path = BMS_ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}
    try:
        import tomllib

        data = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
        return {k: str(v) for k, v in data.items()}
    except Exception:
        return {}


def _mongo_uri() -> str:
    secrets = _read_secrets()
    uri = secrets.get("MONGODB_URI") or os.environ.get("MONGODB_URI", "")
    if not uri:
        raise RuntimeError("MONGODB_URI required for sales seed")
    return uri


def _mongo_database() -> str:
    secrets = _read_secrets()
    if secrets.get("MONGODB_DATABASE"):
        return secrets["MONGODB_DATABASE"]
    return os.environ.get("MONGODB_DATABASE", "zahcci_customization")


def _db():
    return get_database_from_uri(_mongo_uri(), _mongo_database())


@dataclass(frozen=True)
class SalesFixture:
    customer_id: str
    customer_name: str
    phone: str
    customer_account_id: str
    product_id: str
    product_sku: str
    product_name: str
    sku_label: str
    store_account_id: str
    invoice_id: str
    store_invoice_number: str
    qty_sold: float
    rate: float


def _services():
    db = _db()
    account_repo = MongoAccountRepository(db)
    voucher_repo = MongoVoucherRepository(db)
    counter_repo = MongoCounterRepository(db)
    customer_repo = MongoCustomerRepository(db)
    accounting = AccountingAppService(account_repo, voucher_repo, counter_repo)
    customers = CustomerAppService(customer_repo, account_repo)
    rate_history = ProductRateHistoryService(
        MongoProductRateHistoryRepository(db, "product_selling_rate_history"),
        MongoProductRateHistoryRepository(db, "product_mrp_history"),
        MongoProductRateHistoryRepository(db, "product_gst_rate_history"),
    )
    inventory = InventoryAppService(
        MongoProductCategoryRepository(db),
        MongoInventoryProductRepository(db),
        MongoStockMovementRepository(db),
        MongoProductUnitRepository(db),
        MongoProductFieldDefinitionRepository(db),
        rate_history,
    )
    sales = SalesAppService(
        MongoSalesOrderRepository(db),
        MongoDeliveryNoteRepository(db),
        MongoSalesReturnRepository(db),
        counter_repo,
        accounting,
        inventory,
        customer_service=customers,
        estimate_repo=MongoEstimateRepository(db),
        quotation_repo=MongoQuotationRepository(db),
        customer_price_repo=MongoCustomerPriceRepository(db),
    )
    return accounting, customers, inventory, sales


def _ensure_account(
    accounting: AccountingAppService,
    name: str,
    account_type: AccountType,
    *,
    is_store_account: bool = False,
):
    existing = accounting.get_account_by_name(name)
    if existing:
        if is_store_account and not existing.is_store_account:
            return accounting.set_store_account(existing.id, True)
        return existing
    return accounting.create_account(
        name,
        account_type.value,
        is_store_account=is_store_account,
    )


def ensure_posting_accounts(accounting: AccountingAppService | None = None):
    """Ensure Cash Drawer + Sales exist (session seed may wipe accounts)."""
    if accounting is None:
        accounting, _, _, _ = _services()
    cash = _ensure_account(
        accounting, "Cash Drawer", AccountType.ASSET, is_store_account=True
    )
    sales_acct = _ensure_account(accounting, "Sales", AccountType.REVENUE)
    return cash, sales_acct


def unique_invoice_number(prefix: str = "E2E-INV") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def unique_sku(prefix: str = "E2E-SKU") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def product_qty(product_id: str) -> float:
    _, _, inventory, _ = _services()
    product = inventory.get_product(product_id)
    if not product:
        raise ValueError(f"Product not found: {product_id}")
    return float(product.current_qty)


def get_return_by_number(return_number: str):
    _, _, _, sales = _services()
    for item in sales.list_sales_returns():
        if item.return_number == return_number:
            return item
    return None


def return_has_voucher(return_number: str) -> bool:
    sales_return = get_return_by_number(return_number)
    if not sales_return:
        return False
    if not sales_return.voucher_id:
        return False
    accounting, _, _, _ = _services()
    voucher = accounting.get_voucher(sales_return.voucher_id)
    return bool(voucher and voucher.voucher_type == VoucherType.SALES_RETURN)


def create_pending_return_for_fixture(
    fixture: SalesFixture,
    *,
    qty: float | None = None,
    reason: str = "E2E seeded return",
) -> str:
    """Create a Pending Approval return via app services; return the return number."""
    _, _, _, sales = _services()
    return_qty = float(qty if qty is not None else min(fixture.qty_sold, 1.0))
    sales_return = sales.create_sales_return(
        customer_id=fixture.customer_id,
        return_date=date.today(),
        lines=[
            {
                "product_id": fixture.product_id,
                "product_name": fixture.product_name,
                "qty": return_qty,
                "rate": fixture.rate,
            }
        ],
        source_invoice_id=fixture.invoice_id,
        return_reason=reason,
        restock_items=True,
    )
    return sales_return.return_number


def create_cash_sale_fixture(
    *,
    customer_name: str | None = None,
    phone: str | None = None,
    qty: float = 2.0,
    rate: float = 100.0,
    opening_qty: float = 20.0,
) -> SalesFixture:
    """Create customer + stocked product + posted cash sales invoice."""
    from e2e.helpers.unique import unique_name, unique_phone

    accounting, customers, inventory, sales = _services()
    cash, _ = ensure_posting_accounts(accounting)

    name = customer_name or unique_name("RetCust")
    phone_number = phone or unique_phone()
    customer = customers.create_customer(
        CustomerInput(customer_name=name, phone_number=phone_number)
    )
    customer_account = accounting.get_customer_account(customer.id)
    if not customer_account:
        raise RuntimeError("Customer AR account was not created")

    category = inventory.create_category(unique_name("RetCat"))
    sku = unique_sku()
    product_name = unique_name("RetProd")
    unit = inventory.find_or_create_unit("pcs", "Pieces")
    product = inventory.create_product(
        sku,
        product_name,
        category.id,
        opening_qty=opening_qty,
        unit_id=unit.id,
        selling_rate=rate,
        mrp=rate,
        # Registered businesses require HSN on sales lines in the UI editor.
        hsn_sac="5208",
        gst_rate=18.0,
    )

    store_invoice_number = unique_invoice_number()
    voucher = sales.create_direct_sale(
        customer_account_id=customer_account.id,
        store_account_id=cash.id,
        gross_amount=round(qty * rate, 2),
        discount_amount=0,
        amount_received=round(qty * rate, 2),
        store_invoice_number=store_invoice_number,
        line_items=[
            {
                "product_id": product.id,
                "qty": qty,
                "rate": rate,
                "description": product_name,
            }
        ],
        voucher_date=date.today(),
    )

    return SalesFixture(
        customer_id=customer.id,
        customer_name=name,
        phone=phone_number,
        customer_account_id=customer_account.id,
        product_id=product.id,
        product_sku=sku,
        product_name=product_name,
        sku_label=f"{sku} — {product_name}",
        store_account_id=cash.id,
        invoice_id=voucher.id,
        store_invoice_number=store_invoice_number,
        qty_sold=qty,
        rate=rate,
    )
