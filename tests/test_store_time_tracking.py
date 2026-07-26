from datetime import date

import pytest

from vaybooks.bms.application.store.time_tracking.service import (
    StoreTimeTrackingAppService,
)
from vaybooks.bms.domain.parties.workers.entities import (
    SOURCE_STORE,
    Worker,
    WorkerActivityRef,
)
from vaybooks.bms.domain.shared.enums import ActivityCategory
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.store.activities.entities import StoreActivityConfig
from vaybooks.bms.domain.store.time_tracking.entities import StoreTimeEntry


class _FakeTimeRepo:
    def __init__(self):
        self.store: dict[str, StoreTimeEntry] = {}

    def save(self, entry: StoreTimeEntry) -> StoreTimeEntry:
        self.store[entry.id] = entry
        return entry

    def find_by_id(self, entry_id: str):
        return self.store.get(entry_id)

    def list_all(self):
        return list(self.store.values())

    def search(self, **kwargs):
        return list(self.store.values())

    def delete(self, entry_id: str) -> None:
        self.store.pop(entry_id, None)


class _FakeActivityRepo:
    def __init__(self):
        self.store: dict[str, StoreActivityConfig] = {}

    def add(self, activity: StoreActivityConfig) -> StoreActivityConfig:
        self.store[activity.id] = activity
        return activity

    def find_by_id(self, activity_id: str):
        return self.store.get(activity_id)


class _FakeWorkerRepo:
    def __init__(self):
        self.store: dict[str, Worker] = {}

    def add(self, worker: Worker) -> Worker:
        self.store[worker.id] = worker
        return worker

    def find_by_id(self, worker_id: str):
        return self.store.get(worker_id)


def _store_activity(name="Billing", hourly=150.0, is_active=True):
    activity = StoreActivityConfig(
        activity_name=name,
        activity_type=None,
        default_hourly_expense=hourly,
    )
    activity.apply_category(ActivityCategory.IN_HOUSE_SERVICE)
    activity.is_active = is_active
    return activity


@pytest.fixture
def env():
    time_repo = _FakeTimeRepo()
    activity_repo = _FakeActivityRepo()
    worker_repo = _FakeWorkerRepo()
    svc = StoreTimeTrackingAppService(time_repo, activity_repo, worker_repo)

    activity = activity_repo.add(_store_activity())
    worker = worker_repo.add(
        Worker(
            worker_name="Asha",
            activity_refs=[
                WorkerActivityRef(activity_id=activity.id, source=SOURCE_STORE)
            ],
            default_hourly_rate=200.0,
        )
    )
    return svc, activity, worker, time_repo, activity_repo, worker_repo


def test_record_entry_computes_labour_cost_from_worker_rate(env):
    svc, activity, worker, *_ = env
    entry = svc.record_time_entry(
        activity_id=activity.id,
        worker_id=worker.id,
        work_date=date(2026, 7, 26),
        start_time="10:00",
        end_time="13:30",
        location_id="loc1",
        location_name="Main Store",
    )
    assert entry.duration_minutes == 210
    assert entry.hourly_rate == 200.0
    assert entry.labour_cost == 700.0  # 3.5h × 200
    assert entry.activity_name == "Billing"
    assert entry.worker_name == "Asha"
    assert entry.location_id == "loc1"


def test_record_entry_falls_back_to_activity_expense(env):
    svc, activity, _, _, _, worker_repo = env
    worker = worker_repo.add(
        Worker(
            worker_name="NoRate",
            activity_refs=[
                WorkerActivityRef(activity_id=activity.id, source=SOURCE_STORE)
            ],
            default_hourly_rate=0.0,
        )
    )
    entry = svc.record_time_entry(
        activity_id=activity.id,
        worker_id=worker.id,
        work_date=date(2026, 7, 26),
        start_time="10:00",
        end_time="12:00",
    )
    assert entry.hourly_rate == 150.0
    assert entry.labour_cost == 300.0


