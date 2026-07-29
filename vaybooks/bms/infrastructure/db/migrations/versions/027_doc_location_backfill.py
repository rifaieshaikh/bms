"""Backfill document location_id / location_name from first active warehouse."""

from datetime import datetime

from pymongo.database import Database


_COLLECTIONS = (
    "estimates",
    "quotations",
    "purchase_orders",
    "purchase_returns",
    "vouchers",
    "customization_orders",
    "deliveries",
    "invoices",
    "expenses",
    "projects",
    "crm_leads",
    "crm_activities",
    "sales_orders",
    "delivery_notes",
    "sales_returns",
    "goods_receipts",
    "production_batches",
)


def up(db: Database) -> None:
    now = datetime.utcnow()
    warehouses = list(
        db.warehouses.find(
            {"is_active": {"$ne": False}},
            {"_id": 1, "name": 1, "code": 1},
        ).sort("code", 1)
    )
    if not warehouses:
        return

    first = warehouses[0]
    location_id = str(first["_id"])
    location_name = str(first.get("name") or "").strip()

    missing = {
        "$or": [
            {"location_id": {"$exists": False}},
            {"location_id": None},
            {"location_id": ""},
        ]
    }
    for name in _COLLECTIONS:
        db[name].update_many(
            missing,
            {
                "$set": {
                    "location_id": location_id,
                    "location_name": location_name,
                    "updated_at": now,
                }
            },
        )
