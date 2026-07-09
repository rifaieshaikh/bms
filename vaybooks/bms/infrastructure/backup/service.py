"""Full backup, restore, and scheduled backup support."""

from __future__ import annotations

import json
import logging
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from vaybooks.bms import __version__
from vaybooks.bms.application.export_app_service import _serialize_bson
from vaybooks.bms.infrastructure.config.paths import get_backups_dir, get_config_path
from vaybooks.bms.infrastructure.config.runtime import is_desktop
from vaybooks.bms.infrastructure.config.settings import get_settings

logger = logging.getLogger("vaybooks.bms.backup")

ALL_COLLECTIONS = [
    "customers",
    "vendors",
    "accounts",
    "customization_orders",
    "bill_registry",
    "activity_config",
    "vendor_services",
    "workers",
    "time_entries",
    "expenses",
    "invoices",
    "deliveries",
    "vouchers",
    "counters",
    "schema_migrations",
]


class BackupService:
    def __init__(self, db: Database):
        self._db = db

    def export_all_collections(self) -> dict[str, list[dict[str, Any]]]:
        backup: dict[str, list[dict[str, Any]]] = {}
        for name in ALL_COLLECTIONS:
            if name in self._db.list_collection_names():
                backup[name] = list(self._db[name].find())
            else:
                backup[name] = []
        return backup

    def create_backup_zip(self) -> bytes:
        payload = {
            "version": __version__,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": get_settings().db_name,
            "collections": _serialize_bson(self.export_all_collections()),
        }
        config_path = get_config_path()
        if config_path and config_path.exists():
            payload["config_snapshot"] = config_path.read_text(encoding="utf-8")

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("backup.json", json.dumps(payload, indent=2, default=str))
        return buffer.getvalue()

    def save_backup_to_disk(self, label: str | None = None) -> Path | None:
        if not is_desktop():
            return None
        backups_dir = get_backups_dir()
        if not backups_dir:
            return None
        backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        name = label or f"backup_{stamp}"
        path = backups_dir / f"{name}.zip"
        path.write_bytes(self.create_backup_zip())
        logger.info("Backup saved to %s", path)
        return path

    def validate_backup_zip(self, data: bytes) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        try:
            with zipfile.ZipFile(BytesIO(data)) as zf:
                if "backup.json" not in zf.namelist():
                    return {}, ["backup.json not found in zip"]
                payload = json.loads(zf.read("backup.json"))
        except Exception as exc:
            return {}, [str(exc)]

        collections = payload.get("collections", {})
        if not isinstance(collections, dict):
            errors.append("collections must be a dict")
        return payload, errors

    def restore_from_zip(self, data: bytes, dry_run: bool = False) -> dict[str, int]:
        payload, errors = self.validate_backup_zip(data)
        if errors:
            raise ValueError("; ".join(errors))

        collections = payload.get("collections", {})
        stats: dict[str, int] = {}
        if dry_run:
            for name, docs in collections.items():
                stats[name] = len(docs) if isinstance(docs, list) else 0
            return stats

        for name, docs in collections.items():
            if name not in ALL_COLLECTIONS or not isinstance(docs, list):
                continue
            coll = self._db[name]
            coll.delete_many({})
            if docs:
                for doc in docs:
                    if "_id" in doc and isinstance(doc["_id"], str):
                        try:
                            doc["_id"] = ObjectId(doc["_id"])
                        except Exception:
                            pass
                coll.insert_many(docs)
            stats[name] = len(docs)
        logger.info("Restore complete: %s", stats)
        return stats

    def list_local_backups(self) -> list[Path]:
        backups_dir = get_backups_dir()
        if not backups_dir or not backups_dir.exists():
            return []
        return sorted(backups_dir.glob("*.zip"), reverse=True)

    def prune_old_backups(self, retention_days: int) -> int:
        backups_dir = get_backups_dir()
        if not backups_dir or not backups_dir.exists():
            return 0
        cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400
        removed = 0
        for path in backups_dir.glob("*.zip"):
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        return removed
