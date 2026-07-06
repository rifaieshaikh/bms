from datetime import date, datetime
from typing import Any


def to_bson_value(value: Any) -> Any:
    """Convert Python date objects for BSON encoding (PyMongo cannot encode date)."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time())
    return value


def from_bson_date(value: Any) -> Any:
    """Convert BSON datetime back to date for domain entities."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def as_date(value: Any) -> date | None:
    """Normalize date, datetime, BSON, or date-like values to plain ``date``."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date") and callable(getattr(value, "date", None)):
        try:
            result = value.date()
            if isinstance(result, datetime):
                return result.date()
            if isinstance(result, date):
                return result
        except (TypeError, ValueError, AttributeError):
            pass
    converted = from_bson_date(value)
    if isinstance(converted, datetime):
        return converted.date()
    if isinstance(converted, date):
        return converted
    return None
