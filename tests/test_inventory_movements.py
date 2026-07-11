"""Tests for manual stock movements and per-product ledger."""

from datetime import date

import pytest

from vaybooks.bms.application.inventory_app_service import InventoryAppService
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
