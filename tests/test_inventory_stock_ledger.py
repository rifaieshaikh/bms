"""Tests for global stock ledger."""

from datetime import date

from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.domain.shared.enums import StockMovementType
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_STOCK_LEDGER
from tests.conftest import make_inventory_app_service


def _service() -> InventoryAppService:
    return make_inventory_app_service()


def test_stock_ledger_returns_enriched_rows():
    service = _service()
    category = service.create_category("Fabric")
    product = service.create_product("SKU-1", "Cotton", category.id, opening_qty=4)
    service.record_manual_movement(
        product.id, StockMovementType.ISSUE, 1, date.today(), "Issue"
    )
    rows = service.get_stock_ledger()
    assert len(rows) == 2
    assert rows[0]["product_name"] == "Cotton"
    assert rows[0]["sku"] == "SKU-1"
    assert rows[0]["category_name"] == "Fabric"
    assert "balance" not in rows[0]


def test_stock_ledger_filter_by_product():
    service = _service()
    cat = service.create_category("Fabric")
    p1 = service.create_product("SKU-1", "Cotton", cat.id, opening_qty=1)
    p2 = service.create_product("SKU-2", "Silk", cat.id, opening_qty=1)
    rows = service.get_stock_ledger()
    filtered = F.apply_filters(
        rows,
        INVENTORY_STOCK_LEDGER,
        {"product_id": p1.id},
    )
    assert all(r["product_id"] == p1.id for r in filtered)
    assert len(filtered) == 1
    assert p2.id not in {r["product_id"] for r in filtered}
