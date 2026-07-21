"""Idempotent demo/test fixtures for customers, vendors, categories, products, business."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from vaybooks.bms.application.business_app_service import BusinessAppService
from vaybooks.bms.application.customer_app_service import CustomerAppService
from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.application.vendor_app_service import VendorAppService
from vaybooks.bms.domain.customers.entities import CustomerInput
from vaybooks.bms.domain.inventory.rate_history_service import ProductRateHistoryService
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCustomerError,
    DuplicateVendorError,
    ValidationError,
)
from vaybooks.bms.domain.vendors.entities import VendorInput
from vaybooks.bms.infrastructure.repositories.mongo_accounting_repository import (
    MongoAccountRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_business_profile_repository import (
    MongoBusinessProfileRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_customer_repository import (
    MongoCustomerRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_inventory_repository import (
    MongoInventoryProductRepository,
    MongoProductCategoryRepository,
    MongoProductUnitRepository,
    MongoStockMovementRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_product_rate_history_repository import (
    MongoProductRateHistoryRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_vendor_repository import (
    MongoVendorRepository,
)

if TYPE_CHECKING:
    from pymongo.database import Database

    from vaybooks.bms.infrastructure.config.settings import AppSettings

logger = logging.getLogger("vaybooks.bms.demo_seed")

# Stable demo phones / SKUs so re-runs stay idempotent.
DEMO_CUSTOMERS = (
    {
        "customer_name": "Seed Unreg Local",
        "phone_number": "9000001001",
        "city": "Mumbai",
        "state_code": "27",
        "pincode": "400001",
        "registration_type": PartyRegistrationType.UNREGISTERED,
    },
    {
        "customer_name": "Seed Reg Local",
        "phone_number": "9000001002",
        "city": "Pune",
        "state_code": "27",
        "pincode": "411001",
        "registration_type": PartyRegistrationType.REGISTERED,
        "gstin": "27CCCCC0000C1Z5",
        "pan": "CCCCC0000C",
    },
    {
        "customer_name": "Seed Reg Interstate",
        "phone_number": "9000001003",
        "city": "Bengaluru",
        "state_code": "29",
        "pincode": "560001",
        "registration_type": PartyRegistrationType.REGISTERED,
        "gstin": "29DDDDD0000D1Z5",
        "pan": "DDDDD0000D",
    },
)

DEMO_VENDORS = (
    {
        "vendor_name": "Seed Unreg Vendor",
        "phone_number": "9100001001",
        "city": "Mumbai",
        "state_code": "27",
        "pincode": "400002",
        "registration_type": PartyRegistrationType.UNREGISTERED,
    },
    {
        "vendor_name": "Seed Reg Vendor",
        "phone_number": "9100001002",
        "city": "Thane",
        "state_code": "27",
        "pincode": "400601",
        "registration_type": PartyRegistrationType.REGISTERED,
        "gstin": "27EEEEE0000E1Z5",
        "pan": "EEEEE0000E",
    },
)

# (parent_name_or_None, name, description)
DEMO_CATEGORY_TREE = (
    (None, "Fabric", "Fabrics and materials"),
    (None, "Ready-made", "Finished ready-to-sell items"),
    (None, "Accessories", "Accessories and add-ons"),
    ("Fabric", "Cotton", "Cotton fabrics"),
    ("Fabric", "Silk", "Silk fabrics"),
    ("Accessories", "Buttons", "Buttons and fasteners"),
    ("Accessories", "Zippers", "Zippers and closures"),
)

DEMO_UNITS = (
    ("pcs", "Pieces"),
    ("m", "Metres"),
    ("kg", "Kilograms"),
    ("roll", "Roll"),
    ("set", "Set"),
)

# category name preferred first, then fallbacks
DEMO_PRODUCTS = (
    {
        "sku": "DEMO-FAB-001",
        "name": "Seed Cotton Cloth",
        "category_names": ("Cotton", "Fabric"),
        "unit_code": "m",
        "hsn_sac": "5208",
        "selling_rate": 250.0,
        "mrp": 299.0,
        "gst_rate": 5.0,
        "opening_qty": 50.0,
    },
    {
        "sku": "DEMO-RM-001",
        "name": "Seed Kurta Set",
        "category_names": ("Ready-made",),
        "unit_code": "set",
        "hsn_sac": "6204",
        "selling_rate": 1200.0,
        "mrp": 1499.0,
        "gst_rate": 12.0,
        "opening_qty": 10.0,
    },
    {
        "sku": "DEMO-ACC-001",
        "name": "Seed Button Pack",
        "category_names": ("Buttons", "Accessories"),
        "unit_code": "pcs",
        "hsn_sac": "9606",
        "selling_rate": 45.0,
        "mrp": 60.0,
        "gst_rate": 18.0,
        "opening_qty": 100.0,
    },
    {
        "sku": "DEMO-NOHSN-001",
        "name": "Seed Sample No HSN",
        "category_names": ("Accessories",),
        "unit_code": "pcs",
        "hsn_sac": "",
        "selling_rate": 20.0,
        "mrp": 25.0,
        "gst_rate": 0.0,
        "opening_qty": 5.0,
    },
)


def _parse_registration(value: str) -> PartyRegistrationType:
    raw = (value or "").strip()
    for member in PartyRegistrationType:
        if member.value.lower() == raw.lower() or member.name.lower() == raw.lower():
            return member
    logger.warning(
        "Unknown SEED_BUSINESS_REGISTRATION=%r; defaulting to Unregistered", value
    )
    return PartyRegistrationType.UNREGISTERED


def _inventory_service(db: Database) -> InventoryAppService:
    rate_history = ProductRateHistoryService(
        MongoProductRateHistoryRepository(db, "product_selling_rate_history"),
        MongoProductRateHistoryRepository(db, "product_mrp_history"),
        MongoProductRateHistoryRepository(db, "product_gst_rate_history"),
    )
    return InventoryAppService(
        MongoProductCategoryRepository(db),
        MongoInventoryProductRepository(db),
        MongoStockMovementRepository(db),
        MongoProductUnitRepository(db),
        rate_history=rate_history,
    )


def _ensure_unit(inventory: InventoryAppService, code: str, label: str) -> str:
    return inventory.find_or_create_unit(code, label).id


def _ensure_category(
    inventory: InventoryAppService,
    name: str,
    description: str = "",
    parent_id: Optional[str] = None,
) -> str:
    parent_id = parent_id or None
    for category in inventory.list_categories(active_only=False):
        cat_parent = category.parent_id or None
        if category.name == name and cat_parent == parent_id:
            return category.id
    try:
        category = inventory.create_category(
            name, description=description, parent_id=parent_id
        )
        return category.id
    except ValidationError:
        # Race or SEED_CONFIG already inserted the same name under parent
        for category in inventory.list_categories(active_only=False):
            cat_parent = category.parent_id or None
            if category.name == name and cat_parent == parent_id:
                return category.id
        raise


def seed_business(db: Database, settings: AppSettings) -> None:
    registration = _parse_registration(settings.seed_business_registration)
    state = (settings.seed_business_state or "").strip() or "27"
    gstin = (settings.seed_business_gstin or "").strip()
    pan = (settings.seed_business_pan or "").strip()
    if registration in {
        PartyRegistrationType.REGISTERED,
        PartyRegistrationType.COMPOSITION,
    }:
        if not gstin:
            # Build a format-valid GSTIN from state + default PAN
            pan = pan or "AAAAA0000A"
            gstin = f"{state}{pan}1Z5"
        elif not pan and len(gstin) >= 12:
            pan = gstin[2:12]

    service = BusinessAppService(MongoBusinessProfileRepository(db))
    service.update_profile(
        legal_name=settings.seed_business_legal_name or "Seed Demo Business",
        trade_name=settings.seed_business_trade_name or "Seed Demo",
        address_line1="1 Seed Street",
        city="Mumbai" if state == "27" else "Bengaluru" if state == "29" else "City",
        state_code=state,
        pincode="400001" if state == "27" else "560001",
        phone="9000000000",
        email="seed@example.com",
        gstin=gstin,
        pan=pan,
        registration_type=registration,
        composition_tax_rate=float(settings.seed_composition_rate or 1.0),
    )
    logger.info("Seeded business profile as %s (state=%s)", registration.value, state)


def seed_customers(db: Database) -> None:
    customers = CustomerAppService(
        MongoCustomerRepository(db),
        MongoAccountRepository(db),
    )
    repo = MongoCustomerRepository(db)
    for row in DEMO_CUSTOMERS:
        if repo.find_by_phone(row["phone_number"]):
            continue
        try:
            customers.create_customer(CustomerInput(**row))
        except DuplicateCustomerError:
            continue
        except ValidationError as exc:
            logger.warning("Skip seed customer %s: %s", row["customer_name"], exc)
    logger.info("Seed customers ensured")


def seed_vendors(db: Database) -> None:
    vendors = VendorAppService(
        MongoVendorRepository(db),
        MongoAccountRepository(db),
    )
    repo = MongoVendorRepository(db)
    for row in DEMO_VENDORS:
        if repo.find_by_phone(row["phone_number"]):
            continue
        try:
            vendors.create_vendor(VendorInput(**row))
        except DuplicateVendorError:
            continue
        except ValidationError as exc:
            logger.warning("Skip seed vendor %s: %s", row["vendor_name"], exc)
    logger.info("Seed vendors ensured")


def seed_categories(db: Database) -> None:
    inventory = _inventory_service(db)
    by_name: dict[str, str] = {}
    for parent_name, name, description in DEMO_CATEGORY_TREE:
        parent_id = by_name.get(parent_name) if parent_name else None
        if parent_name and parent_id is None:
            # Parent may already exist from SEED_CONFIG
            for category in inventory.list_categories(active_only=False):
                if category.name == parent_name and not category.parent_id:
                    parent_id = category.id
                    by_name[parent_name] = parent_id
                    break
        cat_id = _ensure_category(inventory, name, description, parent_id)
        by_name[name] = cat_id
    logger.info("Seed categories ensured")


def seed_products(db: Database) -> None:
    inventory = _inventory_service(db)

    # Units required for products
    unit_ids: dict[str, str] = {}
    for code, label in DEMO_UNITS:
        unit_ids[code] = _ensure_unit(inventory, code, label)

    # Ensure at least root categories exist for product assignment
    categories_by_name: dict[str, str] = {}
    for category in inventory.list_categories(active_only=False):
        categories_by_name[category.name] = category.id
    for parent_name, name, description in DEMO_CATEGORY_TREE:
        if name in categories_by_name:
            continue
        parent_id = categories_by_name.get(parent_name) if parent_name else None
        categories_by_name[name] = _ensure_category(
            inventory, name, description, parent_id
        )

    product_repo = MongoInventoryProductRepository(db)
    for row in DEMO_PRODUCTS:
        if product_repo.find_by_sku(row["sku"]):
            continue
        category_id = None
        for cat_name in row["category_names"]:
            if cat_name in categories_by_name:
                category_id = categories_by_name[cat_name]
                break
        if not category_id:
            logger.warning("Skip product %s: no category found", row["sku"])
            continue
        unit_code = row["unit_code"]
        try:
            inventory.create_product(
                row["sku"],
                row["name"],
                category_id,
                opening_qty=row["opening_qty"],
                unit_id=unit_ids.get(unit_code, ""),
                unit_code=unit_code,
                hsn_sac=row["hsn_sac"],
                selling_rate=row["selling_rate"],
                mrp=row["mrp"],
                gst_rate=row["gst_rate"],
                gst_required=False,
            )
        except ValidationError as exc:
            logger.warning("Skip seed product %s: %s", row["sku"], exc)
    logger.info("Seed products ensured")


def run_demo_seed(db: Database, settings: AppSettings) -> None:
    """Run enabled demo entity seeds. Order: business → categories → products → parties."""
    if settings.seed_business:
        seed_business(db, settings)
    if settings.seed_categories:
        seed_categories(db)
    if settings.seed_products:
        seed_products(db)
    if settings.seed_customers:
        seed_customers(db)
    if settings.seed_vendors:
        seed_vendors(db)
