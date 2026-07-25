"""Domain tests for GRN disposition and batch/serial validation."""

from datetime import date

import pytest

from vaybooks.bms.domain.purchases.entities import PurchaseOrder, PurchaseOrderLine
from vaybooks.bms.domain.purchases.services import PurchaseDomainService
from vaybooks.bms.domain.shared.enums import PurchaseOrderStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.test_purchase_workflow import (
    InMemoryGRNRepository,
    InMemoryPurchaseOrderRepository,
    InMemoryReturnRepository,
)


def _service_with_po(product_id: str = "p1", qty_ordered: float = 10.0):
    po_repo = InMemoryPurchaseOrderRepository()
    grn_repo = InMemoryGRNRepository()
    return_repo = InMemoryReturnRepository()
    service = PurchaseDomainService(po_repo, grn_repo, return_repo)
    po = PurchaseOrder(
        po_number="PO-1",
        vendor_id="v1",
        vendor_name="Vendor",
        order_date=date.today(),
        status=PurchaseOrderStatus.SENT,
        lines=[
            PurchaseOrderLine(
                product_id=product_id,
                product_name="Widget",
                qty_ordered=qty_ordered,
                rate=10.0,
            )
        ],
    )
    po_repo.save(po)
    return service, po


def test_create_grn_requires_location():
    service, po = _service_with_po()
    with pytest.raises(ValidationError, match="Location is required"):
        service.create_grn(
            grn_number="GRN-1",
            vendor_id="v1",
            vendor_name="Vendor",
            receipt_date=date.today(),
            lines=[{"product_id": "p1", "qty_received": 2, "rate": 10}],
            purchase_order_id=po.id,
        )


def test_create_grn_validates_disposition_sum():
    service, po = _service_with_po()
    with pytest.raises(ValidationError, match="Accepted \\+ damaged \\+ rejected"):
        service.create_grn(
            grn_number="GRN-1",
            vendor_id="v1",
            vendor_name="Vendor",
            receipt_date=date.today(),
            location_id="wh1",
            location_name="Main",
            lines=[
                {
                    "product_id": "p1",
                    "qty_received": 5,
                    "qty_accepted": 3,
                    "qty_damaged": 1,
                    "qty_rejected": 0,
                    "rate": 10,
                }
            ],
            purchase_order_id=po.id,
        )


def test_create_grn_requires_batch_when_tracked():
    service, po = _service_with_po()
    with pytest.raises(ValidationError, match="Batch number is required"):
        service.create_grn(
            grn_number="GRN-1",
            vendor_id="v1",
            vendor_name="Vendor",
            receipt_date=date.today(),
            location_id="wh1",
            location_name="Main",
            lines=[
                {
                    "product_id": "p1",
                    "qty_received": 2,
                    "qty_accepted": 2,
                    "track_batch": True,
                    "rate": 10,
                }
            ],
            purchase_order_id=po.id,
        )


def test_create_grn_requires_serial_count_when_tracked():
    service, po = _service_with_po()
    with pytest.raises(ValidationError, match="Expected 2 serial"):
        service.create_grn(
            grn_number="GRN-1",
            vendor_id="v1",
            vendor_name="Vendor",
            receipt_date=date.today(),
            location_id="wh1",
            location_name="Main",
            lines=[
                {
                    "product_id": "p1",
                    "qty_received": 2,
                    "qty_accepted": 2,
                    "track_serial": True,
                    "serial_numbers": ["S1"],
                    "rate": 10,
                }
            ],
            purchase_order_id=po.id,
        )


def test_create_grn_stock_lines_use_accepted_and_location():
    service, po = _service_with_po()
    grn = service.create_grn(
        grn_number="GRN-1",
        vendor_id="v1",
        vendor_name="Vendor",
        receipt_date=date.today(),
        location_id="wh1",
        location_name="Main",
        lines=[
            {
                "product_id": "p1",
                "qty_received": 5,
                "qty_accepted": 4,
                "qty_damaged": 1,
                "qty_rejected": 0,
                "rate": 10,
            }
        ],
        purchase_order_id=po.id,
    )
    stock_lines = service.grn_to_stock_lines(grn)
    assert len(stock_lines) == 1
    assert stock_lines[0]["qty"] == 4
    assert stock_lines[0]["location_id"] == "wh1"
    assert grn.location_id == "wh1"
    assert grn.warehouse_id == "wh1"  # alias
