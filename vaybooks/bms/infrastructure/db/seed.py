from datetime import datetime
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from vaybooks.bms.domain.activities.entities import DEFAULT_ACTIVITY_STATUSES
from vaybooks.bms.domain.shared.enums import AccountType, ActivityCategory, ActivityType


DEFAULT_ACTIVITIES = [
    {
        "activity_name": "Cutting",
        "activity_type": ActivityType.IN_HOUSE.value,
        "activity_category": ActivityCategory.IN_HOUSE_SERVICE.value,
        "is_in_house": True,
        "requires_time_tracking": True,
        "default_hourly_expense": 250,
    },
    {
        "activity_name": "Stitching",
        "activity_type": ActivityType.IN_HOUSE.value,
        "activity_category": ActivityCategory.IN_HOUSE_SERVICE.value,
        "is_in_house": True,
        "requires_time_tracking": True,
        "default_hourly_expense": 250,
    },
    {
        "activity_name": "Handwork",
        "activity_type": ActivityType.IN_HOUSE.value,
        "activity_category": ActivityCategory.IN_HOUSE_SERVICE.value,
        "is_in_house": True,
        "requires_time_tracking": True,
        "default_hourly_expense": 300,
    },
    {
        "activity_name": "Cutting and Stitching",
        "activity_type": ActivityType.IN_HOUSE.value,
        "activity_category": ActivityCategory.IN_HOUSE_SERVICE.value,
        "is_in_house": True,
        "requires_time_tracking": True,
        "default_hourly_expense": 250,
    },
    {
        "activity_name": "Material Purchase",
        "activity_type": ActivityType.MATERIAL.value,
        "activity_category": ActivityCategory.OUTSOURCED_MATERIAL.value,
        "is_in_house": False,
        "requires_time_tracking": False,
        "default_hourly_expense": 0,
    },
    {
        "activity_name": "Dyeing",
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
]

# (account_name, account_type, is_store_account)
DEFAULT_ACCOUNTS = [
    ("Cash Drawer", AccountType.ASSET, True),
    ("Bank", AccountType.ASSET, True),
    ("Sales", AccountType.REVENUE, False),
    ("Customization", AccountType.REVENUE, False),
    ("Discount Allowed", AccountType.EXPENSE, False),
    ("Cutting Expense", AccountType.EXPENSE, False),
    ("Stitching Expense", AccountType.EXPENSE, False),
    ("Handwork Expense", AccountType.EXPENSE, False),
    ("Cutting and Stitching Expense", AccountType.EXPENSE, False),
    ("Material Purchase Expense", AccountType.EXPENSE, False),
    ("Dyeing Expense", AccountType.EXPENSE, False),
    ("Embroidery Expense", AccountType.EXPENSE, False),
    ("Salary Expense", AccountType.EXPENSE, False),
    ("Advance From Customers", AccountType.LIABILITY, False),
    ("CGST Input", AccountType.ASSET, False),
    ("SGST Input", AccountType.ASSET, False),
    ("IGST Input", AccountType.ASSET, False),
    ("UTGST Input", AccountType.ASSET, False),
    ("CGST Output", AccountType.LIABILITY, False),
    ("SGST Output", AccountType.LIABILITY, False),
    ("IGST Output", AccountType.LIABILITY, False),
    ("UTGST Output", AccountType.LIABILITY, False),
]

COUNTERS = [
    ("order_number", "CO"),
    ("voucher_number", "VCH"),
    ("invoice_number", "INV"),
    ("measurement_number", "MS"),
    ("po_number", "PO"),
    ("grn_number", "GRN"),
    ("purchase_return_number", "PR"),
    ("so_number", "SO"),
    ("dn_number", "DN"),
    ("sales_return_number", "SR"),
    ("estimate_number", "EST"),
    ("quotation_number", "QT"),
]

# (service_name, expense_account_name) — the expense account each vendor
# purchase/service posts to. Account names must exist in DEFAULT_ACCOUNTS.
DEFAULT_VENDOR_SERVICES = [
    ("Material Purchase", "Material Purchase Expense"),
    ("Dyeing", "Dyeing Expense"),
    ("Embroidery", "Embroidery Expense"),
    ("Cutting", "Cutting Expense"),
    ("Stitching", "Stitching Expense"),
    ("Cutting & Stitching", "Cutting and Stitching Expense"),
    ("Handwork", "Handwork Expense"),
]

DEFAULT_PRODUCT_CATEGORIES = [
    ("Fabric", "Fabrics and materials"),
    ("Ready-made", "Finished ready-to-sell items"),
    ("Accessories", "Accessories and add-ons"),
]

DEFAULT_PRODUCT_UNITS = [
    ("pcs", "Pieces"),
    ("m", "Metres"),
    ("kg", "Kilograms"),
    ("roll", "Roll"),
    ("set", "Set"),
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
    else:
        for activity in DEFAULT_ACTIVITIES:
            if db.activity_config.find_one({"activity_name": activity["activity_name"]}):
                continue
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

    for category_name, description in DEFAULT_PRODUCT_CATEGORIES:
        if db.product_categories.find_one({"name": category_name}):
            continue
        _insert_ignoring_duplicates(
            db.product_categories,
            {
                "_id": uuid4().hex,
                "name": category_name,
                "description": description,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        )

    for code, label in DEFAULT_PRODUCT_UNITS:
        if db.product_units.find_one({"code": code}):
            continue
        _insert_ignoring_duplicates(
            db.product_units,
            {
                "_id": uuid4().hex,
                "code": code,
                "label": label,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        )

    from vaybooks.bms.infrastructure.db.measurement_seed import ensure_measurement_specs

    ensure_measurement_specs(db)


def _insert_ignoring_duplicates(collection, document):
    """Insert a seed document, tolerating a concurrent session that beat us to it."""
    try:
        collection.insert_one(document)
    except DuplicateKeyError:
        pass


from vaybooks.bms.interface.api.health_routes import install_harness_health_route_when_ready

install_harness_health_route_when_ready()


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
