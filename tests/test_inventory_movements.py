"""Tests for manual stock movements and per-product ledger."""

from datetime import date

import pytest

from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.domain.shared.enums import StockMovementType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import make_inventory_app_service


def _service() -> InventoryAppService:
    return make_inventory_app_service()


def test_opening_qty_creates_receive_movement():
    service = _service()
    category = service.create_category("Fabric")
    product = service.create_product("SKU-1", "Cotton", category.id, opening_qty=5)
    assert product.current_qty == 5
    ledger = service.get_product_ledger(product.id)
    assert len(ledger) == 1
    assert ledger[0]["movement_type"] == StockMovementType.RECEIVE.value
    assert ledger[0]["balance"] == 5


def test_receive_and_issue_update_running_balance():
    service = _service()
    category = service.create_category("Fabric")
    product = service.create_product("SKU-1", "Cotton", category.id, opening_qty=10)
    service.record_manual_movement(
        product.id, StockMovementType.ISSUE, 3, date.today(), "Sample issue"
    )
    updated = service.get_product(product.id)
    assert updated.current_qty == 7
    ledger = service.get_product_ledger(product.id)
    assert ledger[-1]["balance"] == 7
    assert ledger[-1]["qty_out"] == 3


def test_insufficient_stock_blocks_issue():
    service = _service()
    category = service.create_category("Fabric")
    product = service.create_product("SKU-1", "Cotton", category.id, opening_qty=2)
    with pytest.raises(ValidationError, match="Insufficient stock"):
        service.record_manual_movement(
            product.id, StockMovementType.ISSUE, 5, date.today()
        )


def test_discontinue_product_clears_stock_and_deactivates():
    service = _service()
    category = service.create_category("Fabric")
    product = service.create_product("SKU-1", "Cotton", category.id, opening_qty=8)
    location = service.list_locations(active_only=True)[0]
    assert product.current_qty == 8
    assert service.get_stock_balance(product.id, location.id) == 8.0

    discontinued = service.discontinue_product(product.id)
    assert discontinued.is_active is False
    assert discontinued.current_qty == 0
    assert service.get_stock_balance(product.id, location.id) == 0.0

    ledger = service.get_product_ledger(product.id)
    adjust_outs = [
        row
        for row in ledger
        if row["movement_type"] == StockMovementType.ADJUST_OUT.value
    ]
    assert len(adjust_outs) == 1
    assert adjust_outs[0]["qty_out"] == 8
    assert "discontinue" in (adjust_outs[0].get("notes") or "").lower()


def test_update_product_to_inactive_clears_stock():
    service = _service()
    category = service.create_category("Fabric")
    product = service.create_product("SKU-2", "Silk", category.id, opening_qty=5)
    unit = service.find_or_create_unit("pcs")
    updated = service.update_product(
        product.id,
        product.sku,
        product.name,
        product.category_ids,
        unit.id,
        is_active=False,
        selling_rate=100.0,
        mrp=200.0,
        gst_rate=5.0,
    )
    assert updated.is_active is False
    assert updated.current_qty == 0
    ledger = service.get_product_ledger(product.id)
    assert any(
        row["movement_type"] == StockMovementType.ADJUST_OUT.value for row in ledger
    )
