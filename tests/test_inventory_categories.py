"""Tests for inventory product categories."""

import pytest

from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import make_inventory_app_service


def _service() -> InventoryAppService:
    return make_inventory_app_service()


def test_create_and_list_categories():
    service = _service()
    category = service.create_category("Fabric", "Fabrics and materials")
    assert category.name == "Fabric"
    assert category.description == "Fabrics and materials"
    assert len(service.list_categories()) == 1


def test_duplicate_category_name_rejected():
    service = _service()
    service.create_category("Fabric")
    with pytest.raises(ValidationError, match="already exists"):
        service.create_category("Fabric")


def test_delete_category_blocked_when_products_exist():
    service = _service()
    category = service.create_category("Fabric")
    service.create_product("SKU-1", "Cotton", category.id, opening_qty=0)
    with pytest.raises(ValidationError, match="Cannot delete"):
        service.delete_category(category.id)


def test_get_category_delegation():
    service = _service()
    created = service.create_category("Fabric")
    loaded = service.get_category(created.id)
    assert loaded is not None
    assert loaded.name == "Fabric"
    assert service.get_category("missing") is None


def test_get_category_path_delegation():
    service = _service()
    root = service.create_category("Fabric")
    child = service.create_category("Cotton", parent_id=root.id)
    assert service.get_category_path(child.id) == "Fabric > Cotton"


def test_list_categories_active_only():
    service = _service()
    active = service.create_category("Active Cat")
    inactive = service.create_category("Inactive Cat")
    service.update_category(inactive.id, "Inactive Cat", is_active=False)
    assert len(service.list_categories(active_only=True)) == 1
    assert len(service.list_categories(active_only=False)) == 2


def test_update_category_happy_path():
    service = _service()
    cat = service.create_category("Fabric", "old desc")
    updated = service.update_category(
        cat.id, "Textiles", "new desc", is_active=True
    )
    assert updated.name == "Textiles"
    assert updated.description == "new desc"
    assert service.get_category(cat.id).name == "Textiles"


def test_delete_category_happy_path():
    service = _service()
    cat = service.create_category("Disposable")
    service.delete_category(cat.id)
    assert service.get_category(cat.id) is None


def test_create_child_via_app_service():
    service = _service()
    root = service.create_category("Fabric")
    child = service.create_category("Cotton", parent_id=root.id)
    assert child.parent_id == root.id
    assert service.get_category_path(child.id) == "Fabric > Cotton"
