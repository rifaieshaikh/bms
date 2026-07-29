"""Tests for per-location balances, sales deduction, and stock transfers."""

from datetime import date

import pytest

from vaybooks.bms.domain.shared.enums import (
    LocationType,
    StockMovementType,
    StockReferenceType,
    StockTransferStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import make_inventory_app_service


def _inv_with_locations():
    inv = make_inventory_app_service()
    wh = inv.create_location("MAIN", "Main Warehouse", location_type=LocationType.WAREHOUSE)
    store = inv.create_location(
        "STORE1", "Retail Store", location_type=LocationType.RETAIL_STORE
    )
    category = inv.create_category("Goods")
    product = inv.create_product(
        "SKU-LOC",
        "Widget",
        category.id,
        opening_qty=0,
    )
    return inv, wh, store, product


def test_purchase_receive_updates_location_balance():
    inv, wh, _store, product = _inv_with_locations()
    inv.apply_purchase_receive(
        [
            {
                "product_id": product.id,
                "qty": 10,
                "location_id": wh.id,
            }
        ],
        "grn-bal-1",
        StockReferenceType.GRN,
        date.today(),
    )
    assert inv.get_product(product.id).current_qty == 10
    assert inv.get_stock_balance(product.id, wh.id) == 10.0
    balances = inv.list_balances_by_product(product.id)
    assert len(balances) == 1
    assert balances[0].location_id == wh.id


def test_sale_movements_deduct_from_location():
    inv, wh, store, product = _inv_with_locations()
    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 8, "location_id": store.id}],
        "grn-sale-1",
        StockReferenceType.GRN,
        date.today(),
    )
    inv.apply_sales_movements(
        "inv-1",
        [{"product_id": product.id, "qty": 3, "location_id": store.id}],
        date.today(),
    )
    assert inv.get_product(product.id).current_qty == 5
    assert inv.get_stock_balance(product.id, store.id) == 5.0
    assert inv.get_stock_balance(product.id, wh.id) == 0.0


def test_location_oversell_allowed_while_global_check_still_applies():
    inv, wh, store, product = _inv_with_locations()
    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 5, "location_id": wh.id}],
        "grn-over-1",
        StockReferenceType.GRN,
        date.today(),
    )
    # Oversell at store (no stock there) is allowed at location level
    inv.apply_sales_movements(
        "inv-over-1",
        [{"product_id": product.id, "qty": 2, "location_id": store.id}],
        date.today(),
    )
    assert inv.get_stock_balance(product.id, store.id) == -2.0
    assert inv.get_product(product.id).current_qty == 3

    # Global insufficient stock still blocks
    with pytest.raises(ValidationError):
        inv.apply_sales_movements(
            "inv-over-2",
            [{"product_id": product.id, "qty": 10, "location_id": wh.id}],
            date.today(),
        )


def test_stock_transfer_lifecycle():
    inv, wh, store, product = _inv_with_locations()
    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 10, "location_id": wh.id}],
        "grn-xfer-1",
        StockReferenceType.GRN,
        date.today(),
    )
    transfer = inv.create_stock_transfer(
        "ST-0001",
        wh.id,
        store.id,
        date.today(),
        [{"product_id": product.id, "qty": 4}],
    )
    assert transfer.status == StockTransferStatus.DRAFT
    assert inv.get_stock_balance(product.id, wh.id) == 10.0

    transfer = inv.dispatch_stock_transfer(transfer.id)
    assert transfer.status == StockTransferStatus.IN_TRANSIT
    assert inv.get_stock_balance(product.id, wh.id) == 6.0
    assert inv.get_stock_balance(product.id, store.id) == 0.0
    assert inv.get_product(product.id).current_qty == 6.0

    transfer = inv.receive_stock_transfer(transfer.id)
    assert transfer.status == StockTransferStatus.RECEIVED
    assert inv.get_stock_balance(product.id, store.id) == 4.0
    assert inv.get_product(product.id).current_qty == 10.0

    movements = inv._domain._movement_repo.list_by_reference(transfer.id)
    types = {m.movement_type for m in movements}
    assert StockMovementType.TRANSFER_OUT in types
    assert StockMovementType.TRANSFER_IN in types


