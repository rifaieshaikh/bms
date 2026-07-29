"""Commission agents collection and linked_agent_id account index."""

from pymongo.database import Database

from vaybooks.bms.infrastructure.db.indexes import ensure_indexes


def up(db: Database) -> None:
    ensure_indexes(db)
