import pytest

from vaybooks.bms.application.store.activities.service import StoreActivityAppService
from vaybooks.bms.domain.shared.enums import ActivityCategory, ActivityType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.store.activities.entities import StoreActivityConfig


class _FakeStoreActivityRepo:
    def __init__(self):
        self.store: dict[str, StoreActivityConfig] = {}

    def save(self, activity: StoreActivityConfig) -> StoreActivityConfig:
        self.store[activity.id] = activity
        return activity

    def find_by_id(self, activity_id: str):
        return self.store.get(activity_id)

    def find_by_name(self, name: str):
        for activity in self.store.values():
            if activity.activity_name == name:
                return activity
        return None

    def list_all(self, active_only: bool = True):
        activities = list(self.store.values())
        if active_only:
            activities = [a for a in activities if a.is_active]
        return activities


@pytest.fixture
def svc():
    return StoreActivityAppService(_FakeStoreActivityRepo())


def test_create_in_house_service_activity(svc):
    activity = svc.create_activity(
        "Billing", ActivityCategory.IN_HOUSE_SERVICE.value, 150.0
    )
    assert activity.activity_name == "Billing"
    assert activity.activity_type == ActivityType.IN_HOUSE
    assert activity.requires_time_tracking is True
    assert activity.default_hourly_expense == 150.0
    assert activity.statuses[0] == "Created"
    assert activity.statuses[-1] == "Completed"


def test_create_requires_name(svc):
    with pytest.raises(ValidationError):
        svc.create_activity("   ", ActivityCategory.IN_HOUSE_SERVICE.value, 100.0)


def test_in_house_service_requires_hourly_expense(svc):
    with pytest.raises(ValidationError):
        svc.create_activity("Billing", ActivityCategory.IN_HOUSE_SERVICE.value, 0.0)


def test_create_rejects_duplicate_name(svc):
    svc.create_activity("Billing", ActivityCategory.IN_HOUSE_SERVICE.value, 150.0)
    with pytest.raises(ValidationError, match="already exists"):
        svc.create_activity("billing", ActivityCategory.IN_HOUSE_SERVICE.value, 100.0)


def test_update_and_deactivate(svc):
    activity = svc.create_activity(
        "Packing", ActivityCategory.IN_HOUSE_SERVICE.value, 120.0
    )
    updated = svc.update_activity_details(
        activity.id,
        "Packing & Dispatch",
        ActivityCategory.IN_HOUSE_SERVICE.value,
        140.0,
        is_active=True,
        custom_statuses=["Wrapping"],
    )
    assert updated.activity_name == "Packing & Dispatch"
    assert updated.default_hourly_expense == 140.0
    assert "Wrapping" in updated.statuses

    deactivated = svc.deactivate_activity(activity.id)
    assert deactivated.is_active is False
    assert svc.list_activities(active_only=True) == []
    assert len(svc.list_activities(active_only=False)) == 1
