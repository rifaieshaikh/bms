"""Tests for business-data purge helper."""

from __future__ import annotations

from vaybooks.bms.infrastructure.db.purge import BUSINESS_COLLECTIONS, purge_business_data
from vaybooks.bms.infrastructure.db.seed import DEFAULT_ACCOUNTS


class _DeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None):
        self.docs = list(docs or [])

    def delete_many(self, query):
        remaining = []
        deleted = 0
        for doc in self.docs:
            if _matches(doc, query):
                deleted += 1
            else:
                remaining.append(doc)
        self.docs = remaining
        return _DeleteResult(deleted)

    def find(self, query):
        matched = []
        for doc in self.docs:
            if _matches(doc, query):
                matched.append(dict(doc))
        return matched

    def find_one(self, query):
        for doc in self.docs:
            if _matches(doc, query):
                return dict(doc)
        return None

    def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                return

    def update_many(self, query, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])


class FakeDatabase:
    def __init__(self, collections: dict[str, FakeCollection]):
        self._collections = collections

    def list_collection_names(self):
        return list(self._collections.keys())

    def __getitem__(self, name: str) -> FakeCollection:
        return self._collections[name]

    def __getattr__(self, name: str) -> FakeCollection:
        if name in self._collections:
            return self._collections[name]
        raise AttributeError(name)


def _matches(doc: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(doc, clause) for clause in expected):
                return False
            continue
        value = doc.get(key)
        if isinstance(expected, dict):
            if "$type" in expected:
                type_name = expected["$type"]
                if type_name == "string" and not isinstance(value, str):
                    return False
                if type_name == "string" and value is None:
                    return False
            if "$in" in expected and value not in expected["$in"]:
                return False
            if "$nin" in expected and value in expected["$nin"]:
                return False
        elif value != expected:
            return False
    return True


def test_purge_removes_business_collections_and_linked_accounts():
    default_accounts = [
        {
            "_id": "cash",
            "account_name": "Cash Drawer",
            "opening_balance": 100,
            "current_balance": 500,
            "linked_customer_id": None,
            "linked_vendor_id": None,
        },
        {
            "_id": "cust-acct",
            "account_name": "Ananya Rao",
            "opening_balance": 0,
            "current_balance": 0,
            "linked_customer_id": "cust-1",
            "linked_vendor_id": None,
        },
    ]
    db = FakeDatabase(
        {
            "customization_orders": FakeCollection([{"_id": "O-1001"}]),
            "customers": FakeCollection([{"_id": "cust-1"}]),
            "accounts": FakeCollection(default_accounts),
            "counters": FakeCollection(
                [{"_id": "order_number", "prefix": "CO", "current_value": 12}]
            ),
            "activity_config": FakeCollection([{"_id": "act-1", "activity_name": "Cutting"}]),
        }
    )

    removed = purge_business_data(db)

    assert removed["customization_orders"] == 1
    assert removed["customers"] == 1
    assert removed["linked_accounts"] == 1
    assert db.customization_orders.docs == []
    assert db.customers.docs == []
    assert db.activity_config.docs != []
    assert db.accounts.find_one({"_id": "cash"})["current_balance"] == 100
    assert db.counters.find_one({"_id": "order_number"})["current_value"] == 0


def test_default_account_names_cover_core_seed():
    names = {name for name, _, _ in DEFAULT_ACCOUNTS}
    assert "Cash Drawer" in names
    assert len(names) == len(DEFAULT_ACCOUNTS)
