"""Insert Cancellation Charges revenue account for cancelled-order invoices."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from vaybooks.bms.domain.shared.enums import AccountType

ACCOUNT_NAME = "Cancellation Charges"


def up(db: Database) -> None:
    if db.accounts.find_one({"account_name": ACCOUNT_NAME}):
        return
    now = datetime.utcnow()
    try:
        db.accounts.insert_one(
            {
                "_id": uuid4().hex,
                "account_name": ACCOUNT_NAME,
                "account_type": AccountType.REVENUE.value,
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
