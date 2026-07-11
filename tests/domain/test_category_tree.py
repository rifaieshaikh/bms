"""Tests for hierarchical categories."""

import pytest

from vaybooks.bms.domain.inventory.category_tree import (
    build_category_path,
    build_category_paths,
    list_descendant_ids,
    normalize_parent_id,
    validate_category_parent,
)
from vaybooks.bms.domain.inventory.entities import ProductCategory
from vaybooks.bms.domain.shared.exceptions import ValidationError


def test_normalize_parent_id_empty():
    assert normalize_parent_id(None) is None
    assert normalize_parent_id("") is None
    assert normalize_parent_id("   ") is None


def test_normalize_parent_id_strips():
    assert normalize_parent_id("  abc  ") == "abc"


def test_build_category_path():
    root = ProductCategory(id="r1", name="Fabric")
    child = ProductCategory(id="c1", name="Cotton", parent_id="r1")
    by_id = {root.id: root, child.id: child}
    assert build_category_path("c1", by_id) == "Fabric > Cotton"


def test_build_category_path_missing_ancestor():
    child = ProductCategory(id="c1", name="Cotton", parent_id="missing")
    by_id = {child.id: child}
    assert build_category_path("c1", by_id) == "Cotton"


def test_build_category_paths_multiple():
    root = ProductCategory(id="r1", name="Fabric")
    child = ProductCategory(id="c1", name="Cotton", parent_id="r1")
    other = ProductCategory(id="o1", name="Accessories")
    by_id = {root.id: root, child.id: child, other.id: other}
    paths = build_category_paths(["c1", "o1", "missing"], by_id)
    assert paths == ["Fabric > Cotton", "Accessories"]


def test_list_descendant_ids():
    root = ProductCategory(id="r1", name="Fabric")
    child = ProductCategory(id="c1", name="Cotton", parent_id="r1")
    grand = ProductCategory(id="g1", name="Printed", parent_id="c1")
    by_id = {root.id: root, child.id: child, grand.id: grand}
    assert list_descendant_ids("r1", by_id) == {"c1", "g1"}
    assert list_descendant_ids("c1", by_id) == {"g1"}
    assert list_descendant_ids("g1", by_id) == set()


def test_validate_parent_blocks_cycle():
    a = ProductCategory(id="a", name="A")
    b = ProductCategory(id="b", name="B", parent_id="a")
    c = ProductCategory(id="c", name="C", parent_id="b")
    by_id = {a.id: a, b.id: b, c.id: c}
    with pytest.raises(ValidationError, match="cycle"):
        validate_category_parent("a", "c", by_id)


def test_validate_parent_self():
    cat = ProductCategory(id="a", name="A")
    by_id = {cat.id: cat}
    with pytest.raises(ValidationError, match="cannot be its own parent"):
        validate_category_parent("a", "a", by_id)


def test_validate_parent_not_found():
    with pytest.raises(ValidationError, match="Parent category not found"):
        validate_category_parent(None, "missing", {})
