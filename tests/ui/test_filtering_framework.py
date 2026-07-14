"""Edge-case tests for the list filtering/sorting framework."""

from datetime import date, datetime
from types import SimpleNamespace

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import list_schemas as ls


def _rows():
    return [
        SimpleNamespace(name="Alpha", score=10.0, created_at=datetime(2026, 1, 1), when=date(2026, 1, 1)),
        SimpleNamespace(name="Beta", score=20.0, created_at=datetime(2026, 2, 1), when=date(2026, 2, 1)),
        SimpleNamespace(name="Gamma", score=None, created_at=datetime(2026, 3, 1), when=date(2026, 3, 1)),
    ]


MINI_SCHEMA = ls.ListSchema(
    entity_key="mini",
    title="Mini",
    filter_fields=[
        ls.FilterField("name", "Name", F.EXACT),
        ls.FilterField("score", "Min score", F.NUMBER_MIN, record_attr="score"),
        ls.FilterField("when", "When", F.DATE_RANGE),
        ls.FilterField("active", "Active", F.CHECKBOX),
    ],
    sort_options=[
        ls.SortOption("name", "Name"),
        ls.SortOption("score", "Score"),
        ls.SortOption("created_at", "Created"),
    ],
    default_sort="created_at",
)


def test_is_active_value_rejects_empty_exact():
    fld = MINI_SCHEMA.field("name")
    assert not F.is_active_value(fld, "")
    assert not F.is_active_value(fld, None)


def test_is_active_value_rejects_zero_number_min():
    fld = MINI_SCHEMA.field("score")
    assert not F.is_active_value(fld, 0)
    assert not F.is_active_value(fld, "0")


def test_is_active_value_select_all_is_inactive():
    fld = ls.FilterField("kind", "Kind", F.SELECT)
    assert not F.is_active_value(fld, F.ALL_LABEL)


def test_number_min_is_inclusive():
    recs = _rows()[:2]
    f = F.default_filters(MINI_SCHEMA)
    f["score"] = 20.0
    result = F.apply_filters(recs, MINI_SCHEMA, f)
    assert [r.name for r in result] == ["Beta"]


def test_date_range_excludes_outside():
    recs = _rows()[:2]
    f = F.default_filters(MINI_SCHEMA)
    f["when"] = (date(2026, 1, 15), date(2026, 2, 15))
    result = F.apply_filters(recs, MINI_SCHEMA, f)
    assert [r.name for r in result] == ["Beta"]


def test_sort_nulls_last_ascending():
    recs = _rows()
    ordered = F.sort_records(recs, MINI_SCHEMA, {"key": "score", "desc": False})
    assert ordered[-1].name == "Gamma"


def test_trial_balance_default_sort_ascending():
    recs = [
        {"account_name": "Zeta", "balance": 1},
        {"account_name": "Alpha", "balance": 2},
    ]
    ordered = F.sort_records(recs, ls.TRIAL_BALANCE, F.default_sort(ls.TRIAL_BALANCE))
    assert [r["account_name"] for r in ordered] == ["Alpha", "Zeta"]


def test_filter_token_includes_sort():
    f = F.default_filters(ls.CUSTOMERS)
    sort = {"key": "customer_name", "desc": False}
    token = F.filter_token(ls.CUSTOMERS, f, sort)
    assert "__sort=customer_name:asc" in token


def test_checkbox_filter_only_when_true():
    recs = [
        SimpleNamespace(name="A", active=True, created_at=datetime(2026, 1, 1)),
        SimpleNamespace(name="B", active=False, created_at=datetime(2026, 1, 1)),
    ]
    schema = ls.ListSchema(
        entity_key="cb",
        title="CB",
        filter_fields=[ls.FilterField("active", "Active", F.CHECKBOX)],
        sort_options=[ls.SortOption("name", "Name")],
        default_sort="name",
    )
    f = F.default_filters(schema)
    f["active"] = True
    result = F.apply_filters(recs, schema, f)
    assert len(result) == 1


def test_regex_is_case_insensitive_and_partial():
    schema = ls.ListSchema(
        entity_key="rx",
        title="RX",
        filter_fields=[ls.FilterField("name", "Name", F.REGEX)],
        sort_options=[ls.SortOption("name", "Name")],
        default_sort="name",
    )
    recs = [
        SimpleNamespace(name="Alpha Customer"),
        SimpleNamespace(name="Beta Customer"),
    ]
    f = F.default_filters(schema)
    f["name"] = "alpha"
    assert [r.name for r in F.apply_filters(recs, schema, f)] == ["Alpha Customer"]

    f["name"] = r"Customer$"
    assert len(F.apply_filters(recs, schema, f)) == 2


def test_invalid_regex_matches_nothing():
    schema = ls.ListSchema(
        entity_key="rx",
        title="RX",
        filter_fields=[ls.FilterField("name", "Name", F.REGEX)],
        sort_options=[ls.SortOption("name", "Name")],
        default_sort="name",
    )
    recs = [SimpleNamespace(name="Alpha")]
    f = F.default_filters(schema)
    f["name"] = "["
    assert F.apply_filters(recs, schema, f) == []
