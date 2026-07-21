"""Unit tests for multi-vertical demo seed helpers."""

from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.infrastructure.db.demo_seed import _parse_registration
from vaybooks.bms.infrastructure.db.demo_seed_profiles import (
    KERALA_STATE,
    PROFILE_ORDER,
    PROFILES,
    build_customer_rows,
    build_vendor_rows,
    expand_category_tree,
    expand_products,
    profiles_to_run,
    resolve_business_settings,
)


def test_parse_registration_accepts_common_forms():
    assert _parse_registration("Registered") is PartyRegistrationType.REGISTERED
    assert _parse_registration("composition") is PartyRegistrationType.COMPOSITION
    assert _parse_registration("UNREGISTERED") is PartyRegistrationType.UNREGISTERED
    assert _parse_registration("bogus") is PartyRegistrationType.UNREGISTERED


def test_all_profiles_registered():
    assert set(PROFILES) == set(PROFILE_ORDER)
    assert len(PROFILE_ORDER) == 10


def test_profiles_to_run_single_list_all():
    assert profiles_to_run("boutique") == ["boutique"]
    assert profiles_to_run("pharma, hardware") == ["pharma", "hardware"]
    assert profiles_to_run("all") == list(PROFILE_ORDER)
    assert profiles_to_run("tiles-granites") == ["tiles_granites"]
    assert profiles_to_run("unknown") == []
    assert profiles_to_run("none") == []
    assert profiles_to_run("off") == []
    assert profiles_to_run("") == []


def test_expand_counts():
    profile = PROFILES["boutique"]
    cats = expand_category_tree(profile, 100)
    assert len(cats) == 100
    assert cats[0][0] is None
    products = expand_products(profile, 100)
    assert len(products) == 100
    assert products[0]["sku"].startswith("BOUT-")
    assert products[0]["opening_qty"] > 0
    assert products[1]["sku"] != products[0]["sku"]


def test_customer_vendor_namespaces_and_kerala():
    bout = build_customer_rows(PROFILES["boutique"], 5)
    pos = build_customer_rows(PROFILES["pos"], 5)
    assert bout[0]["state_code"] == KERALA_STATE
    assert bout[0]["phone_number"].startswith("90001")
    assert pos[0]["phone_number"].startswith("90002")
    assert {c["phone_number"] for c in bout}.isdisjoint(
        {c["phone_number"] for c in pos}
    )
    vendors = build_vendor_rows(PROFILES["hardware"], 10)
    assert vendors[0]["phone_number"].startswith("91009")
    assert all(v["state_code"] == KERALA_STATE for v in vendors)


def test_pos_party_mix_includes_composition():
    rows = build_customer_rows(PROFILES["pos"], 100)
    types = {r["registration_type"] for r in rows}
    assert PartyRegistrationType.UNREGISTERED in types
    assert PartyRegistrationType.REGISTERED in types
    assert PartyRegistrationType.COMPOSITION in types


def test_business_single_vs_multi():
    single = resolve_business_settings(["boutique"])
    assert "Boutique" in single["legal_name"] or "Silk" in single["legal_name"]
    assert single["state"] == KERALA_STATE

    multi = resolve_business_settings(["boutique", "pharma"])
    assert multi["legal_name"] == "Seed Multi Vertical Demo"

    all_profiles = resolve_business_settings(list(PROFILE_ORDER))
    assert all_profiles["legal_name"] == multi["legal_name"]

    overridden = resolve_business_settings(
        ["boutique"],
        blocks={"boutique": {"legal_name": "Custom Boutique"}},
    )
    assert overridden["legal_name"] == "Custom Boutique"

    flat = resolve_business_settings(
        ["boutique"],
        flat_overlay={"seed_business_legal_name": "Flat Name"},
    )
    assert flat["legal_name"] == "Flat Name"


def test_profile_sku_prefixes_unique():
    prefixes = {p.sku_prefix for p in PROFILES.values()}
    assert len(prefixes) == len(PROFILES)
