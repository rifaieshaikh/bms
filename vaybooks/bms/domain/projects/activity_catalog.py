from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ActivityCategory, ActivityType


CREATED_STATUS = "Created"
COMPLETED_STATUS = "Completed"
DEFAULT_ACTIVITY_STATUSES = [CREATED_STATUS, COMPLETED_STATUS]


def normalize_statuses(statuses: Optional[List[str]]) -> List[str]:
    """Return a clean status list bookended by Created ... Completed.

    Custom statuses supplied by the user are placed between the two defaults,
    de-duplicated (case-insensitively) and stripped of blanks. The mandatory
    Created/Completed entries are always present regardless of input.
    """
    result = [CREATED_STATUS]
    seen = {CREATED_STATUS.lower(), COMPLETED_STATUS.lower()}
    for status in statuses or []:
        name = str(status).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    result.append(COMPLETED_STATUS)
    return result


CATEGORY_METADATA = {
    ActivityCategory.IN_HOUSE_SERVICE: {
        "is_in_house": True,
        "requires_time_tracking": True,
        "requires_pricing": True,
        "activity_type": ActivityType.IN_HOUSE,
    },
    ActivityCategory.IN_HOUSE_MATERIAL: {
        "is_in_house": True,
        "requires_time_tracking": False,
        "requires_pricing": False,
        "activity_type": ActivityType.MATERIAL,
    },
    ActivityCategory.OUTSOURCED_SERVICE: {
        "is_in_house": False,
        "requires_time_tracking": False,
        "requires_pricing": False,
        "activity_type": ActivityType.OUTSOURCED,
    },
    ActivityCategory.OUTSOURCED_MATERIAL: {
        "is_in_house": False,
        "requires_time_tracking": False,
        "requires_pricing": False,
        "activity_type": ActivityType.MATERIAL,
    },
}


def category_metadata(category: ActivityCategory) -> dict:
    return CATEGORY_METADATA[category]


@dataclass
class ProjectActivityConfig:
    activity_name: str
    activity_type: ActivityType = ActivityType.IN_HOUSE
    activity_category: ActivityCategory = ActivityCategory.IN_HOUSE_SERVICE
    is_in_house: bool = False
    requires_time_tracking: bool = False
    default_hourly_rate: float = 0.0
    default_amount: float = 0.0
    statuses: List[str] = field(
        default_factory=lambda: list(DEFAULT_ACTIVITY_STATUSES)
    )
    is_active: bool = True
    is_system: bool = False
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
            self.default_hourly_rate = 0.0

    @property
    def requires_pricing(self) -> bool:
        return category_metadata(self.activity_category)["requires_pricing"]
