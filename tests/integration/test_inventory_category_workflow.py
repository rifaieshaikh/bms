"""Integration workflow tests for inventory categories."""

import pytest

from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import make_inventory_app_service


def test_hierarchy_product_linkage_and_delete_guards():
    service = make_inventory_app_service()

    fabric = service.create_category("Fabric")
    cotton = service.create_category("Cotton", parent_id=fabric.id)
    printed = service.create_category("Printed", parent_id=cotton.id)

    assert service.get_category_path(printed.id) == "Fabric > Cotton > Printed"

    product = service.create_product("SKU-WF-1", "Printed Cotton", cotton.id, opening_qty=5)
    assert product.category_id == cotton.id

    service.delete_category(printed.id)

    with pytest.raises(ValidationError, match="has products"):
        service.delete_category(cotton.id)

    with pytest.raises(ValidationError, match="child categories"):
        service.delete_category(fabric.id)

    service._product_repo._store.pop(product.id, None)

    service.delete_category(cotton.id)
    service.delete_category(fabric.id)

    assert service.get_category(fabric.id) is None
    assert service.get_category(cotton.id) is None


def test_reparent_reflects_in_product_paths_after_update():
    service = make_inventory_app_service()

    a = service.create_category("Group A")
    b = service.create_category("Group B")
    item_cat = service.create_category("Item Cat", parent_id=a.id)
    product = service.create_product("SKU-RP-1", "Widget", item_cat.id, opening_qty=1)

    assert service.get_category_path(item_cat.id) == "Group A > Item Cat"
    assert product.category_names == ["Group A > Item Cat"]

    service.update_category(item_cat.id, "Item Cat", parent_id=b.id)
    assert service.get_category_path(item_cat.id) == "Group B > Item Cat"

    refreshed = service.update_product(
        product.id,
        product.sku,
        product.name,
        item_cat.id,
        product.unit_id,
        product.selling_rate,
    )
    assert refreshed.category_names == ["Group B > Item Cat"]
