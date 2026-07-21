from typing import List, Optional

from vaybooks.bms.domain.projects.activity_catalog import ProjectActivityConfig
from vaybooks.bms.domain.projects.repository import ProjectActivityConfigRepository
from vaybooks.bms.domain.shared.enums import ActivityCategory
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectActivityConfigAppService:
    def __init__(self, config_repo: ProjectActivityConfigRepository):
        self._repo = config_repo

    def _assert_name_unique(
        self, name: str, exclude_id: Optional[str] = None
    ) -> None:
        normalized = name.strip().lower()
        for config in self._repo.list_all(active_only=False):
            if exclude_id and config.id == exclude_id:
                continue
            if config.activity_name.strip().lower() == normalized:
                raise ValidationError("Activity name already exists")

    def _validate_config(self, config: ProjectActivityConfig) -> None:
        if not config.activity_name.strip():
            raise ValidationError("Activity name is required")
        if config.default_hourly_rate < 0:
            raise ValidationError("Default hourly rate cannot be negative")
        if config.default_amount < 0:
            raise ValidationError("Default amount cannot be negative")
        if config.requires_pricing and config.default_hourly_rate <= 0:
            raise ValidationError(
                "In House Service requires a default hourly rate"
            )

    def list_activities(
        self, active_only: bool = True
    ) -> List[ProjectActivityConfig]:
        return self._repo.list_all(active_only=active_only)

    def get_activity(self, activity_id: str) -> Optional[ProjectActivityConfig]:
        return self._repo.find_by_id(activity_id)

    def create_activity(
        self,
        activity_name: str,
        activity_category: str,
        default_hourly_rate: float = 0.0,
        default_amount: float = 0.0,
        custom_statuses: Optional[List[str]] = None,
    ) -> ProjectActivityConfig:
        name = activity_name.strip()
        self._assert_name_unique(name)
        category = ActivityCategory(activity_category)
        config = ProjectActivityConfig(
            activity_name=name,
            activity_type=None,
            default_hourly_rate=default_hourly_rate,
            default_amount=default_amount,
        )
        config.apply_category(category)
        config.set_statuses(custom_statuses)
        self._validate_config(config)
        return self._repo.save(config)

    def update_activity_details(
        self,
        activity_id: str,
        activity_name: str,
        activity_category: str,
        default_hourly_rate: float = 0.0,
        default_amount: float = 0.0,
        is_active: bool = True,
        custom_statuses: Optional[List[str]] = None,
    ) -> ProjectActivityConfig:
        config = self._repo.find_by_id(activity_id)
        if not config:
            raise ValueError("Error: Activity not found")
        name = activity_name.strip()
        self._assert_name_unique(name, exclude_id=activity_id)
        category = ActivityCategory(activity_category)
        config.activity_name = name
        config.default_hourly_rate = default_hourly_rate
        config.default_amount = default_amount
        config.is_active = is_active
        config.apply_category(category)
        if custom_statuses is not None:
            config.set_statuses(custom_statuses)
        self._validate_config(config)
        return self._repo.save(config)

    def deactivate_activity(self, activity_id: str) -> ProjectActivityConfig:
        config = self._repo.find_by_id(activity_id)
        if not config:
            raise ValueError("Error: Activity not found")
        config.is_active = False
        return self._repo.save(config)
