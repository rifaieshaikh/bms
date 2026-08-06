"""Backup CLI for scheduled tasks."""

from __future__ import annotations

import argparse
import sys

from vaybooks.bms.infrastructure.backup.service import (
    BackupService,
    normalize_backup_mode,
    normalize_retention,
)
from vaybooks.bms.infrastructure.config.settings import get_settings
from vaybooks.bms.infrastructure.db.connection import get_mongo_client_from_settings
from vaybooks.bms.infrastructure.logging.setup import setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VayBooks-BMS backup utility")
    parser.add_argument(
        "command",
        choices=["backup", "prune", "run"],
        help="backup: create zip; prune: apply retention; run: scheduled backup+drive",
    )
    parser.add_argument("--label", default=None, help="Optional backup label")
    parser.add_argument(
        "--mode",
        choices=["complete", "balances"],
        default=None,
        help="Backup mode (default: settings BACKUP_MODE)",
    )
    args = parser.parse_args(argv)

    setup_logging()
    settings = get_settings()
    client = get_mongo_client_from_settings()
    db = client[settings.db_name]
    service = BackupService(db)

    if args.command == "backup":
        mode = normalize_backup_mode(args.mode or settings.backup_mode)
        path = service.save_backup_to_disk(args.label, mode=mode)
        if path:
            print(f"Backup created ({mode}): {path}")
            return 0
        print("Backup failed: desktop data directory not available", file=sys.stderr)
        return 1

    if args.command == "prune":
        retention = normalize_retention(settings.backup_retention)
        removed = service.apply_retention(retention)
        print(f"Retention {retention}: removed {removed} older backup(s)")
        return 0

    if args.command == "run":
        result = service.run_scheduled_backup()
        print(result)
        return 0 if result.get("ok") or result.get("skipped") else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
