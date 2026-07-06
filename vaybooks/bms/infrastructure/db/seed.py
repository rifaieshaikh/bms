from datetime import datetime
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from vaybooks.bms.domain.activities.entities import DEFAULT_ACTIVITY_STATUSES
from vaybooks.bms.domain.shared.enums import AccountType, ActivityCategory, ActivityType


DEFAULT_ACTIVITIES = [
    {
        "activity_name": "Stitching",
        "activity_type": ActivityType.IN_HOUSE.value,
        "activity_category": ActivityCategory.IN_HOUSE_SERVICE.value,
        "is_in_house": True,
        "requires_time_tracking": True,
        "default_hourly_expense": 500,
    },
    {
        "activity_name": "Hand Work",
        "activity_type": ActivityType.IN_HOUSE.value,
        "activity_category": ActivityCategory.IN_HOUSE_SERVICE.value,
        "is_in_house": True,
        "requires_time_tracking": True,
        "default_hourly_expense": 500,
    },
    {
        "activity_name": "Dying",
        "activity_type": ActivityType.OUTSOURCED.value,
        "activity_category": ActivityCategory.OUTSOURCED_SERVICE.value,
        "is_in_house": False,
        "requires_time_tracking": False,
        "default_hourly_expense": 0,
    },
    {
        "activity_name": "Embroidery",
        "activity_type": ActivityType.OUTSOURCED.value,
        "activity_category": ActivityCategory.OUTSOURCED_SERVICE.value,
        "is_in_house": False,
        "requires_time_tracking": False,
        "default_hourly_expense": 0,
    },
    {
        "activity_name": "Material Purchase",
        "activity_type": ActivityType.MATERIAL.value,
        "activity_category": ActivityCategory.OUTSOURCED_MATERIAL.value,
        "is_in_house": False,
        "requires_time_tracking": False,
        "default_hourly_expense": 0,
    },
]

# (account_name, account_type, is_store_account)
DEFAULT_ACCOUNTS = [
    ("Cash", AccountType.ASSET, True),
    ("Bank", AccountType.ASSET, True),
    ("Sales", AccountType.REVENUE, False),
    ("Customization", AccountType.REVENUE, False),
    ("Discount Allowed", AccountType.EXPENSE, False),
    ("Stitching Expense", AccountType.EXPENSE, False),
    ("Hand Work Expense", AccountType.EXPENSE, False),
    ("Material Purchase Expense", AccountType.EXPENSE, False),
    ("Outsourced Work Expense", AccountType.EXPENSE, False),
    ("Salary Expense", AccountType.EXPENSE, False),
    ("Advance From Customers", AccountType.LIABILITY, False),
]

COUNTERS = [
    ("order_number", "CO"),
    ("voucher_number", "VCH"),
    ("invoice_number", "INV"),
]

# (service_name, expense_account_name) — the expense account each vendor
# purchase/service posts to. Account names must exist in DEFAULT_ACCOUNTS.
DEFAULT_VENDOR_SERVICES = [
    ("Material Purchase", "Material Purchase Expense"),
    ("Stitching", "Stitching Expense"),
    ("Hand Work", "Hand Work Expense"),
    ("Outsourced Work", "Outsourced Work Expense"),
]


def run_seed(db):
    now = datetime.utcnow()

    # Seed default activities only on a fresh database. Re-seeding by name would
    # resurrect defaults that the user has renamed or deleted. Inserts are wrapped
    # in a duplicate-key guard because concurrent Streamlit sessions can race to
    # seed the same fresh database at startup.
    if db.activity_config.count_documents({}) == 0:
        for activity in DEFAULT_ACTIVITIES:
            _insert_ignoring_duplicates(
                db.activity_config,
                {
                    "_id": uuid4().hex,
                    **activity,
                    "statuses": list(DEFAULT_ACTIVITY_STATUSES),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                },
            )

    for account_name, account_type, is_store_account in DEFAULT_ACCOUNTS:
        existing = db.accounts.find_one({"account_name": account_name})
        if not existing:
            _insert_ignoring_duplicates(
                db.accounts,
                {
                    "_id": uuid4().hex,
                    "account_name": account_name,
                    "account_type": account_type.value,
                    "linked_customer_id": None,
                    "opening_balance": 0,
                    "current_balance": 0,
                    "is_store_account": is_store_account,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                },
            )

    # Seed default vendor services, linking each to its expense account by name.
    for service_name, expense_account_name in DEFAULT_VENDOR_SERVICES:
        if db.vendor_services.find_one({"service_name": service_name}):
            continue
        expense_account = db.accounts.find_one({"account_name": expense_account_name})
        if not expense_account:
            continue
        _insert_ignoring_duplicates(
            db.vendor_services,
            {
                "_id": uuid4().hex,
                "service_name": service_name,
                "expense_account_id": expense_account["_id"],
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        )

    for counter_id, prefix in COUNTERS:
        existing = db.counters.find_one({"_id": counter_id})
        if not existing:
            _insert_ignoring_duplicates(
                db.counters,
                {
                    "_id": counter_id,
                    "prefix": prefix,
                    "current_value": 0,
                },
            )


def _insert_ignoring_duplicates(collection, document):
    """Insert a seed document, tolerating a concurrent session that beat us to it."""
    try:
        collection.insert_one(document)
    except DuplicateKeyError:
        pass


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DATABASE", "zahcci_customization")
    if not uri:
        print("Set MONGODB_URI environment variable or use Streamlit secrets")
    else:
        from vaybooks.bms.infrastructure.db.connection import get_database_from_uri

        database = get_database_from_uri(uri, db_name)
        run_seed(database)
        print("Seed data created successfully")