def test_initiate_send_in_transit_updates_source_only():
    inv, wh, store, product = _inv_with_locations()
    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 10, "location_id": wh.id}],
        "grn-xfer-init",
        StockReferenceType.GRN,
        date.today(),
    )
    transfer = inv.create_stock_transfer(
        "ST-INIT",
        wh.id,
        store.id,
        date.today(),
        [{"product_id": product.id, "qty": 3}],
        send_in_transit=True,
        allowed_location_ids=[wh.id, store.id],
    )
    assert transfer.status == StockTransferStatus.IN_TRANSIT
    assert inv.get_stock_balance(product.id, wh.id) == 7.0
    assert inv.get_stock_balance(product.id, store.id) == 0.0

    inv.receive_stock_transfer(transfer.id, allowed_location_ids=[wh.id, store.id])
    assert inv.get_stock_balance(product.id, store.id) == 3.0


def test_transfer_rejects_locations_outside_access():
    inv, wh, store, product = _inv_with_locations()
    other = inv.create_location("OTHER", "Other WH", location_type=LocationType.WAREHOUSE)
    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 5, "location_id": wh.id}],
        "grn-xfer-acl",
        StockReferenceType.GRN,
        date.today(),
    )
    with pytest.raises(ValidationError, match="locations you have access"):
        inv.create_stock_transfer(
            "ST-ACL",
            wh.id,
            other.id,
            date.today(),
            [{"product_id": product.id, "qty": 1}],
            allowed_location_ids=[wh.id, store.id],
        )


def test_transfer_out_requires_source_location_qty():
    inv, wh, store, product = _inv_with_locations()
    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 5, "location_id": store.id}],
        "grn-xfer-loc",
        StockReferenceType.GRN,
        date.today(),
    )
    transfer = inv.create_stock_transfer(
        "ST-LOC",
        wh.id,
        store.id,
        date.today(),
        [{"product_id": product.id, "qty": 2}],
    )
    with pytest.raises(ValidationError, match="Insufficient stock at location"):
        inv.dispatch_stock_transfer(transfer.id)


def test_list_stock_transfers_filters_by_accessible_locations():
    inv, wh, store, product = _inv_with_locations()
    other = inv.create_location("X", "X", location_type=LocationType.WAREHOUSE)
    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 5, "location_id": wh.id}],
        "grn-list",
        StockReferenceType.GRN,
        date.today(),
    )
    t1 = inv.create_stock_transfer(
        "ST-L1", wh.id, store.id, date.today(), [{"product_id": product.id, "qty": 1}]
    )
    t2 = inv.create_stock_transfer(
        "ST-L2",
        wh.id,
        other.id,
        date.today(),
        [{"product_id": product.id, "qty": 1}],
    )
    visible = inv.list_stock_transfers(location_ids=[store.id])
    ids = {t.id for t in visible}
    assert t1.id in ids
    assert t2.id not in ids


def test_cancel_dispatched_transfer_reverses_out():
    inv, wh, store, product = _inv_with_locations()
    inv.apply_purchase_receive(
        [{"product_id": product.id, "qty": 5, "location_id": wh.id}],
        "grn-cancel-1",
        StockReferenceType.GRN,
        date.today(),
    )
    transfer = inv.create_stock_transfer(
        "ST-0002",
        wh.id,
        store.id,
        date.today(),
        [{"product_id": product.id, "qty": 2}],
    )
    inv.dispatch_stock_transfer(transfer.id)
    assert inv.get_stock_balance(product.id, wh.id) == 3.0

    cancelled = inv.cancel_stock_transfer(transfer.id)
    assert cancelled.status == StockTransferStatus.CANCELLED
    assert inv.get_stock_balance(product.id, wh.id) == 5.0
    assert inv.get_product(product.id).current_qty == 5.0


def test_stock_transfer_status_parses_legacy_dispatched():
    assert StockTransferStatus("Dispatched") == StockTransferStatus.IN_TRANSIT
    assert StockTransferStatus.DISPATCHED == StockTransferStatus.IN_TRANSIT


def test_opening_stock_uses_explicit_location():
    inv = make_inventory_app_service()
    wh = inv.create_location("OPEN", "Opening WH")
    category = inv.create_category("OpenCat")
    product = inv.create_product(
        "SKU-OPEN",
        "Open Widget",
        category.id,
        opening_qty=7,
        location_id=wh.id,
    )
    assert inv.get_product(product.id).current_qty == 7
    assert inv.get_stock_balance(product.id, wh.id) == 7.0
