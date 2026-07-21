"""Seed project templates and document counters for Projects module."""

from __future__ import annotations

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError


def up(db: Database) -> None:
    from vaybooks.bms.infrastructure.db.project_seed import ensure_project_templates

    ensure_project_templates(db)

    counters = [
        ("project_number", "PRJ"),
        ("project_quotation_number", "PQ"),
        ("project_work_order_number", "PWO"),
        ("project_ra_number", "PRA"),
        ("project_proforma_number", "PPF"),
        ("project_variation_number", "PV"),
    ]
    for counter_id, prefix in counters:
        if db.counters.find_one({"_id": counter_id}):
            continue
        try:
            db.counters.insert_one(
                {"_id": counter_id, "prefix": prefix, "current_value": 0}
            )
        except DuplicateKeyError:
            pass
