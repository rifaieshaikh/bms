from typing import List, Optional

from vaybooks.bms.domain.store.activities.entities import StoreActivityConfig
from vaybooks.bms.domain.store.activities.repository import StoreActivityRepository
from vaybooks.bms.domain.shared.enums import ActivityCategory
from vaybooks.bms.domain.shared.exceptions import ValidationError


class StoreActivityAppService:
    def __init__(self, activity_repo: StoreActivityRepository):
        self._repo = activity_repo

    def _assert_name_unique(
        self, name: str, exclude_id: Optional[str] = None
    ) -> None:
        normalized = name.strip().lower()
        for config in self._repo.list_all(active_only=False):
            if exclude_id and config.id == exclude_id:
                continue
            if config.activity_name.strip().lower() == normalized:
                raise ValidationError("Activity name already exists")

    def _validate_config(self, config: StoreActivityConfig) -> None:
        if not config.activity_name.strip():
            raise ValidationError("Activity name is required")
        if config.default_hourly_expense < 0:
            raise ValidationError("Default hourly expense cannot be negative")
        if config.requires_pricing and config.default_hourly_expense <= 0:
            raise ValidationError(
                "In House Service requires a default hourly expense"
            )

    def list_activities(
        self, active_only: bool = True
    ) -> List[StoreActivityConfig]:
        return self._repo.list_all(active_only=active_only)

    def get_activity(self, activity_id: str) -> Optional[StoreActivityConfig]:
        return self._repo.find_by_id(activity_id)

    def create_activity(
        self,
        activity_name: str,
        activity_category: str,
        default_hourly_expense: float = 0.0,
        custom_statuses: Optional[List[str]] = None,
    ) -> StoreActivityConfig:
        name = activity_name.strip()
        self._assert_name_unique(name)
        category = ActivityCategory(activity_category)
        activity = StoreActivityConfig(
            activity_name=name,
            activity_type=None,
            default_hourly_expense=default_hourly_expense,
        )
        activity.apply_category(category)
        activity.set_statuses(custom_statuses)
        self._validate_config(activity)
        return self._repo.save(activity)

    def update_activity_details(
        self,
        activity_id: str,
        activity_name: str,
        activity_category: str,
        default_hourly_expense: float = 0.0,
        is_active: bool = True,
        custom_statuses: Optional[List[str]] = None,
    ) -> StoreActivityConfig:
        activity = self._repo.find_by_id(activity_id)
        if not activity:
            raise ValueError("Error: Activity not found")
        name = activity_name.strip()
        self._assert_name_unique(name, exclude_id=activity_id)
        category = ActivityCategory(activity_category)
        activity.activity_name = name
        activity.default_hourly_expense = default_hourly_expense
        activity.is_active = is_active
        activity.apply_category(category)
        if custom_statuses is not None:
            activity.set_statuses(custom_statuses)
        self._validate_config(activity)
        return self._repo.save(activity)

    def deactivate_activity(self, activity_id: str) -> StoreActivityConfig:
        activity = self._repo.find_by_id(activity_id)
        if not activity:
            raise ValueError("Error: Activity not found")
        activity.is_active = False
        return self._repo.save(activity)
