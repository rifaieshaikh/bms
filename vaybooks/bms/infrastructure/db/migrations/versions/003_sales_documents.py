"""Seed Estimate/Quotation counters and document template storage."""


def up(db) -> None:
    for counter_id, prefix in (
        ("estimate_number", "EST"),
        ("quotation_number", "QT"),
    ):
        db.counters.update_one(
            {"_id": counter_id},
            {"$setOnInsert": {"prefix": prefix, "current_value": 0}},
            upsert=True,
        )
    db.business_profile.update_one(
        {"_id": "default", "document_templates": {"$exists": False}},
        {"$set": {"document_templates": {}, "bank_accounts": []}},
    )
