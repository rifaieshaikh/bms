"""Backfill per-item MPH snapshots for invoiced and delivered items."""

from pymongo.database import Database

from vaybooks.bms.infrastructure.db.backfill_item_mph import backfill_item_mph


def up(db: Database) -> None:
    backfill_item_mph(db)
