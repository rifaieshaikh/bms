"""Baseline migration — ensures schema_migrations collection exists."""

from pymongo.database import Database


def up(db: Database) -> None:
    db.schema_migrations.create_index("version", unique=True)
