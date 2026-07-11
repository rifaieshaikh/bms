"""Tests for legacy tax_profile migration in Mongo product repo."""

from datetime import datetime

from vaybooks.bms.infrastructure.repositories.mongo_inventory_repository import (
    MongoInventoryProductRepository,
)


def test_from_doc_migrates_legacy_tax_profile():
    repo = MongoInventoryProductRepository.__new__(MongoInventoryProductRepository)
    doc = {
        "_id": "p1",
        "sku": "SKU-1",
        "name": "Cotton",
        "category_id": "c1",
        "tax_profile": {
            "hsn_sac": "5208",
            "gst_rate": 12.0,
            "mrp": 450.0,
        },
    }
    product = repo._from_doc(doc)
    assert product.hsn_sac == "5208"
    assert len(product.gst_rates) == 1
    assert product.gst_rates[0].gst_rate == 12.0
    assert product.gst_rates[0].is_active is True
    assert len(product.mrp_entries) == 1
    assert product.mrp_entries[0].mrp == 450.0
    assert product.tax_profile.gst_rate == 12.0
    assert product.tax_profile.mrp == 450.0


def test_to_doc_persists_slabs():
    repo = MongoInventoryProductRepository.__new__(MongoInventoryProductRepository)
    doc = {
        "_id": "p1",
        "sku": "SKU-1",
        "name": "Cotton",
        "category_id": "c1",
        "tax_profile": {"hsn_sac": "5208", "gst_rate": 5.0, "mrp": 100.0},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    product = repo._from_doc(doc)
    saved = repo._to_doc(product)
    assert saved["hsn_sac"] == "5208"
    assert len(saved["gst_rates"]) == 1
    assert len(saved["mrp_entries"]) == 1
    assert saved["tax_profile"]["gst_rate"] == 5.0
