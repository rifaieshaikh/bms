"""Seed configurable measurement sections."""

from __future__ import annotations

from pymongo.database import Database


def up(db: Database) -> None:
    from vaybooks.bms.infrastructure.db.measurement_seed import ensure_measurement_specs

    ensure_measurement_specs(db)
