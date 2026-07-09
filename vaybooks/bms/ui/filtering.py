"""Exact-match filtering + sorting framework for list views.

Locked policy:
- String filters match on strict equality (no substring / regex / fuzzy).
- Multiple filter fields are combined with AND.
- A single ``multiselect`` field matches when the record value is in the
  selected values (the only OR allowed, within one field).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable, Optional

# Filter field types
EXACT = "exact"
SELECT = "select"
MULTISELECT = "multiselect"
DATE_RANGE = "date_range"
DATE = "date"
NUMBER_MIN = "number_min"
CHECKBOX = "checkbox"
ENTITY_SELECT = "entity_select"

ALL_LABEL = "All"


def _norm(value: Any) -> Any:
    """Normalize an enum to its value for comparison."""
    if isinstance(value, Enum):
        return value.value
    return value


def _get(record: Any, attr: str) -> Any:
    """Read an attribute from a dataclass/object or a dict row."""
    if isinstance(record, dict):
        return record.get(attr)
    return getattr(record, attr, None)


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


@dataclass
class FilterField:
    key: str
    label: str
    type: str
    record_attr: Optional[str] = None
    options: Optional[list] = None
    options_loader: Optional[str] = None
    placeholder: str = ""
    help: str = ""
    default_active: bool = False
    default: Any = None
    # Custom predicate(record, value) -> bool. When set, overrides the
    # type-based default matcher.
    match: Optional[Callable[[Any, Any], bool]] = None

    @property
    def attr(self) -> str:
        return self.record_attr or self.key


@dataclass
class SortOption:
    key: str
    label: str
    record_attr: Optional[str] = None

    @property
    def attr(self) -> str:
        return self.record_attr or self.key


@dataclass
class ListSchema:
    entity_key: str
    title: str
    filter_fields: list[FilterField]
    sort_options: list[SortOption]
    default_sort: str
    default_desc: bool = True
    page_size: int = 12

    def field(self, key: str) -> Optional[FilterField]:
        for f in self.filter_fields:
            if f.key == key:
                return f
        return None

    def sort_option(self, key: str) -> Optional[SortOption]:
        for s in self.sort_options:
            if s.key == key:
                return s
        return None


def is_active_value(fld: FilterField, value: Any) -> bool:
    """Whether a stored filter value should constrain the results."""
    if value is None:
        return False
    if fld.type in (EXACT,):
        return bool(str(value).strip())
    if fld.type in (SELECT, ENTITY_SELECT):
        return value not in (None, "", ALL_LABEL)
    if fld.type == MULTISELECT:
        return bool(value)
    if fld.type == DATE_RANGE:
        return bool(value) and value[0] is not None and value[1] is not None
    if fld.type == DATE:
        return value is not None
    if fld.type == NUMBER_MIN:
        try:
            return float(value) > 0
        except (TypeError, ValueError):
            return False
    if fld.type == CHECKBOX:
        return bool(value)
    return bool(value)


def _default_match(fld: FilterField, record: Any, value: Any) -> bool:
    attr = fld.attr
    rec_value = _get(record, attr)

    if fld.type == EXACT:
        return str(_norm(rec_value)).strip() == str(value).strip()

    if fld.type in (SELECT, ENTITY_SELECT):
        return str(_norm(rec_value)) == str(value)

    if fld.type == MULTISELECT:
        return _norm(rec_value) in set(value)

    if fld.type == DATE_RANGE:
        start, end = value
        rec_date = _as_date(rec_value)
        if rec_date is None:
            return False
        return start <= rec_date <= end

    if fld.type == DATE:
        rec_date = _as_date(rec_value)
        return rec_date == value

    if fld.type == NUMBER_MIN:
        try:
            return float(rec_value or 0) >= float(value)
        except (TypeError, ValueError):
            return False

    if fld.type == CHECKBOX:
        # Only reached when value is True (active); default: attr is truthy.
        return bool(rec_value)

    return True


def matches(fld: FilterField, record: Any, value: Any) -> bool:
    if fld.match is not None:
        return fld.match(record, value)
    return _default_match(fld, record, value)


def apply_filters(
    records: list, schema: ListSchema, filters: dict
) -> list:
    """Return records satisfying every active filter (AND across fields)."""
    active: list[tuple[FilterField, Any]] = []
    for fld in schema.filter_fields:
        value = filters.get(fld.key)
        if is_active_value(fld, value):
            active.append((fld, value))
    if not active:
        return list(records)
    return [
        record
        for record in records
        if all(matches(fld, record, value) for fld, value in active)
    ]


def _sort_value(record: Any, attr: str) -> Any:
    value = _norm(_get(record, attr))
    if value is None:
        return (1, "")  # push None to the end for ascending
    if isinstance(value, datetime):
        return (0, value.timestamp())
    if isinstance(value, date):
        return (0, datetime(value.year, value.month, value.day).timestamp())
    if isinstance(value, (int, float)):
        return (0, value)
    return (0, str(value).lower())


def sort_records(records: list, schema: ListSchema, sort: dict) -> list:
    sort_key = (sort or {}).get("key", schema.default_sort)
    desc = (sort or {}).get("desc", schema.default_desc)
    option = schema.sort_option(sort_key) or schema.sort_option(schema.default_sort)
    if option is None:
        return list(records)
    attr = option.attr
    try:
        return sorted(records, key=lambda r: _sort_value(r, attr), reverse=desc)
    except TypeError:
        return list(records)


def filter_token(schema: ListSchema, filters: dict, sort: dict) -> str:
    """Stable string capturing current filters+sort for pagination reset."""
    parts = []
    for fld in schema.filter_fields:
        value = filters.get(fld.key)
        if is_active_value(fld, value):
            parts.append(f"{fld.key}={value}")
    sort_key = (sort or {}).get("key", schema.default_sort)
    desc = (sort or {}).get("desc", schema.default_desc)
    parts.append(f"__sort={sort_key}:{'desc' if desc else 'asc'}")
    return "|".join(parts)


def default_filters(schema: ListSchema) -> dict:
    result: dict = {}
    for fld in schema.filter_fields:
        if fld.default is not None:
            result[fld.key] = fld.default() if callable(fld.default) else fld.default
        elif fld.type == CHECKBOX:
            result[fld.key] = bool(fld.default_active)
        elif fld.type == MULTISELECT:
            result[fld.key] = []
        else:
            result[fld.key] = None
    return result


def default_sort(schema: ListSchema) -> dict:
    return {"key": schema.default_sort, "desc": schema.default_desc}
