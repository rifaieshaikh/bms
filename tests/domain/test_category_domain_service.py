"""Tests for category CRUD via InventoryAppService (domain rules)."""

import pytest

from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import make_inventory_app_service


def _service():
    return make_inventory_app_service()


def test_create_root_and_child_path():
    service = _service()
    fabric = service.create_category("Fabric")
    cotton = service.create_category("Cotton", parent_id=fabric.id)
    assert cotton.parent_id == fabric.id
    assert service.get_category_path(cotton.id) == "Fabric > Cotton"


def test_same_name_under_different_parents_allowed():
    service = _service()
    fabric = service.create_category("Fabric")
    ready = service.create_category("Ready-made")
    service.create_category("Cotton", parent_id=fabric.id)
    cotton2 = service.create_category("Cotton", parent_id=ready.id)
    assert cotton2.parent_id == ready.id


def test_duplicate_name_same_parent_rejected():
    service = _service()
    fabric = service.create_category("Fabric")
    service.create_category("Cotton", parent_id=fabric.id)
    with pytest.raises(ValidationError, match="already exists under the parent"):
        service.create_category("Cotton", parent_id=fabric.id)


def test_create_with_invalid_parent():
    service = _service()
    with pytest.raises(ValidationError, match="Parent category not found"):
        service.create_category("Orphan", parent_id="missing-id")


def test_empty_name_on_create():
    service = _service()
    with pytest.raises(ValidationError, match="Category name is required"):
        service.create_category("   ")


def test_update_not_found():
    service = _service()
    with pytest.raises(ValidationError, match="Category not found"):
        service.update_category("missing", "Name")


def test_empty_name_on_update():
    service = _service()
    cat = service.create_category("Fabric")
    with pytest.raises(ValidationError, match="Category name is required"):
        service.update_category(cat.id, "  ")


def test_reparent_updates_path():
    service = _service()
    fabric = service.create_category("Fabric")
    ready = service.create_category("Ready-made")
    cotton = service.create_category("Cotton", parent_id=fabric.id)
    service.update_category(cotton.id, "Cotton", parent_id=ready.id)
    assert service.get_category_path(cotton.id) == "Ready-made > Cotton"


def test_deactivate_excluded_from_active_only_list():
    service = _service()
    cat = service.create_category("Fabric")
    service.update_category(cat.id, "Fabric", is_active=False)
    active = service.list_categories(active_only=True)
    all_cats = service.list_categories(active_only=False)
    assert cat.id not in {c.id for c in active}
    assert cat.id in {c.id for c in all_cats}


def test_delete_leaf_category():
    service = _service()
    cat = service.create_category("Fabric")
    service.delete_category(cat.id)
    assert service.get_category(cat.id) is None


def test_delete_blocked_with_children():
    service = _service()
    fabric = service.create_category("Fabric")
    service.create_category("Cotton", parent_id=fabric.id)
    with pytest.raises(ValidationError, match="child categories"):
        service.delete_category(fabric.id)


def test_delete_blocked_with_products():
    service = _service()
    cat = service.create_category("Fabric")
    service.create_product("SKU-1", "Cotton", cat.id, opening_qty=0)
    with pytest.raises(ValidationError, match="has products"):
        service.delete_category(cat.id)


def test_product_create_invalid_category():
    service = _service()
    with pytest.raises(ValidationError, match="Category not found"):
        service.create_product("SKU-1", "Item", "missing-cat", opening_qty=0)


def test_multi_category_product_paths():
    service = _service()
    fabric = service.create_category("Fabric")
    cotton = service.create_category("Cotton", parent_id=fabric.id)
    product = service.create_product(
        "SKU-1", "Blend", [fabric.id, cotton.id], opening_qty=0
    )
    assert product.category_ids == [fabric.id, cotton.id]
    assert product.category_names == ["Fabric", "Fabric > Cotton"]
