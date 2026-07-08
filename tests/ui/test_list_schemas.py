"""Schema invariants: no free-text search fields; sane defaults."""

from vaybooks.bms.ui.list_schemas import SCHEMAS


def test_no_search_or_q_fields_anywhere():
    banned = {"q", "search", "query"}
    for entity_key, schema in SCHEMAS.items():
        keys = {f.key for f in schema.filter_fields}
        assert not (keys & banned), f"{entity_key} exposes a free-text search field"


def test_every_schema_has_default_sort_in_options():
    for entity_key, schema in SCHEMAS.items():
        sort_keys = {s.key for s in schema.sort_options}
        assert schema.default_sort in sort_keys, entity_key


def test_entity_keys_match_dict_keys():
    for entity_key, schema in SCHEMAS.items():
        assert schema.entity_key == entity_key


def test_filter_field_keys_unique_per_schema():
    for entity_key, schema in SCHEMAS.items():
        keys = [f.key for f in schema.filter_fields]
        assert len(keys) == len(set(keys)), entity_key
