"""Insert Settlement and Settlement Expense accounts for two-step customer clearing.

These accounts are normally created by the optional startup seed
(SEED_CONFIG). Databases created before they were added to
DEFAULT_ACCOUNTS never received them, which makes customer Settle fail
with "No Settlement account found".
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from vaybooks.bms.domain.shared.enums import AccountType

SETTLEMENT_ACCOUNTS = [
    ("Settlement", AccountType.ASSET),
    ("Settlement Expense", AccountType.EXPENSE),
]


def up(db: Database) -> None:
    now = datetime.utcnow()
    for account_name, account_type in SETTLEMENT_ACCOUNTS:
        if db.accounts.find_one({"account_name": account_name}):
            continue
        try:
            db.accounts.insert_one(
                {
                    "_id": uuid4().hex,
                    "account_name": account_name,
                    "account_type": account_type.value,
                    "linked_customer_id": None,
                    "opening_balance": 0,
                    "current_balance": 0,
                    "is_store_account": False,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        except DuplicateKeyError:
            pass
