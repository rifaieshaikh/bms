"""Tests for product units."""

import pytest

from vaybooks.bms.domain.inventory.entities import ProductUnit
from vaybooks.bms.domain.inventory.units import normalize_unit_code
from vaybooks.bms.domain.shared.exceptions import ValidationError


class FakeUnitRepo:
    def __init__(self):
        self._units: dict[str, ProductUnit] = {}

    def save(self, unit: ProductUnit) -> ProductUnit:
        self._units[unit.id] = unit
        return unit

    def find_by_id(self, unit_id: str):
        return self._units.get(unit_id)

    def find_by_code(self, code: str):
        for unit in self._units.values():
            if unit.code == code.strip().lower():
                return unit
        return None

    def list_all(self, active_only: bool = True):
        units = list(self._units.values())
        return [u for u in units if u.is_active] if active_only else units

    def count_products_using(self, unit_id: str) -> int:
        return 0


class FakeCategoryRepo:
    def list_all(self, active_only: bool = True):
        return []

    def find_by_id(self, category_id: str):
        return None

    def find_by_name(self, name: str):
        return None

    def find_by_parent_and_name(self, parent_id, name):
        return None

    def list_children(self, parent_id):
        return []

    def save(self, category):
        return category

    def delete(self, category_id):
        pass


class FakeProductRepo:
    def count_by_category(self, category_id: str) -> int:
        return 0

    def find_by_id(self, product_id: str):
        return None

    def find_by_sku(self, sku: str):
        return None

    def save(self, product):
        return product

    def list_all(self, active_only: bool = True):
        return []


class FakeMovementRepo:
    def save(self, movement):
        return movement


def _service():
    from vaybooks.bms.domain.inventory.services import InventoryDomainService

    return InventoryDomainService(
        FakeCategoryRepo(),
        FakeProductRepo(),
        FakeMovementRepo(),
        FakeUnitRepo(),
    )


def test_normalize_unit_code():
    assert normalize_unit_code(" PCS ") == "pcs"


def test_find_or_create_unit_dedupes():
    service = _service()
    first = service.find_or_create_unit("roll", "Roll")
    second = service.find_or_create_unit("ROLL", "Rolls")
    assert first.id == second.id
    assert len(service.list_units(active_only=False)) == 1


def test_update_unit_requires_label():
    service = _service()
    unit = service.find_or_create_unit("kg", "Kilograms")
    with pytest.raises(ValidationError):
        service.update_unit(unit.id, "", True)
