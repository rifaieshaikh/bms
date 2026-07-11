"""Tests for sales-driven stock deduction."""

import pytest

from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.domain.shared.enums import StockMovementType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import make_inventory_app_service


def _service() -> InventoryAppService:
    return make_inventory_app_service()


def test_sale_movement_deducts_stock():
    service = _service()
    category = service.create_category("Ready-made")
    product = service.create_product("SKU-1", "Kurta", category.id, opening_qty=10)
    service.apply_sales_movements(
        "voucher-1",
        [{"product_id": product.id, "qty": 3, "description": "Kurta sale"}],
    )
    updated = service.get_product(product.id)
    assert updated.current_qty == 7
    ledger = service.get_product_ledger(product.id)
    sale_rows = [r for r in ledger if r["movement_type"] == StockMovementType.SALE.value]
    assert len(sale_rows) == 1
    assert sale_rows[0]["reference_id"] == "voucher-1"


def test_sale_blocks_when_insufficient_stock():
    service = _service()
    category = service.create_category("Ready-made")
    product = service.create_product("SKU-1", "Kurta", category.id, opening_qty=2)
    with pytest.raises(ValidationError, match="Insufficient stock"):
        service.apply_sales_movements(
            "voucher-1",
            [{"product_id": product.id, "qty": 5, "description": "Kurta sale"}],
        )


def test_manual_lines_without_product_id_are_skipped():
    service = _service()
    category = service.create_category("Ready-made")
    product = service.create_product("SKU-1", "Kurta", category.id, opening_qty=5)
    movements = service.apply_sales_movements(
        "voucher-1",
        [{"description": "Custom line", "qty": 1}],
    )
    assert movements == []
    assert service.get_product(product.id).current_qty == 5
