"""Tests for purchase price history."""

from datetime import date

from vaybooks.bms.domain.purchases.line_items import PurchaseBillLine, PurchasePriceHistory
from vaybooks.bms.domain.shared.enums import CatalogItemType
from vaybooks.bms.infrastructure.repositories.purchases.mongo_purchase_price_history_repository import (
    MongoPurchasePriceHistoryRepository,
)


class FakeDb:
    def __init__(self):
        self.purchase_price_history = FakeCollection()


class FakeCollection:
    def __init__(self):
        self._docs = {}

    def replace_one(self, query, doc, upsert=False):
        self._docs[doc["_id"]] = doc

    def find(self, query):
        results = []
        for doc in self._docs.values():
            match = all(doc.get(k) == v for k, v in query.items())
            if match:
                results.append(doc)
        return _FakeCursor(results)


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, field, direction=-1):
        if isinstance(field, list):
            for key, direction in reversed(field):
                self._docs.sort(
                    key=lambda d, k=key: d.get(k) or "",
                    reverse=(direction == -1),
                )
            return self
        self._docs.sort(key=lambda d: d.get(field, ""), reverse=(direction == -1))
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


def test_price_history_latest_rate():
    repo = MongoPurchasePriceHistoryRepository(FakeDb())
    repo.save(
        PurchasePriceHistory(
            item_type=CatalogItemType.PRODUCT,
            item_id="p1",
            vendor_id="v1",
            purchase_date=date(2026, 1, 1),
            qty=1,
            rate=100,
            taxable_amount=100,
            line_total=100,
        )
    )
    repo.save(
        PurchasePriceHistory(
            item_type=CatalogItemType.PRODUCT,
            item_id="p1",
            vendor_id="v1",
            purchase_date=date(2026, 6, 1),
            qty=1,
            rate=120,
            taxable_amount=120,
            line_total=120,
        )
    )
    assert repo.latest_rate(CatalogItemType.PRODUCT, "p1", "v1") == 120.0
    # Prior rate remains in history; latest is active for that vendor.
    history = repo.list_for_item(CatalogItemType.PRODUCT, "p1", vendor_id="v1")
    assert [h.rate for h in history] == [120.0, 100.0]
