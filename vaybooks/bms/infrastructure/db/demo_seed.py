"""Idempotent multi-vertical demo seed (customers, vendors, categories, products, business)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from vaybooks.bms.application.settings.business.service import BusinessAppService
from vaybooks.bms.application.parties.customers.service import CustomerAppService
from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.application.parties.vendors.service import VendorAppService
from vaybooks.bms.domain.parties.customers.entities import CustomerInput
from vaybooks.bms.domain.inventory.rate_history_service import ProductRateHistoryService
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCustomerError,
    DuplicateVendorError,
    ValidationError,
)
from vaybooks.bms.domain.parties.vendors.entities import VendorInput
from vaybooks.bms.infrastructure.db.demo_seed_profiles import (
    DEMO_UNITS,
    KERALA_STATE,
    PROFILES,
    build_customer_rows,
    build_vendor_rows,
    expand_category_tree,
    expand_products,
    profiles_to_run,
    resolve_business_settings,
)
from vaybooks.bms.infrastructure.repositories.finance.mongo_accounting_repository import (
    MongoAccountRepository,
)
from vaybooks.bms.infrastructure.repositories.shared.mongo_business_profile_repository import (
    MongoBusinessProfileRepository,
)
from vaybooks.bms.infrastructure.repositories.parties.mongo_customer_repository import (
    MongoCustomerRepository,
)
from vaybooks.bms.infrastructure.repositories.inventory.mongo_inventory_repository import (
    MongoInventoryProductRepository,
    MongoProductCategoryRepository,
    MongoProductUnitRepository,
    MongoStockMovementRepository,
)
from vaybooks.bms.infrastructure.repositories.inventory.mongo_product_rate_history_repository import (
    MongoProductRateHistoryRepository,
)
from vaybooks.bms.infrastructure.repositories.parties.mongo_vendor_repository import (
    MongoVendorRepository,
)

if TYPE_CHECKING:
    from pymongo.database import Database

    from vaybooks.bms.infrastructure.config.settings import AppSettings

logger = logging.getLogger("vaybooks.bms.demo_seed")


def _parse_registration(value: str) -> PartyRegistrationType:
    raw = (value or "").strip()
    for member in PartyRegistrationType:
        if member.value.lower() == raw.lower() or member.name.lower() == raw.lower():
            return member
    logger.warning(
        "Unknown registration=%r; defaulting to Unregistered", value
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
        for category in inventory.list_categories(active_only=False):
            cat_parent = category.parent_id or None
            if category.name == name and cat_parent == parent_id:
                return category.id
        raise


def _kerala_city(state: str) -> tuple[str, str]:
    if state == "32":
        return "Kochi", "682001"
    if state == "27":
        return "Mumbai", "400001"
    if state == "29":
        return "Bengaluru", "560001"
    return "Kochi", "682001"


def seed_business(db: Database, settings: AppSettings) -> None:
    selected = profiles_to_run(getattr(settings, "seed_profile", "boutique"))
    biz = resolve_business_settings(
        selected,
        blocks=getattr(settings, "seed_business_blocks", None) or {},
        flat_overlay=getattr(settings, "seed_business_flat_overrides", None) or {},
    )
    registration = _parse_registration(str(biz.get("registration", "Unregistered")))
    state = str(biz.get("state") or KERALA_STATE).strip() or KERALA_STATE
    gstin = str(biz.get("gstin") or "").strip()
    pan = str(biz.get("pan") or "").strip()
    if registration in {
        PartyRegistrationType.REGISTERED,
        PartyRegistrationType.COMPOSITION,
    }:
        if not gstin:
            pan = pan or "AAAAA0000A"
            gstin = f"{state}{pan}1Z5"
        elif not pan and len(gstin) >= 12:
            pan = gstin[2:12]

    city, pincode = _kerala_city(state)
    service = BusinessAppService(MongoBusinessProfileRepository(db))
    service.update_profile(
        legal_name=str(biz.get("legal_name") or "Seed Demo Business"),
        trade_name=str(biz.get("trade_name") or "Seed Demo"),
        address_line1="1 Seed Street",
        city=city,
        state_code=state,
        pincode=pincode,
        phone="9000000000",
        email="seed@example.com",
        gstin=gstin,
        pan=pan,
        registration_type=registration,
        composition_tax_rate=float(biz.get("composition_rate") or 1.0),
    )
    logger.info(
        "Seeded business profile as %s (state=%s, profiles=%s)",
        registration.value,
        state,
        ",".join(selected),
    )


def seed_customers_for_profile(
    db: Database, profile_key: str, count: int
) -> None:
    profile = PROFILES[profile_key]
    customers = CustomerAppService(
        MongoCustomerRepository(db),
        MongoAccountRepository(db),
    )
    repo = MongoCustomerRepository(db)
    for row in build_customer_rows(profile, count):
        if repo.find_by_phone(row["phone_number"]):
            continue
        try:
            customers.create_customer(CustomerInput(**row))
        except DuplicateCustomerError:
            continue
        except ValidationError as exc:
            logger.warning("Skip seed customer %s: %s", row["customer_name"], exc)
    logger.info("Seed customers ensured for %s (count=%s)", profile_key, count)


def seed_vendors_for_profile(db: Database, profile_key: str, count: int) -> None:
    profile = PROFILES[profile_key]
    vendors = VendorAppService(
        MongoVendorRepository(db),
        MongoAccountRepository(db),
    )
    repo = MongoVendorRepository(db)
    for row in build_vendor_rows(profile, count):
        if repo.find_by_phone(row["phone_number"]):
            continue
        try:
            vendors.create_vendor(VendorInput(**row))
        except DuplicateVendorError:
            continue
        except ValidationError as exc:
            logger.warning("Skip seed vendor %s: %s", row["vendor_name"], exc)
    logger.info("Seed vendors ensured for %s (count=%s)", profile_key, count)


def seed_categories_for_profile(
    db: Database, profile_key: str, count: int
) -> None:
    profile = PROFILES[profile_key]
    inventory = _inventory_service(db)
    # Prefix root names with profile label to avoid collisions across verticals
    prefix = profile.label
    by_name: dict[str, str] = {}
    for parent_name, name, description in expand_category_tree(profile, count):
        if parent_name is None:
            full_name = f"{prefix} · {name}"
            parent_id = None
        else:
            root_key = f"{prefix} · {parent_name}"
            parent_id = by_name.get(root_key)
            if parent_id is None:
                parent_id = _ensure_category(
                    inventory, root_key, f"{parent_name} ({prefix})"
                )
                by_name[root_key] = parent_id
            full_name = f"{prefix} · {parent_name} · {name}"
        cat_id = _ensure_category(inventory, full_name, description, parent_id)
        by_name[full_name] = cat_id
        if parent_name is None:
            by_name[f"{prefix} · {name}"] = cat_id
    logger.info("Seed categories ensured for %s (count=%s)", profile_key, count)


def seed_products_for_profile(db: Database, profile_key: str, count: int) -> None:
    profile = PROFILES[profile_key]
    inventory = _inventory_service(db)
    prefix = profile.label

    unit_ids: dict[str, str] = {}
    for code, label in DEMO_UNITS:
        unit_ids[code] = _ensure_unit(inventory, code, label)

    # Ensure category tree exists for product assignment
    seed_categories_for_profile(db, profile_key, max(count, 20))

    categories_by_name: dict[str, str] = {
        c.name: c.id for c in inventory.list_categories(active_only=False)
    }

    product_repo = MongoInventoryProductRepository(db)
    for row in expand_products(profile, count):
        if product_repo.find_by_sku(row["sku"]):
            continue
        category_id = None
        for cat_name in row["category_names"]:
            # Match prefixed leaf or root
            candidates = [
                f"{prefix} · {cat_name}",
                f"{prefix} · {cat_name} · {cat_name}",
            ]
            # Also search any category ending with · cat_name
            for full, cid in categories_by_name.items():
                if full == f"{prefix} · {cat_name}" or full.endswith(f" · {cat_name}"):
                    category_id = cid
                    break
            if category_id:
                break
            for cand in candidates:
                if cand in categories_by_name:
                    category_id = categories_by_name[cand]
                    break
            if category_id:
                break
        if not category_id:
            # Fallback: any category for this profile prefix
            for full, cid in categories_by_name.items():
                if full.startswith(f"{prefix} ·"):
                    category_id = cid
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
    logger.info("Seed products ensured for %s (count=%s)", profile_key, count)


def run_demo_seed(db: Database, settings: AppSettings) -> None:
    """Seed selected verticals from SEED_PROFILE (single control).

    Set ``SEED_PROFILE`` to a profile key, comma-list, or ``all``.
    Use ``none`` / empty to disable. When enabled, seeds business +
    categories + products + customers + vendors for each selected profile.
    """
    selected = profiles_to_run(getattr(settings, "seed_profile", "none"))
    if not selected:
        logger.info("Demo profile seed skipped (SEED_PROFILE=%r)", settings.seed_profile)
        return

    logger.info("Demo seed profiles: %s", ",".join(selected))
    seed_business(db, settings)

    for profile_key in selected:
        if profile_key not in PROFILES:
            logger.warning("Unknown seed profile %r; skipping", profile_key)
            continue
        seed_categories_for_profile(
            db, profile_key, int(settings.seed_category_count)
        )
        seed_products_for_profile(
            db, profile_key, int(settings.seed_product_count)
        )
        seed_customers_for_profile(
            db, profile_key, int(settings.seed_customer_count)
        )
        seed_vendors_for_profile(
            db, profile_key, int(settings.seed_vendor_count)
        )
