"""Tests for inventory product categories."""

import pytest

from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import (
    FakeInventoryProductRepository,
    FakeProductCategoryRepository,
    FakeStockMovementRepository,
)


def _service() -> InventoryAppService:
    return InventoryAppService(
        FakeProductCategoryRepository(),
        FakeInventoryProductRepository(),
        FakeStockMovementRepository(),
    )


def test_create_and_list_categories():
    service = _service()
    category = service.create_category("Fabric", "Fabrics and materials")
    assert category.name == "Fabric"
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
