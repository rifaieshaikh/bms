"""Backfill party location_ids with all active warehouse/location ids."""

from datetime import datetime

from pymongo.database import Database


def up(db: Database) -> None:
    now = datetime.utcnow()
    location_ids = [
        str(doc["_id"])
        for doc in db.warehouses.find({"is_active": {"$ne": False}}, {"_id": 1})
    ]
    if not location_ids:
        # No locations yet — leave empty; seed will create locations later.
        return

    collections = (
        "customers",
        "vendors",
        "commission_agents",
        "delivery_partners",
        "workers",
    )
    for name in collections:
        db[name].update_many(
            {
                "$or": [
                    {"location_ids": {"$exists": False}},
                    {"location_ids": None},
                    {"location_ids": []},
                ]
            },
            {"$set": {"location_ids": list(location_ids), "updated_at": now}},
        )
