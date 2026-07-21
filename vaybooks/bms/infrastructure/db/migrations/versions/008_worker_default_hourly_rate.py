"""Backfill default_hourly_rate on worker documents."""

from __future__ import annotations

from pymongo.database import Database


def up(db: Database) -> None:
    db.workers.update_many(
        {"default_hourly_rate": {"$exists": False}},
        {"$set": {"default_hourly_rate": 0.0}},
    )
