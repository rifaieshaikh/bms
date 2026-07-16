"""Insert GST Input/Output ledger accounts missing from the accounts collection.

These accounts are normally created by the optional startup seed
(SEED_CONFIG). Databases created before GST accounts were added to
DEFAULT_ACCOUNTS never received them, which made GST invoices fail with
"Voucher is not balanced" because the tax credit lines were skipped.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from vaybooks.bms.domain.shared.enums import AccountType

GST_ACCOUNTS = [
    ("CGST Input", AccountType.ASSET),
    ("SGST Input", AccountType.ASSET),
    ("IGST Input", AccountType.ASSET),
    ("UTGST Input", AccountType.ASSET),
    ("CGST Output", AccountType.LIABILITY),
    ("SGST Output", AccountType.LIABILITY),
    ("IGST Output", AccountType.LIABILITY),
    ("UTGST Output", AccountType.LIABILITY),
]


def up(db: Database) -> None:
    now = datetime.utcnow()
    for account_name, account_type in GST_ACCOUNTS:
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
