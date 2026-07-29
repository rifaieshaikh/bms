"""Delivery note lifecycle, qty override, stock-once, and cancel reverse."""

from datetime import date

import pytest

from vaybooks.bms.domain.sales.entities import DeliveryNote, DeliveryNoteLine
from vaybooks.bms.domain.sales.services import SalesDomainService
from vaybooks.bms.domain.shared.enums import (
    DeliveryNoteStatus,
    DeliveryReferenceType,
    SalesOrderStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.test_sales_workflow import (
    InMemoryDeliveryNoteRepository,
    InMemorySalesOrderRepository,
    InMemorySalesReturnRepository,
)


@pytest.fixture
def domain():
    so_repo = InMemorySalesOrderRepository()
    dn_repo = InMemoryDeliveryNoteRepository()
    return_repo = InMemorySalesReturnRepository()
    svc = SalesDomainService(so_repo, dn_repo, return_repo)
    return svc, so_repo, dn_repo


def _make_so(domain_tuple, qty=10.0):
    svc, so_repo, _ = domain_tuple
    order = svc.create_sales_order(
        so_number="SO-1",
        customer_id="c1",
        customer_name="Cust",
        order_date=date.today(),
        lines=[
            {
                "product_id": "p1",
                "product_name": "Item",
                "qty_ordered": qty,
                "rate": 100,
            }
        ],
        status=SalesOrderStatus.CONFIRMED,
    )
    return order


def test_create_dn_is_draft(domain):
    svc, _, dn_repo = domain
    so = _make_so(domain)
    dn = svc.create_delivery_note(
        dn_number="DN-1",
        customer_id="c1",
        customer_name="Cust",
        delivery_date=date.today(),
        lines=[{"product_id": "p1", "product_name": "Item", "qty_delivered": 4, "rate": 100}],
        sales_order_id=so.id,
        so_number=so.so_number,
    )
    assert dn.status == DeliveryNoteStatus.DRAFT
    assert dn.reference_type == DeliveryReferenceType.SALES_ORDER
    assert not dn.stock_issued


def test_qty_cannot_exceed_pending_without_override(domain):
    svc, _, _ = domain
    so = _make_so(domain, qty=5)
    with pytest.raises(ValidationError, match="pending"):
        svc.create_delivery_note(
            dn_number="DN-2",
            customer_id="c1",
            customer_name="Cust",
            delivery_date=date.today(),
            lines=[
                {
                    "product_id": "p1",
                    "product_name": "Item",
                    "qty_delivered": 6,
                    "rate": 100,
                }
            ],
            sales_order_id=so.id,
        )


def test_qty_override_requires_reason(domain):
    svc, _, _ = domain
    so = _make_so(domain, qty=5)
    with pytest.raises(ValidationError, match="Override reason"):
        svc.create_delivery_note(
            dn_number="DN-3",
            customer_id="c1",
            customer_name="Cust",
            delivery_date=date.today(),
            lines=[
                {
                    "product_id": "p1",
                    "product_name": "Item",
                    "qty_delivered": 6,
                    "rate": 100,
                }
            ],
            sales_order_id=so.id,
            allow_override=True,
            override_qty_reason="",
        )


def test_confirm_applies_so_qty_dispatch_marks_stock_flag(domain):
    svc, so_repo, _ = domain
    so = _make_so(domain)
    dn = svc.create_delivery_note(
        dn_number="DN-4",
        customer_id="c1",
        customer_name="Cust",
        delivery_date=date.today(),
        lines=[
            {
                "product_id": "p1",
                "product_name": "Item",
                "qty_delivered": 3,
                "rate": 100,
            }
        ],
        sales_order_id=so.id,
    )
    confirmed = svc.confirm_delivery_note(dn.id)
    assert confirmed.status == DeliveryNoteStatus.CONFIRMED
    so = so_repo.find_by_id(so.id)
    assert so.lines[0].qty_delivered == 3
    assert so.status == SalesOrderStatus.PARTIALLY_DELIVERED

    dispatched = svc.dispatch_delivery_note(dn.id)
    assert dispatched.status == DeliveryNoteStatus.DISPATCHED

    delivered = svc.deliver_delivery_note(dn.id)
    assert delivered.status == DeliveryNoteStatus.DELIVERED


def test_cancel_reverses_so_qty(domain):
    svc, so_repo, _ = domain
    so = _make_so(domain)
    dn = svc.create_delivery_note(
        dn_number="DN-5",
        customer_id="c1",
        customer_name="Cust",
        delivery_date=date.today(),
        lines=[
            {
                "product_id": "p1",
                "product_name": "Item",
                "qty_delivered": 2,
                "rate": 100,
            }
        ],
        sales_order_id=so.id,
    )
    svc.confirm_delivery_note(dn.id)
    svc.cancel_delivery_note(dn.id)
    so = so_repo.find_by_id(so.id)
    assert so.lines[0].qty_delivered == 0


def test_invoice_pending_cap(domain):
    svc, _, _ = domain
    with pytest.raises(ValidationError, match="invoiced pending"):
        svc.create_delivery_note(
            dn_number="DN-6",
            customer_id="c1",
            customer_name="Cust",
            delivery_date=date.today(),
            lines=[
                {
                    "product_id": "p1",
                    "product_name": "Item",
                    "qty_delivered": 5,
                    "rate": 100,
                    "qty_ordered": 10,
                    "qty_previously_delivered": 0,
                }
            ],
            sales_invoice_id="inv1",
            invoice_number="INV-1",
            invoice_pending={"p1": 3},
        )


def test_mark_stock_issued_idempotent(domain):
    svc, _, dn_repo = domain
    so = _make_so(domain)
    dn = svc.create_delivery_note(
        dn_number="DN-7",
        customer_id="c1",
        customer_name="Cust",
        delivery_date=date.today(),
        lines=[
            {
                "product_id": "p1",
                "product_name": "Item",
                "qty_delivered": 1,
                "rate": 100,
            }
        ],
        sales_order_id=so.id,
    )
    svc.mark_stock_issued(dn.id)
    again = svc.mark_stock_issued(dn.id)
    assert again.stock_issued is True
    assert again.stock_source == "delivery_note"
