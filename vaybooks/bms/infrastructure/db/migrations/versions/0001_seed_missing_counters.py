"""Insert any document-number counters missing from the counters collection.

Counters were previously only created by the optional startup seed
(SEED_CONFIG). Databases created before newer counters (e.g. so_number)
were added never received them, which made document creation fail with
"Counter <name> not found".
"""

from __future__ import annotations

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError


def up(db: Database) -> None:
    from vaybooks.bms.infrastructure.db.seed import COUNTERS

    for counter_id, prefix in COUNTERS:
        if db.counters.find_one({"_id": counter_id}):
            continue
        try:
            db.counters.insert_one(
                {"_id": counter_id, "prefix": prefix, "current_value": 0}
            )
        except DuplicateKeyError:
            pass
