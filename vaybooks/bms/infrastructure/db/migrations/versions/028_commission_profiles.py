"""Commission profiles and accrual ledger indexes."""

from pymongo.database import Database

from vaybooks.bms.infrastructure.db.indexes import ensure_indexes


def up(db: Database) -> None:
    ensure_indexes(db)
    # Drop legacy flat default fields once profiles exist (best-effort).
    db.commission_agents.update_many(
        {"commission_profile": {"$exists": False}},
        {
            "$set": {
                "commission_profile": {
                    "include_unpaid": True,
                    "min_sales_amount": 0.0,
                    "min_collection_amount": 0.0,
                    "threshold_reset_period": "monthly",
                    "conflict_strategy": "maximize",
                    "sales_rules": [],
                    "collection_rules": [],
                }
            }
        },
    )
    db.workers.update_many(
        {"commission_enabled": {"$exists": False}},
        {"$set": {"commission_enabled": False, "commission_profile": None}},
    )
