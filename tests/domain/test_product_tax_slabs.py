"""Tests for product GST/MRP via rate history."""

from datetime import date

from tests.conftest import make_inventory_app_service


def test_active_tax_profile_uses_resolved_rates():
    service = make_inventory_app_service()
    unit = service.find_or_create_unit("pcs", "Pieces")
    cat = service.create_category("Fabric")
    product = service.create_product(
        "SKU1",
        "Fabric",
        [cat.id],
        unit_id=unit.id,
        hsn_sac="5208",
        selling_rate=100,
        mrp=500,
        gst_rate=12.0,
    )
    profile = product.active_tax_profile()
    assert profile.hsn_sac == "5208"
    assert profile.gst_rate == 12.0
    assert profile.mrp == 500.0
    assert profile.cgst_rate == 6.0
