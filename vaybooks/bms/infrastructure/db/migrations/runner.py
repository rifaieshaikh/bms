"""Database migration framework."""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from pymongo.database import Database

logger = logging.getLogger("vaybooks.bms.migrations")

MIGRATIONS_COLLECTION = "schema_migrations"
VERSIONS_PACKAGE = "vaybooks.bms.infrastructure.db.migrations.versions"


def _versions_dir() -> Path:
    return Path(__file__).resolve().parent / "versions"


def _discover_migrations() -> list[tuple[str, Callable[[Database], None]]]:
    migrations: list[tuple[str, Callable[[Database], None]]] = []
    versions_path = _versions_dir()
    if not versions_path.exists():
        return migrations
    for path in sorted(versions_path.glob("*.py")):
        if path.name.startswith("_"):
            continue
        version = path.stem
        module = importlib.import_module(f"{VERSIONS_PACKAGE}.{version}")
        up = getattr(module, "up", None)
        if callable(up):
            migrations.append((version, up))
    return migrations


def _checksum(version: str, fn: Callable[[Database], None]) -> str:
    source = Path(fn.__code__.co_filename).read_bytes()
    return hashlib.sha256(f"{version}:{source!r}".encode()).hexdigest()[:16]


def _applied_versions(db: Database) -> set[str]:
    return {doc["version"] for doc in db[MIGRATIONS_COLLECTION].find({}, {"version": 1})}


def _write_local_history(version: str, checksum: str) -> None:
    from vaybooks.bms.infrastructure.config.paths import get_data_dir
    from vaybooks.bms.infrastructure.config.runtime import is_desktop

    if not is_desktop():
        return
    data_dir = get_data_dir()
    if not data_dir:
        return
    history_path = data_dir / "migrations" / "history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    history.append(
        {
            "version": version,
            "checksum": checksum,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def run_pending_migrations(db: Database) -> list[str]:
    applied: list[str] = []
    done = _applied_versions(db)
    for version, up in _discover_migrations():
        if version in done:
            continue
        checksum = _checksum(version, up)
        logger.info("Applying migration %s", version)
        up(db)
        db[MIGRATIONS_COLLECTION].insert_one(
            {
                "version": version,
                "checksum": checksum,
                "applied_at": datetime.now(timezone.utc),
            }
        )
        _write_local_history(version, checksum)
        applied.append(version)
        logger.info("Migration %s applied", version)
    return applied
