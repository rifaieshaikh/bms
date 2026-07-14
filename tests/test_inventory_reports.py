"""Tests for inventory report service."""

from datetime import date

from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.application.report_filters import (
    DateRange,
    LowStockFilter,
    StockOnHandFilter,
)
from vaybooks.bms.application.reports.inventory_report_service import (
    InventoryReportService,
)
from vaybooks.bms.domain.shared.enums import StockMovementType
from tests.conftest import make_inventory_app_service


def _service() -> InventoryReportService:
    return InventoryReportService(make_inventory_app_service())


def test_health_summary_counts_low_and_out_of_stock():
    service = _service()
    category = service._inventory.create_category("Fabric")
    service._inventory.create_product("SKU-1", "Cotton", category.id, opening_qty=10)
    service._inventory.create_product("SKU-2", "Silk", category.id, opening_qty=1)
    service._inventory.create_product("SKU-3", "Linen", category.id, opening_qty=0)

    summary = service.health_summary()
    assert summary["active_products"] == 3
    assert summary["low_stock_count"] == 1
    assert summary["out_of_stock_count"] == 1
    assert summary["total_units"] == 11
    assert len(summary["low_stock_items"]) >= 2


def test_stock_on_hand_report_filters_active_only():
    service = _service()
    category = service._inventory.create_category("Fabric")
    active = service._inventory.create_product(
        "SKU-1", "Cotton", category.id, opening_qty=5
    )
    inactive = service._inventory.create_product(
        "SKU-2", "Silk", category.id, opening_qty=3
    )
    service._inventory.update_product(
        inactive.id,
        inactive.sku,
        inactive.name,
        category.id,
        inactive.unit_id,
        is_active=False,
    )

    rows = service.stock_on_hand_report(StockOnHandFilter(active_only=True))
    assert len(rows) == 1
    assert rows[0]["sku"] == active.sku


def test_low_stock_report_uses_threshold():
    service = _service()
    category = service._inventory.create_category("Fabric")
    service._inventory.create_product("SKU-1", "Cotton", category.id, opening_qty=5)
    service._inventory.create_product("SKU-2", "Silk", category.id, opening_qty=1)

    rows = service.low_stock_report(LowStockFilter(threshold=2.0))
    assert len(rows) == 1
    assert rows[0]["sku"] == "SKU-2"
