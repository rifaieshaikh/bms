from typing import List, Optional

from vaybooks.bms.domain.activities.entities import ActivityConfig
from vaybooks.bms.domain.activities.repository import ActivityRepository
from vaybooks.bms.domain.activities.services import ActivityDomainService
from vaybooks.bms.domain.orders.repository import OrderRepository
from vaybooks.bms.domain.shared.enums import ActivityCategory
from vaybooks.bms.domain.shared.exceptions import ActivityInUseError


class ActivityAppService:
    def __init__(
        self,
        activity_repo: ActivityRepository,
        order_repo: Optional[OrderRepository] = None,
    ):
        self._repo = activity_repo
        self._order_repo = order_repo
        self._domain = ActivityDomainService()

    def _assert_activity_not_in_use(self, activity_id: str) -> None:
        if not self._order_repo:
            return
        for order in self._order_repo.list_all():
            for order_activity in order.order_activities:
                if order_activity.activity_id == activity_id:
                    raise ActivityInUseError(
                        "Error: Cannot deactivate this activity — "
                        "it is still referenced by an order."
                    )

    def list_activities(self, active_only: bool = True) -> List[ActivityConfig]:
        return self._repo.list_all(active_only=active_only)

    def get_activity(self, activity_id: str) -> Optional[ActivityConfig]:
        return self._repo.find_by_id(activity_id)

    def create_activity(
        self,
        activity_name: str,
        activity_category: str,
        default_hourly_expense: float = 0.0,
        custom_statuses: Optional[List[str]] = None,
    ) -> ActivityConfig:
        category = ActivityCategory(activity_category)
        activity = ActivityConfig(
            activity_name=activity_name.strip(),
            activity_type=None,
            default_hourly_expense=default_hourly_expense,
        )
        activity.apply_category(category)
        activity.set_statuses(custom_statuses)
        self._domain.validate_activity_config(activity)
        return self._repo.save(activity)

    def update_activity_details(
        self,
        activity_id: str,
        activity_name: str,
        activity_category: str,
        default_hourly_expense: float = 0.0,
        is_active: bool = True,
        custom_statuses: Optional[List[str]] = None,
    ) -> ActivityConfig:
        activity = self._repo.find_by_id(activity_id)
        if not activity:
            raise ValueError("Error: Activity not found")
        if activity.is_active and not is_active:
            self._assert_activity_not_in_use(activity_id)
        category = ActivityCategory(activity_category)
        activity.activity_name = activity_name.strip()
        activity.default_hourly_expense = default_hourly_expense
        activity.is_active = is_active
        activity.apply_category(category)
        if custom_statuses is not None:
            activity.set_statuses(custom_statuses)
        self._domain.validate_activity_config(activity)
        return self._repo.save(activity)

    def update_activity(self, activity: ActivityConfig) -> ActivityConfig:
        self._domain.validate_activity_config(activity)
        return self._repo.save(activity)

    def deactivate_activity(self, activity_id: str) -> ActivityConfig:
        activity = self._repo.find_by_id(activity_id)
        if not activity:
            raise ValueError("Error: Activity not found")
        self._assert_activity_not_in_use(activity_id)
        activity.is_active = False
        return self._repo.save(activity)
