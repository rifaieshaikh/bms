"""Tests for GRN receive and landed cost."""

from datetime import date

from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.domain.shared.enums import StockReferenceType
from tests.conftest import make_inventory_app_service


def _inventory() -> InventoryAppService:
    return make_inventory_app_service()


def test_apply_purchase_receive_increases_stock():
    inv = _inventory()
    category = inv.create_category("Fabric")
    product = inv.create_product("SKU-1", "Cotton", category.id)

    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 5, "description": "GRN"}],
        "grn-1",
        StockReferenceType.GRN,
        date.today(),
    )
    updated = inv.get_product(product.id)
    assert updated.current_qty == 5


def test_apply_purchase_receive_stores_warehouse_id():
    inv = _inventory()
    category = inv.create_category("Fabric")
    product = inv.create_product("SKU-1", "Cotton", category.id)
    warehouse = inv.create_warehouse("MAIN", "Main")

    inv.apply_purchase_receive(
        [
            {
                "product_id": product.id,
                "qty": 3,
                "warehouse_id": warehouse.id,
                "description": "GRN",
            }
        ],
        "grn-wh-1",
        StockReferenceType.GRN,
        date.today(),
    )
    movements = [
        m
        for m in inv._domain._movement_repo.list_by_reference("grn-wh-1")
    ]
    assert len(movements) == 1
    assert movements[0].warehouse_id == warehouse.id
    assert movements[0].qty == 3


def test_apply_landed_cost_updates_weighted_average():
    inv = _inventory()
    category = inv.create_category("Fabric")
    product = inv.create_product("SKU-1", "Cotton", category.id, opening_qty=10)

    inv.apply_landed_cost(
        [{"product_id": product.id, "qty": 10, "unit_cost": 100.0}]
    )
    updated = inv.get_product(product.id)
    assert updated.weighted_avg_cost == 100.0
    assert updated.last_purchase_rate == 100.0


def test_reverse_movements_by_reference():
    inv = _inventory()
    category = inv.create_category("Fabric")
    product = inv.create_product("SKU-1", "Cotton", category.id)
    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 4}],
        "bill-1",
        StockReferenceType.PURCHASE,
    )
    inv.reverse_movements_by_reference("bill-1")
    updated = inv.get_product(product.id)
    assert updated.current_qty == 0
