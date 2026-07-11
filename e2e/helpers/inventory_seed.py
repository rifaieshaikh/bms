"""Programmatic inventory seeding for E2E tests."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.infrastructure.db.connection import get_database_from_uri
from vaybooks.bms.infrastructure.repositories.mongo_inventory_repository import (
    MongoInventoryProductRepository,
    MongoProductCategoryRepository,
    MongoProductUnitRepository,
    MongoStockMovementRepository,
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
        raise RuntimeError("MONGODB_URI required for inventory seed")
    return uri


def _mongo_database() -> str:
    secrets = _read_secrets()
    if secrets.get("MONGODB_DATABASE"):
        return secrets["MONGODB_DATABASE"]
    return os.environ.get("MONGODB_DATABASE", "zahcci_customization")


def _inventory_service() -> InventoryAppService:
    db = get_database_from_uri(_mongo_uri(), _mongo_database())
    return InventoryAppService(
        MongoProductCategoryRepository(db),
        MongoInventoryProductRepository(db),
        MongoStockMovementRepository(db),
        MongoProductUnitRepository(db),
    )


def create_category(name: str, parent_id: str | None = None) -> str:
    service = _inventory_service()
    category = service.create_category(name, parent_id=parent_id)
    return category.id


def create_category_chain(*names: str) -> list[str]:
    """Create a root-to-leaf chain; returns category ids in order."""
    parent_id: str | None = None
    ids: list[str] = []
    for name in names:
        parent_id = create_category(name, parent_id)
        ids.append(parent_id)
    return ids


def create_siblings_same_name(parent_ids: list[str], name: str) -> list[str]:
    """Create the same category name under multiple parents."""
    return [create_category(name, pid) for pid in parent_ids]


def create_product_in_category(category_id: str, sku: str, name: str) -> str:
    service = _inventory_service()
    product = service.create_product(sku, name, category_id, opening_qty=0)
    return product.id


def unique_sku(prefix: str = "E2E") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
