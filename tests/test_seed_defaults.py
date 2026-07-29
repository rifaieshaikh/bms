from vaybooks.bms.domain.shared.enums import ActivityCategory
from vaybooks.bms.infrastructure.db.location_seed import ensure_default_locations
from vaybooks.bms.infrastructure.db.seed import (
    DEFAULT_ACCOUNTS,
    DEFAULT_ACTIVITIES,
    DEFAULT_VENDOR_SERVICES,
    run_seed,
)


class _FakeCollection:
    def __init__(self):
        self.docs: list[dict] = []

    def find_one(self, query=None):
        query = query or {}
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    def insert_one(self, document):
        self.docs.append(dict(document))

    def count_documents(self, query=None):
        query = query or {}
        if not query:
            return len(self.docs)
        return sum(
            1
            for doc in self.docs
            if all(doc.get(k) == v for k, v in query.items())
        )


class _FakeDatabase:
    def __init__(self):
        self._collections: dict[str, _FakeCollection] = {}

    def __getattr__(self, name: str) -> _FakeCollection:
        return self[name]

    def __getitem__(self, name: str) -> _FakeCollection:
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]


def test_ensure_default_locations_creates_main_and_store():
    db = _FakeDatabase()
    main_id, store_id = ensure_default_locations(db)
    assert main_id
    assert store_id
    assert main_id != store_id
    main = db.warehouses.find_one({"code": "MAIN"})
    store = db.warehouses.find_one({"code": "STORE1"})
    assert main is not None
    assert store is not None
    assert main["_id"] == main_id
    assert store["_id"] == store_id
    # Idempotent
    main_id2, store_id2 = ensure_default_locations(db)
    assert (main_id2, store_id2) == (main_id, store_id)
    assert len(db.warehouses.docs) == 2


def test_run_seed_ensures_main_warehouse():
    db = _FakeDatabase()
    run_seed(db)
    main = db.warehouses.find_one({"code": "MAIN"})
    assert main is not None
    assert main["name"] == "Main Warehouse"
    store = db.warehouses.find_one({"code": "STORE1"})
    assert store is not None


def test_default_activities_cover_in_house_and_outsourced():
    names = {a["activity_name"] for a in DEFAULT_ACTIVITIES}
    assert names == {
        "Cutting",
        "Stitching",
        "Handwork",
        "Cutting and Stitching",
        "Material Purchase",
        "Dyeing",
        "Embroidery",
    }

    in_house = [
        a
        for a in DEFAULT_ACTIVITIES
        if a["activity_category"] == ActivityCategory.IN_HOUSE_SERVICE.value
    ]
    assert len(in_house) == 4
    assert all(a["requires_time_tracking"] for a in in_house)
    assert {a["activity_name"]: a["default_hourly_expense"] for a in in_house} == {
        "Cutting": 250,
        "Stitching": 250,
        "Handwork": 300,
        "Cutting and Stitching": 250,
    }

    outsourced = [
        a
        for a in DEFAULT_ACTIVITIES
        if a["activity_category"]
        in (
            ActivityCategory.OUTSOURCED_SERVICE.value,
            ActivityCategory.OUTSOURCED_MATERIAL.value,
        )
    ]
    assert {a["activity_name"] for a in outsourced} == {
        "Material Purchase",
        "Dyeing",
        "Embroidery",
    }
    assert all(not a["requires_time_tracking"] for a in outsourced)


def test_default_vendor_services_link_to_expense_accounts():
    account_names = {name for name, _, _ in DEFAULT_ACCOUNTS}
    service_names = {name for name, _ in DEFAULT_VENDOR_SERVICES}
    assert service_names == {
        "Material Purchase",
        "Dyeing",
        "Embroidery",
        "Cutting",
        "Stitching",
        "Cutting & Stitching",
        "Handwork",
    }
    for service_name, expense_account_name in DEFAULT_VENDOR_SERVICES:
        assert expense_account_name in account_names, (
            f"{service_name} -> {expense_account_name} missing from DEFAULT_ACCOUNTS"
        )


def test_default_accounts_include_activity_expense_buckets():
    expense_names = {
        name for name, account_type, _ in DEFAULT_ACCOUNTS if account_type.value == "Expense"
    }
    assert {
        "Cutting Expense",
        "Stitching Expense",
        "Handwork Expense",
        "Cutting and Stitching Expense",
        "Material Purchase Expense",
        "Dyeing Expense",
        "Embroidery Expense",
        "Salary Expense",
        "Discount Allowed",
        "Settlement Expense",
    }.issubset(expense_names)


def test_default_accounts_include_settlement_accounts():
    by_name = {name: account_type for name, account_type, _ in DEFAULT_ACCOUNTS}
    assert by_name["Settlement"].value == "Asset"
    assert by_name["Settlement Expense"].value == "Expense"
