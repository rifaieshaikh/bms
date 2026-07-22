"""Tests for sales return stock movements."""

from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.domain.shared.enums import StockMovementType
from tests.conftest import make_inventory_app_service


def _service() -> InventoryAppService:
    return make_inventory_app_service()


def test_sales_return_adds_stock():
    service = _service()
    category = service.create_category("Ready-made")
    product = service.create_product("SKU-1", "Kurta", category.id, opening_qty=5)
    service.apply_sales_return(
        "return-1",
        [{"product_id": product.id, "qty": 2, "description": "Return"}],
    )
    assert service.get_product(product.id).current_qty == 7
    ledger = service.get_product_ledger(product.id)
    rows = [r for r in ledger if r["movement_type"] == StockMovementType.SALES_RETURN.value]
    assert len(rows) == 1
    assert rows[0]["reference_id"] == "return-1"
