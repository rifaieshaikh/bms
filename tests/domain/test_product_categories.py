"""Tests for multi-category products."""

from vaybooks.bms.domain.inventory.entities import InventoryProduct


def test_sync_legacy_category_fields():
    product = InventoryProduct(
        sku="SKU1",
        name="Item",
        category_ids=["c1", "c2"],
        category_names=["Fabric", "Cotton"],
    )
    product.sync_legacy_category_fields()
    assert product.category_id == "c1"
    assert product.category_name == "Fabric"
