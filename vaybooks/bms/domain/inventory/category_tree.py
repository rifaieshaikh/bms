"""Helpers for hierarchical product categories."""

from __future__ import annotations

from typing import Dict, List, Optional

from vaybooks.bms.domain.inventory.entities import ProductCategory
from vaybooks.bms.domain.shared.exceptions import ValidationError


def normalize_parent_id(parent_id: Optional[str]) -> Optional[str]:
    if not parent_id or not str(parent_id).strip():
        return None
    return str(parent_id).strip()


def build_category_path(
    category_id: str,
    categories_by_id: Dict[str, ProductCategory],
    *,
    separator: str = " > ",
) -> str:
    parts: List[str] = []
    current_id: Optional[str] = category_id
    seen: set[str] = set()
    while current_id and current_id not in seen:
        seen.add(current_id)
        category = categories_by_id.get(current_id)
        if not category:
            break
        parts.append(category.name)
        current_id = category.parent_id
    parts.reverse()
    return separator.join(parts)


def build_category_paths(
    category_ids: List[str],
    categories_by_id: Dict[str, ProductCategory],
) -> List[str]:
    return [
        build_category_path(cid, categories_by_id)
        for cid in category_ids
        if cid in categories_by_id
    ]


def validate_category_parent(
    category_id: Optional[str],
    parent_id: Optional[str],
    categories_by_id: Dict[str, ProductCategory],
) -> None:
    parent_id = normalize_parent_id(parent_id)
    if not parent_id:
        return
    if category_id and parent_id == category_id:
        raise ValidationError("A category cannot be its own parent")
    if parent_id not in categories_by_id:
        raise ValidationError("Parent category not found")
    if not category_id:
        return
    current: Optional[str] = parent_id
    seen: set[str] = set()
    while current:
        if current == category_id:
            raise ValidationError("Category parent would create a cycle")
        if current in seen:
            break
        seen.add(current)
        parent = categories_by_id.get(current)
        current = parent.parent_id if parent else None


def list_descendant_ids(
    category_id: str,
    categories_by_id: Dict[str, ProductCategory],
) -> set[str]:
    children = {
        cid
        for cid, cat in categories_by_id.items()
        if cat.parent_id == category_id
    }
    descendants = set(children)
    for child_id in list(children):
        descendants |= list_descendant_ids(child_id, categories_by_id)
    return descendants
