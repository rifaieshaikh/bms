"""Full backup, restore, retention, and scheduled backup support."""

from __future__ import annotations

import json
import logging
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from bson import ObjectId
from pymongo.database import Database

from vaybooks.bms.application.finance.export.service import _serialize_bson
from vaybooks.bms.infrastructure.config.paths import get_backups_dir, get_config_path
from vaybooks.bms.infrastructure.config.runtime import is_desktop
from vaybooks.bms.infrastructure.config.settings import get_settings
from vaybooks.bms.version import __version__

logger = logging.getLogger("vaybooks.bms.backup")

BackupMode = Literal["complete", "balances"]
RetentionMode = Literal["keep_one", "keep_all"]

# Scheduled/manual backups eligible for keep_one prune. Pre-upgrade and
# pre-FY-close archives are preserved.
MANAGED_BACKUP_PREFIXES = ("backup_", "balances_")
PROTECTED_BACKUP_PREFIXES = ("pre_upgrade_", "pre_fy_close_")


def is_managed_backup_name(name: str) -> bool:
    stem = Path(name).name.lower()
    if any(stem.startswith(p) for p in PROTECTED_BACKUP_PREFIXES):
        return False
    return any(stem.startswith(p) for p in MANAGED_BACKUP_PREFIXES)


# Legacy allowlist kept for older ZIP restores that only exported these names.
LEGACY_COLLECTIONS = [
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

# Back-compat alias used by older callers / CLI docs.
ALL_COLLECTIONS = LEGACY_COLLECTIONS

BALANCES_COLLECTIONS = [
    "customers",
    "vendors",
    "commission_agents",
    "delivery_partners",
    "workers",
    "party_segments",
    "accounts",
]

SYSTEM_COLLECTION_PREFIXES = ("system.",)


def _is_system_collection(name: str) -> bool:
    lower = (name or "").strip().lower()
    return not lower or any(lower.startswith(p) for p in SYSTEM_COLLECTION_PREFIXES)


def normalize_backup_mode(mode: str | None) -> BackupMode:
    value = (mode or "complete").strip().lower()
    return "balances" if value == "balances" else "complete"


def normalize_retention(mode: str | None) -> RetentionMode:
    value = (mode or "keep_one").strip().lower()
    return "keep_all" if value == "keep_all" else "keep_one"


class BackupService:
    def __init__(self, db: Database):
        self._db = db

    def list_exportable_collections(self, mode: BackupMode = "complete") -> list[str]:
        mode = normalize_backup_mode(mode)
        existing = set(self._db.list_collection_names())
        if mode == "balances":
            return [name for name in BALANCES_COLLECTIONS if name in existing]
        return sorted(name for name in existing if not _is_system_collection(name))

    def export_collections(
        self, mode: BackupMode = "complete"
    ) -> dict[str, list[dict[str, Any]]]:
        backup: dict[str, list[dict[str, Any]]] = {}
        for name in self.list_exportable_collections(mode):
            backup[name] = list(self._db[name].find())
        return backup

    def export_all_collections(self) -> dict[str, list[dict[str, Any]]]:
        """Back-compat: complete dump of all user collections."""
        return self.export_collections("complete")

    def build_outstanding_summary(self) -> dict[str, Any]:
        """Lightweight AR/AP snapshot for balances backups (audit only)."""
        customers: list[dict[str, Any]] = []
        vendors: list[dict[str, Any]] = []
        if "accounts" not in self._db.list_collection_names():
            return {"customers": customers, "vendors": vendors}
        for doc in self._db["accounts"].find({}):
            balance = round(float(doc.get("current_balance") or 0), 2)
            customer_id = (doc.get("linked_customer_id") or "").strip()
            vendor_id = (doc.get("linked_vendor_id") or "").strip()
            if customer_id and balance > 0.01:
                customers.append(
                    {
                        "account_id": str(doc.get("_id")),
                        "customer_id": customer_id,
                        "account_name": doc.get("account_name") or "",
                        "receivable": balance,
                    }
                )
            if vendor_id and balance < -0.01:
                vendors.append(
                    {
                        "account_id": str(doc.get("_id")),
                        "vendor_id": vendor_id,
                        "account_name": doc.get("account_name") or "",
                        "payable": round(abs(balance), 2),
                    }
                )
        return {"customers": customers, "vendors": vendors}

    def create_backup_zip(self, mode: BackupMode = "complete") -> bytes:
        mode = normalize_backup_mode(mode)
        payload: dict[str, Any] = {
            "version": __version__,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": get_settings().db_name,
            "backup_mode": mode,
            "collections": _serialize_bson(self.export_collections(mode)),
        }
        if mode == "balances":
            payload["outstanding_summary"] = self.build_outstanding_summary()
        config_path = get_config_path()
        if config_path and config_path.exists():
            payload["config_snapshot"] = config_path.read_text(encoding="utf-8")

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("backup.json", json.dumps(payload, indent=2, default=str))
        return buffer.getvalue()

    def save_backup_to_disk(
        self,
        label: str | None = None,
        *,
        mode: BackupMode | None = None,
        apply_retention_after: bool = True,
    ) -> Path | None:
        if not is_desktop():
            return None
        backups_dir = get_backups_dir()
        if not backups_dir:
            return None
        settings = get_settings()
        mode = normalize_backup_mode(mode or getattr(settings, "backup_mode", "complete"))
        backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = "balances" if mode == "balances" else "backup"
        name = label or f"{prefix}_{stamp}"
        path = backups_dir / f"{name}.zip"
        path.write_bytes(self.create_backup_zip(mode))
        logger.info("Backup (%s) saved to %s", mode, path)
        if apply_retention_after:
            retention = normalize_retention(
                getattr(settings, "backup_retention", None)
                or self._legacy_retention_from_days(
                    getattr(settings, "backup_retention_days", 30)
                )
            )
            self.apply_retention(retention, keep_path=path)
        return path

    @staticmethod
    def _legacy_retention_from_days(days: int) -> RetentionMode:
        try:
            return "keep_one" if int(days) <= 1 else "keep_all"
        except (TypeError, ValueError):
            return "keep_one"

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

        mode = normalize_backup_mode(payload.get("backup_mode") or "complete")
        if mode == "balances" and not dry_run:
            raise ValueError(
                "Balances-only backups cannot fully restore the database. "
                "Use a complete backup ZIP, or restore accounts/parties manually."
            )

        collections = payload.get("collections", {})
        stats: dict[str, int] = {}
        if dry_run:
            for name, docs in collections.items():
                stats[name] = len(docs) if isinstance(docs, list) else 0
            stats["_backup_mode"] = mode  # type: ignore[assignment]
            return stats

        for name, docs in collections.items():
            if _is_system_collection(name) or not isinstance(docs, list):
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
        return sorted(
            backups_dir.glob("*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def list_managed_backups(self) -> list[Path]:
        """Scheduled/manual backup ZIPs only (excludes pre_upgrade / pre_fy_close)."""
        return [p for p in self.list_local_backups() if is_managed_backup_name(p.name)]

    def apply_retention(
        self,
        mode: RetentionMode = "keep_one",
        *,
        keep_path: Path | None = None,
    ) -> int:
        """Apply keep_one (delete older managed backups) or keep_all (no-op).

        Never deletes ``pre_upgrade_*`` or ``pre_fy_close_*`` archives.
        """
        mode = normalize_retention(mode)
        if mode == "keep_all":
            return 0
        backups = self.list_managed_backups()
        if not backups:
            return 0
        if keep_path and is_managed_backup_name(keep_path.name):
            newest = keep_path.resolve()
        else:
            newest = backups[0].resolve()
        removed = 0
        for path in backups:
            if path.resolve() == newest:
                continue
            path.unlink(missing_ok=True)
            removed += 1
        if removed:
            logger.info(
                "Retention keep_one removed %s older managed backup(s)", removed
            )
        return removed

    def prune_old_backups(self, retention_days: int) -> int:
        """Legacy day-based prune (secondary to keep_one/keep_all)."""
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

    def run_scheduled_backup(self) -> dict[str, Any]:
        """Create backup per settings; upload to Drive when enabled (desktop)."""
        if not is_desktop():
            return {"ok": False, "skipped": True, "reason": "not_desktop"}
        settings = get_settings()
        schedule = (settings.backup_schedule or "off").strip().lower()
        if schedule == "off":
            return {"ok": False, "skipped": True, "reason": "schedule_off"}

        mode = normalize_backup_mode(getattr(settings, "backup_mode", "complete"))
        path = self.save_backup_to_disk(mode=mode, apply_retention_after=True)
        if not path:
            return {"ok": False, "error": "save_failed"}

        result: dict[str, Any] = {
            "ok": True,
            "path": str(path),
            "mode": mode,
            "drive_uploaded": False,
        }
        if getattr(settings, "backup_google_drive_enabled", False):
            try:
                from vaybooks.bms.infrastructure.backup.google_drive import (
                    upload_backup_and_prune,
                )

                drive_id = upload_backup_and_prune(
                    path,
                    retention=normalize_retention(
                        getattr(settings, "backup_retention", "keep_one")
                    ),
                )
                result["drive_uploaded"] = True
                result["drive_file_id"] = drive_id
            except Exception as exc:
                logger.exception("Google Drive upload failed")
                result["drive_error"] = str(exc)
        return result
