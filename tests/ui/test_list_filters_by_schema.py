"""Filter and sort coverage for every list schema."""

import pytest

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.list_schemas import SCHEMAS
from tests.ui.list_filter_fixtures import (
    FILTER_NEGATIVE,
    FILTER_POSITIVE,
    FIXTURES,
    SORT_CASES,
)


@pytest.mark.parametrize("entity_key", list(SCHEMAS.keys()))
def test_empty_filters_return_all(entity_key):
    schema = SCHEMAS[entity_key]
    recs = FIXTURES[entity_key]
    result = F.apply_filters(recs, schema, F.default_filters(schema))
    assert len(result) == len(recs)


@pytest.mark.parametrize("entity_key,field_key,value,expected", FILTER_POSITIVE)
def test_filter_positive(entity_key, field_key, value, expected):
    schema = SCHEMAS[entity_key]
    recs = FIXTURES[entity_key]
    filters = F.default_filters(schema)
    filters[field_key] = value
    result = F.apply_filters(recs, schema, filters)
    assert len(result) == expected


@pytest.mark.parametrize("entity_key,field_key,value,expected", FILTER_NEGATIVE)
def test_filter_negative_no_match(entity_key, field_key, value, expected):
    schema = SCHEMAS[entity_key]
    recs = FIXTURES[entity_key]
    filters = F.default_filters(schema)
    filters[field_key] = value
    result = F.apply_filters(recs, schema, filters)
    assert len(result) == expected


@pytest.mark.parametrize("entity_key,sort_key,desc,first_label", SORT_CASES)
def test_sort_order(entity_key, sort_key, desc, first_label):
    schema = SCHEMAS[entity_key]
    recs = FIXTURES[entity_key]
    ordered = F.sort_records(recs, schema, {"key": sort_key, "desc": desc})
    option = schema.sort_option(sort_key)
    attr = option.attr

    def _value(record):
        if isinstance(record, dict):
            return record.get(attr)
        return getattr(record, attr, None)

    assert str(_value(ordered[0])) == first_label


@pytest.mark.parametrize("entity_key", list(SCHEMAS.keys()))
def test_and_semantics_excludes_partial_cross_field(entity_key):
    schema = SCHEMAS[entity_key]
    recs = FIXTURES[entity_key]
    if len(recs) < 2:
        pytest.skip("need at least two records")
    exact_fields = [f for f in schema.filter_fields if f.type == F.EXACT]
    if len(exact_fields) < 2:
        pytest.skip("need two exact fields")
    f1, f2 = exact_fields[0], exact_fields[1]
    v1 = getattr(recs[0], f1.attr, None) if not isinstance(recs[0], dict) else recs[0].get(f1.attr)
    v2 = getattr(recs[1], f2.attr, None) if not isinstance(recs[1], dict) else recs[1].get(f2.attr)
    if v1 is None or v2 is None:
        pytest.skip("fixture values unavailable")
    filters = F.default_filters(schema)
    filters[f1.key] = v1
    filters[f2.key] = v2
    result = F.apply_filters(recs, schema, filters)
    assert result == []
