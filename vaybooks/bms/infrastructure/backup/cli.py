"""Backup CLI for scheduled tasks."""

from __future__ import annotations

import argparse
import sys

from vaybooks.bms.infrastructure.backup.service import BackupService
from vaybooks.bms.infrastructure.config.settings import get_settings
from vaybooks.bms.infrastructure.db.connection import get_mongo_client_from_settings
from vaybooks.bms.infrastructure.logging.setup import setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VayBooks-BMS backup utility")
    parser.add_argument(
        "command",
        choices=["backup", "prune"],
        help="backup: create zip; prune: remove old backups",
    )
    parser.add_argument("--label", default=None, help="Optional backup label")
    args = parser.parse_args(argv)

    setup_logging()
    settings = get_settings()
    client = get_mongo_client_from_settings()
    db = client[settings.db_name]
    service = BackupService(db)

    if args.command == "backup":
        path = service.save_backup_to_disk(args.label)
        if path:
            print(f"Backup created: {path}")
            return 0
        print("Backup failed: desktop data directory not available", file=sys.stderr)
        return 1

    if args.command == "prune":
        removed = service.prune_old_backups(settings.backup_retention_days)
        print(f"Removed {removed} old backup(s)")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
