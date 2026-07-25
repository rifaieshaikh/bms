"""Filtering + sorting framework for list views.

Policy:
- ``exact`` string filters match on full-string equality, case-insensitive.
- ``regex`` string filters use case-insensitive ``re.search`` (invalid
  patterns match nothing).
- Multiple filter fields are combined with AND.
- A single ``multiselect`` field matches when the record value is in the
  selected values (the only OR allowed, within one field).
- ``select`` / ``entity_select`` fields hold a list of chosen values by
  default (``multi=False`` keeps them single-valued). A list matches when any
  chosen value matches, so per-value ``match`` predicates stay single-valued.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable, Optional

# Filter field types
EXACT = "exact"
REGEX = "regex"
SELECT = "select"
MULTISELECT = "multiselect"
DATE_RANGE = "date_range"
DATE = "date"
NUMBER_MIN = "number_min"
CHECKBOX = "checkbox"
ENTITY_SELECT = "entity_select"

# Types rendered as a dropdown of predefined / loaded options.
SELECT_TYPES = (SELECT, ENTITY_SELECT)

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


def string_equals(left: Any, right: Any) -> bool:
    """Case-insensitive, whitespace-trimmed full-string equality."""
    return (
        str(_norm(left)).strip().casefold() == str(_norm(right)).strip().casefold()
    )


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
    # Placeholder for an empty SELECT / ENTITY_SELECT dropdown.
    all_label: str = ALL_LABEL
    # Custom predicate(record, value) -> bool. When set, overrides the
    # type-based default matcher. Always called with a single value.
    match: Optional[Callable[[Any, Any], bool]] = None
    # SELECT / ENTITY_SELECT: allow choosing several options (OR within field).
    multi: bool = True

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


def is_multi_select(fld: FilterField) -> bool:
    """Whether ``fld`` stores a list of chosen dropdown values."""
    if fld.type == MULTISELECT:
        return True
    return fld.type in SELECT_TYPES and bool(getattr(fld, "multi", True))


def _as_values(value: Any) -> Optional[list]:
    """Return ``value`` as a list of selections, or None when it is scalar."""
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return None


def is_active_value(fld: FilterField, value: Any) -> bool:
    """Whether a stored filter value should constrain the results."""
    if value is None:
        return False
    if fld.type in (EXACT, REGEX):
        return bool(str(value).strip())
    if fld.type in SELECT_TYPES:
        values = _as_values(value)
        if values is not None:
            return bool(values)
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
        return string_equals(rec_value, value)

    if fld.type == REGEX:
        text = "" if rec_value is None else str(_norm(rec_value))
        try:
            return re.search(str(value), text, re.IGNORECASE) is not None
        except re.error:
            return False

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


def _match_single(fld: FilterField, record: Any, value: Any) -> bool:
    if fld.match is not None:
        return fld.match(record, value)
    return _default_match(fld, record, value)


def matches(fld: FilterField, record: Any, value: Any) -> bool:
    if fld.type in SELECT_TYPES:
        values = _as_values(value)
        if values is not None:
            # OR within one dropdown; predicates stay single-valued.
            return any(_match_single(fld, record, v) for v in values)
    return _match_single(fld, record, value)


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


MAX_SORT_LEVELS = 3


def default_sort(schema: ListSchema) -> list[dict]:
    return [{"key": schema.default_sort, "desc": bool(schema.default_desc)}]


def normalize_sort(schema: ListSchema, sort) -> list[dict]:
    """Return an ordered list of ``{{key, desc}}`` (max ``MAX_SORT_LEVELS``).

    Accepts legacy single-dict ``{{key, desc}}``, a list of such dicts, or
    empty / invalid input (falls back to ``default_sort``).
    """
    allowed = {s.key for s in schema.sort_options}
    raw: list = []
    if isinstance(sort, dict) and ("key" in sort or "desc" in sort):
        raw = [sort]
    elif isinstance(sort, (list, tuple)):
        raw = list(sort)
    seen: set[str] = set()
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not key or key not in allowed or key in seen:
            continue
        seen.add(key)
        out.append({"key": key, "desc": bool(item.get("desc", schema.default_desc))})
        if len(out) >= MAX_SORT_LEVELS:
            break
    return out or default_sort(schema)


def sort_records(records: list, schema: ListSchema, sort) -> list:
    criteria = normalize_sort(schema, sort)
    result = list(records)
    # Stable sort: apply lowest-priority criterion first.
    for crit in reversed(criteria):
        option = schema.sort_option(crit["key"])
        if option is None:
            continue
        attr = option.attr
        desc = bool(crit.get("desc", schema.default_desc))
        try:
            result = sorted(result, key=lambda r, a=attr: _sort_value(r, a), reverse=desc)
        except TypeError:
            pass
    return result


def filter_token(schema: ListSchema, filters: dict, sort) -> str:
    """Stable string capturing current filters+sort for pagination reset."""
    parts = []
    for fld in schema.filter_fields:
        value = filters.get(fld.key)
        if is_active_value(fld, value):
            parts.append(f"{fld.key}={value}")
    criteria = normalize_sort(schema, sort)
    encoded = ",".join(
        f"{c['key']}:{'desc' if c.get('desc') else 'asc'}" for c in criteria
    )
    parts.append(f"__sort={encoded}")
    return "|".join(parts)


def default_filters(schema: ListSchema) -> dict:
    result: dict = {}
    for fld in schema.filter_fields:
        if fld.default is not None:
            result[fld.key] = fld.default() if callable(fld.default) else fld.default
        elif fld.type == CHECKBOX:
            result[fld.key] = bool(fld.default_active)
        elif is_multi_select(fld):
            result[fld.key] = []
        else:
            result[fld.key] = None
    return result
