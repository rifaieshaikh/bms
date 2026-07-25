"""Multi-field sort model tests."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import list_schemas as ls


def test_default_sort_is_list():
    sort = F.default_sort(ls.CUSTOMERS)
    assert isinstance(sort, list)
    assert len(sort) == 1
    assert sort[0]["key"] == ls.CUSTOMERS.default_sort
    assert sort[0]["desc"] is True


def test_normalize_sort_wraps_legacy_dict():
    legacy = {"key": "customer_name", "desc": False}
    out = F.normalize_sort(ls.CUSTOMERS, legacy)
    assert out == [{"key": "customer_name", "desc": False}]


def test_normalize_sort_drops_duplicates_and_unknown():
    raw = [
        {"key": "customer_name", "desc": False},
        {"key": "customer_name", "desc": True},
        {"key": "nope", "desc": True},
        {"key": "created_at", "desc": True},
        {"key": "order_count", "desc": False},
        {"key": "extra", "desc": True},
    ]
    out = F.normalize_sort(ls.CUSTOMERS, raw)
    assert [c["key"] for c in out] == ["customer_name", "created_at", "order_count"]
    assert len(out) <= F.MAX_SORT_LEVELS


def test_normalize_sort_truncates_to_max():
    keys = [s.key for s in ls.CUSTOMERS.sort_options]
    raw = [{"key": k, "desc": False} for k in keys]
    out = F.normalize_sort(ls.CUSTOMERS, raw)
    assert len(out) == min(F.MAX_SORT_LEVELS, len(keys))


def test_normalize_sort_empty_falls_back():
    out = F.normalize_sort(ls.CUSTOMERS, None)
    assert out == F.default_sort(ls.CUSTOMERS)


def test_multi_key_sort_records_order():
    recs = [
        SimpleNamespace(customer_name="B", created_at=datetime(2026, 1, 2), order_count=1),
        SimpleNamespace(customer_name="A", created_at=datetime(2026, 1, 3), order_count=2),
        SimpleNamespace(customer_name="A", created_at=datetime(2026, 1, 1), order_count=3),
    ]
    # Primary name asc, secondary created_at desc
    ordered = F.sort_records(
        recs,
        ls.CUSTOMERS,
        [
            {"key": "customer_name", "desc": False},
            {"key": "created_at", "desc": True},
        ],
    )
    assert [r.customer_name for r in ordered] == ["A", "A", "B"]
    assert ordered[0].created_at == datetime(2026, 1, 3)
    assert ordered[1].created_at == datetime(2026, 1, 1)


def test_filter_token_encodes_multi_sort():
    f = F.default_filters(ls.CUSTOMERS)
    sort = [
        {"key": "customer_name", "desc": False},
        {"key": "created_at", "desc": True},
    ]
    token = F.filter_token(ls.CUSTOMERS, f, sort)
    assert "__sort=customer_name:asc,created_at:desc" in token


def test_sort_records_accepts_legacy_dict():
    recs = [
        SimpleNamespace(name="Beta", score=2.0, created_at=datetime(2026, 1, 1), when=None),
        SimpleNamespace(name="Alpha", score=1.0, created_at=datetime(2026, 1, 1), when=None),
    ]
    schema = ls.ListSchema(
        entity_key="mini2",
        title="Mini2",
        filter_fields=[],
        sort_options=[
            ls.SortOption("name", "Name"),
            ls.SortOption("score", "Score"),
        ],
        default_sort="name",
        default_desc=False,
    )
    ordered = F.sort_records(recs, schema, {"key": "name", "desc": False})
    assert [r.name for r in ordered] == ["Alpha", "Beta"]
