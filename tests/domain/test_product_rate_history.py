"""Tests for product rate history resolution and validation."""

from datetime import date, timedelta

import pytest

from vaybooks.bms.domain.inventory.rate_history import (
    ProductRatePeriod,
    is_effective,
    period_status,
    resolve_active_period,
    validate_no_overlaps,
    validate_product_pricing,
    RatePeriodStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import make_inventory_app_service


def test_is_effective_open_ended():
    today = date.today()
    period = ProductRatePeriod(
        product_id="p1",
        value=100,
        start_date=today - timedelta(days=10),
    )
    assert is_effective(period, today)


def test_future_period_not_effective():
    today = date.today()
    period = ProductRatePeriod(
        product_id="p1",
        value=100,
        start_date=today + timedelta(days=5),
    )
    assert not is_effective(period, today)
    assert period_status(period, today) == RatePeriodStatus.FUTURE


def test_expired_period():
    today = date.today()
    period = ProductRatePeriod(
        product_id="p1",
        value=100,
        start_date=today - timedelta(days=30),
        end_date=today - timedelta(days=1),
    )
    assert not is_effective(period, today)
    assert period_status(period, today) == RatePeriodStatus.EXPIRED


def test_resolve_active_picks_latest_start():
    today = date.today()
    older = ProductRatePeriod(
        product_id="p1",
        value=80,
        start_date=today - timedelta(days=20),
        end_date=today,
    )
    current = ProductRatePeriod(
        product_id="p1",
        value=100,
        start_date=today - timedelta(days=5),
    )
    active = resolve_active_period([older, current], today)
    assert active is not None
    assert active.value == 100


def test_validate_product_pricing_rejects_selling_above_mrp():
    with pytest.raises(ValidationError, match="cannot exceed MRP"):
        validate_product_pricing(150, 100)


def test_create_product_writes_rate_history():
    service = make_inventory_app_service()
    unit = service.find_or_create_unit("pcs", "Pieces")
    cat = service.create_category("Fabric")
    product = service.create_product(
        "SKU-RH-1",
        "Cotton",
        [cat.id],
        unit_id=unit.id,
        selling_rate=100,
        mrp=200,
        gst_rate=5,
    )
    assert product.active_selling_rate == 100
    assert product.active_mrp == 200
    assert product.active_gst_rate == 5
    assert len(service.list_selling_rate_history(product.id)) == 1


def test_update_product_closes_prior_rate_on_change():
    service = make_inventory_app_service()
    unit = service.find_or_create_unit("pcs", "Pieces")
    cat = service.create_category("Fabric")
    product = service.create_product(
        "SKU-RH-2",
        "Silk",
        [cat.id],
        unit_id=unit.id,
        selling_rate=100,
        mrp=200,
        gst_rate=5,
    )
    service.update_product(
        product.id,
        product.sku,
        product.name,
        product.category_ids,
        unit.id,
        selling_rate=120,
        mrp=200,
        gst_rate=5,
    )
    history = service.list_selling_rate_history(product.id)
    assert len(history) == 2
    closed = [p for p in history if p.end_date is not None]
    assert len(closed) == 1
