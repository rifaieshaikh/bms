"""Dated selling price, MRP, and GST rate history for products."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError


class RatePeriodStatus(str, Enum):
    ACTIVE = "Active"
    FUTURE = "Future"
    EXPIRED = "Expired"


@dataclass
class ProductRatePeriod:
    product_id: str
    value: float
    start_date: date
    end_date: Optional[date] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "value": self.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProductRatePeriod:
        start = data.get("start_date")
        if isinstance(start, str):
            start = date.fromisoformat(start[:10])
        end = data.get("end_date")
        if isinstance(end, str) and end:
            end = date.fromisoformat(end[:10])
        else:
            end = None
        return cls(
            id=str(data.get("id") or uuid4().hex),
            product_id=str(data["product_id"]),
            value=float(data.get("value") or 0),
            start_date=start,
            end_date=end,
            created_at=data.get("created_at", utc_now()),
        )


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value[:10])
    raise ValidationError("Invalid date")


def is_effective(period: ProductRatePeriod, as_of: date) -> bool:
    if period.start_date > as_of:
        return False
    if period.end_date is None:
        return True
    return period.end_date >= as_of


def period_status(period: ProductRatePeriod, as_of: date) -> RatePeriodStatus:
    if period.start_date > as_of:
        return RatePeriodStatus.FUTURE
    if period.end_date is not None and period.end_date < as_of:
        return RatePeriodStatus.EXPIRED
    return RatePeriodStatus.ACTIVE


def resolve_active_period(
    periods: List[ProductRatePeriod], as_of: Optional[date] = None
) -> Optional[ProductRatePeriod]:
    as_of = as_of or date.today()
    candidates = [p for p in periods if is_effective(p, as_of)]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.start_date)


def periods_overlap(a: ProductRatePeriod, b: ProductRatePeriod) -> bool:
    if a.id == b.id:
        return False
    a_end = a.end_date or date.max
    b_end = b.end_date or date.max
    return a.start_date <= b_end and b.start_date <= a_end


def validate_period_dates(start_date: date, end_date: Optional[date]) -> None:
    if end_date is not None and end_date < start_date:
        raise ValidationError("End date cannot be before start date")


def validate_no_overlaps(
    periods: List[ProductRatePeriod], *, exclude_id: Optional[str] = None
) -> None:
    active = [p for p in periods if p.id != exclude_id]
    for i, left in enumerate(active):
        for right in active[i + 1 :]:
            if periods_overlap(left, right):
                raise ValidationError("Rate periods cannot overlap")


def validate_rate_value(value: float, *, field_label: str, allow_zero: bool = False) -> None:
    if value < 0:
        raise ValidationError(f"{field_label} cannot be negative")
    if not allow_zero and value <= 0:
        raise ValidationError(f"{field_label} must be greater than zero")


def validate_product_pricing(selling_rate: float, mrp: float) -> None:
    validate_rate_value(selling_rate, field_label="Selling price")
    validate_rate_value(mrp, field_label="MRP")
    if selling_rate > mrp:
        raise ValidationError("Selling price cannot exceed MRP")


def validate_gst_rate_value(gst_rate: float, *, required: bool = False) -> None:
    if gst_rate < 0 or gst_rate > 100:
        raise ValidationError("GST rate must be between 0 and 100")
    if required and gst_rate < 0:
        raise ValidationError("GST rate is required")


def close_open_period_before(
    periods: List[ProductRatePeriod],
    new_start: date,
    *,
    repo_save,
) -> None:
    """Close any open period that would overlap a new period starting on new_start."""
    day_before = new_start.fromordinal(new_start.toordinal() - 1)
    for period in periods:
        if period.end_date is None and period.start_date < new_start:
            period.end_date = day_before
            repo_save(period)


def apply_immediate_rate_change(
    periods: List[ProductRatePeriod],
    product_id: str,
    new_value: float,
    *,
    edit_date: date,
    repo_save,
) -> ProductRatePeriod:
    """Close current effective period on edit_date; new period starts next day (or today if none)."""
    active = resolve_active_period(periods, edit_date)
    if active and float(active.value) == float(new_value):
        return active
    if active:
        active.end_date = edit_date
        repo_save(active)
    next_start = edit_date if not periods else edit_date.fromordinal(edit_date.toordinal() + 1)
    new_period = ProductRatePeriod(
        product_id=product_id,
        value=round(float(new_value), 2),
        start_date=next_start,
    )
    validate_no_overlaps(periods + [new_period])
    return repo_save(new_period)


def create_initial_period(
    product_id: str, value: float, *, start_date: Optional[date] = None
) -> ProductRatePeriod:
    return ProductRatePeriod(
        product_id=product_id,
        value=round(float(value), 2),
        start_date=start_date or date.today(),
    )
