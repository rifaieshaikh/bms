"""Idempotent default location seeding (MAIN warehouse + STORE1)."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from vaybooks.bms.domain.shared.enums import LocationType


def _ensure_location(
    db: Database,
    *,
    code: str,
    name: str,
    location_type: LocationType,
) -> str:
    """Insert location by code if missing; return its id."""
    coll = db.warehouses
    existing = coll.find_one({"code": code})
    if existing:
        return str(existing["_id"])

    now = datetime.utcnow()
    location_id = uuid4().hex
    try:
        coll.insert_one(
            {
                "_id": location_id,
                "code": code,
                "name": name,
                "location_type": location_type.value,
                "address": "",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        return location_id
    except DuplicateKeyError:
        existing = coll.find_one({"code": code})
        if existing:
            return str(existing["_id"])
        raise


def ensure_default_locations(db: Database) -> tuple[str, str]:
    """Ensure MAIN warehouse and STORE1 retail store exist.

    Returns ``(main_id, store_id)``.
    """
    main_id = _ensure_location(
        db,
        code="MAIN",
        name="Main Warehouse",
        location_type=LocationType.WAREHOUSE,
    )
    store_id = _ensure_location(
        db,
        code="STORE1",
        name="Retail Store",
        location_type=LocationType.RETAIL_STORE,
    )
    return main_id, store_id
