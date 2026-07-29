"""Ensure location_id / location_ids indexes for location association."""

from pymongo.database import Database

from vaybooks.bms.infrastructure.db.indexes import ensure_indexes


def up(db: Database) -> None:
    ensure_indexes(db)
