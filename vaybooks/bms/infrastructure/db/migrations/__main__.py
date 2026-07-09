"""Run pending database migrations from CLI."""

from vaybooks.bms.infrastructure.db.connection import get_mongo_client_from_settings
from vaybooks.bms.infrastructure.db.migrations.runner import run_pending_migrations
from vaybooks.bms.infrastructure.config.settings import get_settings
from vaybooks.bms.infrastructure.logging.setup import setup_logging


def main() -> int:
    setup_logging()
    settings = get_settings()
    client = get_mongo_client_from_settings()
    db = client[settings.db_name]
    applied = run_pending_migrations(db)
    print(f"Applied migrations: {applied or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
