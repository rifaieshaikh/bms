"""Product custom field definitions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProductFieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    BOOLEAN = "boolean"


@dataclass
class ProductFieldDefinition:
    key: str
    label: str
    field_type: ProductFieldType = ProductFieldType.TEXT
    id: str = field(default_factory=lambda: uuid4().hex)
    options: List[str] = field(default_factory=list)
    required: bool = False
    applies_to_category_ids: List[str] = field(default_factory=list)
    sort_order: int = 0
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()

    def applies_to_product(self, category_ids: List[str]) -> bool:
        if not self.is_active:
            return False
        if not self.applies_to_category_ids:
            return True
        return bool(set(category_ids) & set(self.applies_to_category_ids))


def normalize_field_key(key: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", (key or "").strip().lower()).strip("_")


def validate_custom_field_values(
    definitions: List[ProductFieldDefinition],
    values: Dict[str, Any],
    category_ids: List[str],
) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for definition in sorted(definitions, key=lambda d: d.sort_order):
        if not definition.applies_to_product(category_ids):
            continue
        raw = values.get(definition.key)
        if definition.field_type == ProductFieldType.BOOLEAN:
            cleaned[definition.key] = bool(raw)
            continue
        if raw in (None, "") and definition.required:
            raise ValidationError(f"{definition.label} is required")
        if raw in (None, ""):
            continue
        if definition.field_type == ProductFieldType.NUMBER:
            cleaned[definition.key] = float(raw)
        elif definition.field_type == ProductFieldType.DATE:
            if isinstance(raw, date):
                cleaned[definition.key] = raw.isoformat()
            else:
                cleaned[definition.key] = str(raw)[:10]
        elif definition.field_type == ProductFieldType.SELECT:
            choice = str(raw).strip()
            if choice not in definition.options:
                raise ValidationError(f"Invalid option for {definition.label}")
            cleaned[definition.key] = choice
        else:
            cleaned[definition.key] = str(raw).strip()
    return cleaned
