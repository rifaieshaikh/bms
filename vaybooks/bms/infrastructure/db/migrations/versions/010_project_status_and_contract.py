"""Remap project statuses and backfill contract value fields."""

from __future__ import annotations

from pymongo.database import Database


def up(db: Database) -> None:
    db.projects.update_many(
        {"status": "Completed"},
        {"$set": {"status": "Physically Completed"}},
    )
    db.projects.update_many(
        {"status": "Closed"},
        {"$set": {"status": "Financially Closed"}},
    )

    for project in db.projects.find({}, {"contract_value": 1}):
        contract_value = float(project.get("contract_value") or 0.0)
        updates: dict = {}
        if "original_contract_value" not in project:
            updates["original_contract_value"] = contract_value
        if "revised_contract_value" not in project:
            updates["revised_contract_value"] = contract_value
        if updates:
            db.projects.update_one({"_id": project["_id"]}, {"$set": updates})
