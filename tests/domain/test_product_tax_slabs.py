"""Tests for product GST/MRP slab model."""

from datetime import date

import pytest

from vaybooks.bms.domain.inventory.entities import InventoryProduct
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.item_tax import ProductGstSlab, ProductMrpSlab, validate_gst_slabs, validate_mrp_entries


def test_active_tax_profile_uses_active_slabs():
    product = InventoryProduct(sku="SKU1", name="Fabric", category_id="c1")
    product.apply_tax_data(
        "5208",
        [
            ProductGstSlab(gst_rate=5.0, effective_from=date(2024, 1, 1), is_active=False),
            ProductGstSlab(gst_rate=12.0, effective_from=date(2025, 4, 1), is_active=True),
        ],
        [
            ProductMrpSlab(mrp=400.0, effective_from=date(2024, 1, 1), is_active=False),
            ProductMrpSlab(mrp=500.0, effective_from=date(2025, 4, 1), is_active=True),
        ],
    )
    profile = product.active_tax_profile()
    assert profile.hsn_sac == "5208"
    assert profile.gst_rate == 12.0
    assert profile.mrp == 500.0
    assert profile.cgst_rate == 6.0


def test_validate_gst_requires_exactly_one_active():
    slabs = [
        ProductGstSlab(gst_rate=5.0, effective_from=date.today(), is_active=True),
        ProductGstSlab(gst_rate=12.0, effective_from=date(2026, 1, 1), is_active=True),
    ]
    with pytest.raises(ValidationError, match="Exactly one GST rate"):
        validate_gst_slabs(slabs)


def test_validate_gst_rejects_duplicate_dates():
    today = date.today()
    slabs = [
        ProductGstSlab(gst_rate=5.0, effective_from=today, is_active=True),
        ProductGstSlab(gst_rate=12.0, effective_from=today, is_active=False),
    ]
    with pytest.raises(ValidationError, match="Duplicate effective-from"):
        validate_gst_slabs(slabs)


def test_validate_mrp_requires_one_active():
    with pytest.raises(ValidationError, match="At least one MRP"):
        validate_mrp_entries([])


def test_default_slabs_on_new_product():
    product = InventoryProduct(sku="SKU1", name="Fabric", category_id="c1")
    product.apply_tax_data(
        "5208",
        [InventoryProduct.default_gst_slab(18.0)],
        [InventoryProduct.default_mrp_entry(999.0)],
    )
    assert product.active_gst_slab().gst_rate == 18.0
    assert product.active_mrp_slab().mrp == 999.0
