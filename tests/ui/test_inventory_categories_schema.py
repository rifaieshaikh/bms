"""Schema tests for inventory category list page."""

from vaybooks.bms.ui.inventory_list_schemas import (
    INVENTORY_CATEGORIES,
    _match_inv_category_active,
)


def test_inventory_categories_schema_fields():
    filter_keys = {f.key for f in INVENTORY_CATEGORIES.filter_fields}
    assert filter_keys == {"name", "path", "active_only"}
    sort_keys = {s.key for s in INVENTORY_CATEGORIES.sort_options}
    assert sort_keys == {"created_at", "name"}
    assert INVENTORY_CATEGORIES.default_sort == "created_at"
    assert INVENTORY_CATEGORIES.entity_key == "inventory_categories"


def test_match_inv_category_active():
    class Active:
        is_active = True

    class Inactive:
        is_active = False

    assert _match_inv_category_active(Active(), True) is True
    assert _match_inv_category_active(Inactive(), True) is False
