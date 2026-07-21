"""Unit tests for demo seed helpers."""

from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.infrastructure.db.demo_seed import (
    DEMO_CUSTOMERS,
    DEMO_PRODUCTS,
    DEMO_VENDORS,
    _parse_registration,
)


def test_parse_registration_accepts_common_forms():
    assert _parse_registration("Registered") is PartyRegistrationType.REGISTERED
    assert _parse_registration("composition") is PartyRegistrationType.COMPOSITION
    assert _parse_registration("UNREGISTERED") is PartyRegistrationType.UNREGISTERED
    assert _parse_registration("bogus") is PartyRegistrationType.UNREGISTERED


def test_demo_catalog_covers_gst_variants():
    customer_types = {c["registration_type"] for c in DEMO_CUSTOMERS}
    assert PartyRegistrationType.UNREGISTERED in customer_types
    assert PartyRegistrationType.REGISTERED in customer_types
    assert any(c.get("state_code") == "29" for c in DEMO_CUSTOMERS)

    vendor_types = {v["registration_type"] for v in DEMO_VENDORS}
    assert PartyRegistrationType.UNREGISTERED in vendor_types
    assert PartyRegistrationType.REGISTERED in vendor_types

    skus = {p["sku"] for p in DEMO_PRODUCTS}
    assert "DEMO-NOHSN-001" in skus
    assert any(p["gst_rate"] == 5.0 for p in DEMO_PRODUCTS)
    assert any(p["gst_rate"] == 18.0 for p in DEMO_PRODUCTS)
