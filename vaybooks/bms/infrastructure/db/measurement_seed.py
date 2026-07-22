"""Idempotent measurement-spec seeding shared by startup seed and migrations."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError


def ensure_measurement_specs(db: Database) -> int:
    """Insert any missing measurement spec rows from the seed catalog.

    Also reactivates inactive Extended rows so the measurement form shows the
    full person-type catalog. Returns the number of documents inserted.
    """
    from vaybooks.bms.domain.boutique.measurements.seed_catalog import dedupe_seed_specs

    now = datetime.utcnow()
    inserted = 0
    default_sections = [
        ("Meta", "Meta", 0),
        ("Head", "Head / Neck", 100),
        ("Torso", "Torso", 200),
        ("Arms", "Arms", 300),
        ("Lower", "Lower Body", 400),
        ("Lengths", "Garment Lengths", 500),
    ]
    for key, label, sort_order in default_sections:
        if db.measurement_sections.find_one({"key": key}):
            continue
        try:
            db.measurement_sections.insert_one(
                {
                    "_id": uuid4().hex,
                    "key": key,
                    "label": label,
                    "sort_order": sort_order,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        except DuplicateKeyError:
            pass

    for spec in dedupe_seed_specs():
        query = {
            "key": spec["key"],
            "person_types": {"$all": spec["person_types"]},
            "is_core": spec.get("is_core", True),
        }
        existing = db.measurement_specs.find_one(query)
        if existing:
            updates = {}
            if not existing.get("is_active", True):
                updates["is_active"] = True
            for attr in (
                "label",
                "section",
                "value_type",
                "unit",
                "required",
                "sort_order",
                "options",
            ):
                if existing.get(attr) != spec.get(attr):
                    updates[attr] = spec.get(attr)
            if updates:
                updates["updated_at"] = now
                db.measurement_specs.update_one(
                    {"_id": existing["_id"]}, {"$set": updates}
                )
            continue
        try:
            db.measurement_specs.insert_one(
                {
                    "_id": uuid4().hex,
                    **spec,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            inserted += 1
        except DuplicateKeyError:
            pass

    if not db.counters.find_one({"_id": "measurement_number"}):
        try:
            db.counters.insert_one(
                {
                    "_id": "measurement_number",
                    "prefix": "MS",
                    "current_value": 0,
                }
            )
        except DuplicateKeyError:
            pass
    return inserted