def test_record_rejects_worker_without_store_assignment(env):
    svc, activity, _, _, _, worker_repo = env
    outsider = worker_repo.add(
        Worker(worker_name="Ravi", activity_refs=["some-customization-id"])
    )
    with pytest.raises(ValidationError, match="not assigned"):
        svc.record_time_entry(
            activity_id=activity.id,
            worker_id=outsider.id,
            work_date=date(2026, 7, 26),
            start_time="10:00",
            end_time="12:00",
        )


def test_record_rejects_inactive_activity(env):
    svc, _, worker, _, activity_repo, _ = env
    inactive = activity_repo.add(_store_activity(name="Old", is_active=False))
    with pytest.raises(ValidationError, match="inactive"):
        svc.record_time_entry(
            activity_id=inactive.id,
            worker_id=worker.id,
            work_date=date(2026, 7, 26),
            start_time="10:00",
            end_time="12:00",
        )


def test_record_requires_times(env):
    svc, activity, worker, *_ = env
    with pytest.raises(ValidationError, match="required"):
        svc.record_time_entry(
            activity_id=activity.id,
            worker_id=worker.id,
            work_date=date(2026, 7, 26),
            start_time="",
            end_time="12:00",
        )


def test_update_recomputes_cost(env):
    svc, activity, worker, *_ = env
    entry = svc.record_time_entry(
        activity_id=activity.id,
        worker_id=worker.id,
        work_date=date(2026, 7, 26),
        start_time="10:00",
        end_time="12:00",
    )
    assert entry.labour_cost == 400.0

    updated = svc.update_time_entry(
        entry.id,
        work_date=date(2026, 7, 27),
        start_time="10:00",
        end_time="11:00",
        notes="short shift",
    )
    assert updated.duration_minutes == 60
    assert updated.labour_cost == 200.0
    assert updated.notes == "short shift"


def test_new_entry_defaults_to_created(env):
    svc, activity, worker, *_ = env
    entry = svc.record_time_entry(
        activity_id=activity.id,
        worker_id=worker.id,
        work_date=date(2026, 7, 26),
        start_time="10:00",
        end_time="12:00",
    )
    assert entry.status == "Created"
    assert entry.is_completed is False
    assert entry.completed_at is None


def test_complete_task_sets_status_and_timestamp(env):
    svc, activity, worker, *_ = env
    entry = svc.record_time_entry(
        activity_id=activity.id,
        worker_id=worker.id,
        work_date=date(2026, 7, 26),
        start_time="10:00",
        end_time="12:00",
    )
    completed = svc.complete_task(entry.id)
    assert completed.status == "Completed"
    assert completed.is_completed is True
    assert completed.completed_at is not None

    # Reverting to Created clears the completion timestamp.
    reverted = svc.set_status(entry.id, "Created")
    assert reverted.is_completed is False
    assert reverted.completed_at is None


def test_set_status_rejects_unknown_status(env):
    svc, activity, worker, *_ = env
    entry = svc.record_time_entry(
        activity_id=activity.id,
        worker_id=worker.id,
        work_date=date(2026, 7, 26),
        start_time="10:00",
        end_time="12:00",
    )
    with pytest.raises(ValidationError, match="Invalid status"):
        svc.set_status(entry.id, "Bogus")


def test_set_status_allows_activity_custom_status(env):
    svc, _, worker, _, activity_repo, worker_repo = env
    activity = _store_activity(name="With Flow")
    activity.set_statuses(["Wrapping"])
    activity_repo.add(activity)
    worker.activity_refs.append(
        WorkerActivityRef(activity_id=activity.id, source=SOURCE_STORE)
    )
    entry = svc.record_time_entry(
        activity_id=activity.id,
        worker_id=worker.id,
        work_date=date(2026, 7, 26),
        start_time="10:00",
        end_time="12:00",
    )
    moved = svc.set_status(entry.id, "Wrapping")
    assert moved.status == "Wrapping"
    assert moved.is_completed is False


def test_delete_entry(env):
    svc, activity, worker, time_repo, *_ = env
    entry = svc.record_time_entry(
        activity_id=activity.id,
        worker_id=worker.id,
        work_date=date(2026, 7, 26),
        start_time="10:00",
        end_time="12:00",
    )
    svc.delete_time_entry(entry.id)
    assert time_repo.list_all() == []
