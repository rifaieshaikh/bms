"""Remove transactional business data while keeping config/reference collections."""

from __future__ import annotations

import logging

from pymongo.database import Database

from vaybooks.bms.infrastructure.db.seed import COUNTERS, DEFAULT_ACCOUNTS

logger = logging.getLogger("vaybooks.bms.db.purge")

BUSINESS_COLLECTIONS = (
    "customization_orders",
    "bill_registry",
    "customers",
    "vendors",
    "workers",
    "invoices",
    "deliveries",
    "expenses",
    "time_entries",
    "vouchers",
    "product_categories",
    "inventory_products",
    "stock_movements",
)

DEFAULT_ACCOUNT_NAMES = {name for name, _, _ in DEFAULT_ACCOUNTS}


def purge_business_data(db: Database) -> dict[str, int]:
    """Delete business documents and reset counters / linked accounts.

    Preserves activity_config, vendor_services, schema_migrations, and the
    default chart-of-accounts rows from core seed.
    """
    removed: dict[str, int] = {}

    for collection_name in BUSINESS_COLLECTIONS:
        if collection_name not in db.list_collection_names():
            removed[collection_name] = 0
            continue
        result = db[collection_name].delete_many({})
        removed[collection_name] = result.deleted_count

    linked_accounts = db.accounts.delete_many(
        {
            "$or": [
                {"linked_customer_id": {"$type": "string"}},
                {"linked_vendor_id": {"$type": "string"}},
                {"linked_worker_id": {"$type": "string"}},
            ]
        }
    )
    removed["linked_accounts"] = linked_accounts.deleted_count

    non_default_accounts = db.accounts.delete_many(
        {"account_name": {"$nin": list(DEFAULT_ACCOUNT_NAMES)}}
    )
    removed["non_default_accounts"] = non_default_accounts.deleted_count

    db.accounts.update_many(
        {"account_name": {"$in": list(DEFAULT_ACCOUNT_NAMES)}},
        {"$set": {"linked_customer_id": None, "linked_vendor_id": None, "linked_worker_id": None}},
    )
    for account in db.accounts.find({"account_name": {"$in": list(DEFAULT_ACCOUNT_NAMES)}}):
        db.accounts.update_one(
            {"_id": account["_id"]},
            {"$set": {"current_balance": account.get("opening_balance", 0)}},
        )

    for counter_id, _prefix in COUNTERS:
        db.counters.update_one(
            {"_id": counter_id},
            {"$set": {"current_value": 0}},
            upsert=False,
        )

    logger.warning("Purged business data from database: %s", removed)
    return removed
