from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.boutique.activities.entities import (
    COMPLETED_STATUS,
    CREATED_STATUS,
    DEFAULT_ACTIVITY_STATUSES,
    category_metadata,
    normalize_statuses,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ActivityCategory, ActivityType

__all__ = [
    "COMPLETED_STATUS",
    "CREATED_STATUS",
    "DEFAULT_ACTIVITY_STATUSES",
    "StoreActivityConfig",
    "category_metadata",
    "normalize_statuses",
]


@dataclass
class StoreActivityConfig:
    """Catalog entry for a store (retail) activity.

    Mirrors the boutique ``ActivityConfig`` shape so both catalogs behave the
    same way in settings and on the employee picker.
    """

    activity_name: str
    activity_type: Optional[ActivityType] = None
    activity_category: ActivityCategory = ActivityCategory.IN_HOUSE_SERVICE
    is_in_house: bool = False
    requires_time_tracking: bool = False
    default_hourly_expense: float = 0.0
    statuses: List[str] = field(
        default_factory=lambda: list(DEFAULT_ACTIVITY_STATUSES)
    )
    is_active: bool = True
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.statuses = normalize_statuses(self.statuses)

    @property
    def custom_statuses(self) -> List[str]:
        """User-defined statuses between the mandatory Created/Completed."""
        return [
            status
            for status in self.statuses
            if status not in (CREATED_STATUS, COMPLETED_STATUS)
        ]

    def set_statuses(self, custom_statuses: Optional[List[str]]) -> None:
        self.statuses = normalize_statuses(custom_statuses)

    def apply_category(self, category: ActivityCategory) -> None:
        """Sync derived flags/type from the selected category."""
        meta = category_metadata(category)
        self.activity_category = category
        self.is_in_house = meta["is_in_house"]
        self.requires_time_tracking = meta["requires_time_tracking"]
        self.activity_type = meta["activity_type"]
        if not meta["requires_pricing"]:
            self.default_hourly_expense = 0.0

    @property
    def requires_pricing(self) -> bool:
        return category_metadata(self.activity_category)["requires_pricing"]
