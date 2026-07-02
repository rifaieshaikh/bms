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
