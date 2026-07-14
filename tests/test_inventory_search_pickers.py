"""Tests for category/unit search helpers used by product pickers."""

from tests.conftest import make_inventory_app_service


def test_search_categories_limits_and_filters():
    service = make_inventory_app_service()
    service.create_category("Apparel")
    service.create_category("Accessories")
    service.create_category("Fabric")

    all_default = service.search_categories("", limit=2)
    assert len(all_default) == 2

    hits = service.search_categories("app", limit=25)
    assert [c.name for c in hits] == ["Apparel"]


def test_search_units_limits_and_filters():
    service = make_inventory_app_service()
    service.find_or_create_unit("pcs", "Pieces")
    service.find_or_create_unit("mtr", "Meter")
    service.find_or_create_unit("box", "Box")

    limited = service.search_units("", limit=2)
    assert len(limited) == 2

    hits = service.search_units("met", limit=25)
    assert len(hits) == 1
    assert hits[0].code == "mtr"


def test_category_paths_for_does_not_require_full_list():
    service = make_inventory_app_service()
    root = service.create_category("Apparel")
    child = service.create_category("Sarees", parent_id=root.id)
    paths = service.category_paths_for([child.id])
    assert paths[child.id] == "Apparel > Sarees"
