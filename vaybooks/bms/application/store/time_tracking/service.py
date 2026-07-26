from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.parties.workers.entities import SOURCE_STORE
from vaybooks.bms.domain.parties.workers.repository import WorkerRepository
from vaybooks.bms.domain.shared.date_utils import (
    calculate_duration_minutes,
    utc_now,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.store.activities.entities import (
    COMPLETED_STATUS,
    DEFAULT_ACTIVITY_STATUSES,
)
from vaybooks.bms.domain.store.activities.repository import StoreActivityRepository
from vaybooks.bms.domain.store.time_tracking.entities import StoreTimeEntry
from vaybooks.bms.domain.store.time_tracking.repository import (
    StoreTimeTrackingRepository,
)


class StoreTimeTrackingAppService:
    def __init__(
        self,
        time_repo: StoreTimeTrackingRepository,
        activity_repo: StoreActivityRepository,
        worker_repo: WorkerRepository,
    ):
        self._time_repo = time_repo
        self._activity_repo = activity_repo
        self._worker_repo = worker_repo

    def _resolve_activity(self, activity_id: str):
        activity = self._activity_repo.find_by_id(activity_id)
        if activity is None:
            raise ValidationError("Store activity not found")
        if not activity.is_active:
            raise ValidationError("This store activity is inactive")
        if not activity.requires_time_tracking:
            raise ValidationError(
                "This store activity does not require task time tracking"
            )
        return activity

    def _resolve_worker(self, worker_id: str, activity_id: str):
        worker = self._worker_repo.find_by_id(worker_id)
        if worker is None:
            raise ValidationError("Employee not found")
        if not worker.has_activity(activity_id, SOURCE_STORE):
            raise ValidationError(
                "This employee is not assigned to the selected store activity"
            )
        return worker

    @staticmethod
    def _labour_cost(duration_minutes: int, hourly_rate: float) -> float:
        return round((duration_minutes / 60) * hourly_rate, 2)

    def record_time_entry(
        self,
        activity_id: str,
        worker_id: str,
        work_date: date,
        start_time: str,
        end_time: str,
        location_id: str = "",
        location_name: str = "",
        notes: str = "",
        ends_next_day: bool = False,
    ) -> StoreTimeEntry:
        missing = []
        if not (start_time or "").strip():
            missing.append("start_time")
        if not (end_time or "").strip():
            missing.append("end_time")
        if missing:
            raise ValidationError(
                "; ".join(f"{field}: This field is required" for field in missing)
            )

        activity = self._resolve_activity(activity_id)
        worker = self._resolve_worker(worker_id, activity_id)

        duration_minutes = calculate_duration_minutes(
            start_time, end_time, ends_next_day=ends_next_day
        )
        hourly_rate = float(
            worker.default_hourly_rate or activity.default_hourly_expense or 0.0
        )
        entry = StoreTimeEntry(
            activity_id=activity.id,
            activity_name=activity.activity_name,
            worker_id=worker.id,
            worker_name=worker.worker_name,
            work_date=work_date,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            hourly_rate=hourly_rate,
            labour_cost=self._labour_cost(duration_minutes, hourly_rate),
            location_id=location_id or "",
            location_name=location_name or "",
            notes=notes,
        )
        return self._time_repo.save(entry)

    def update_time_entry(
        self,
        entry_id: str,
        work_date: date,
        start_time: str,
        end_time: str,
        notes: str = "",
        ends_next_day: bool = False,
        activity_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        location_id: Optional[str] = None,
        location_name: Optional[str] = None,
    ) -> StoreTimeEntry:
        entry = self._time_repo.find_by_id(entry_id)
        if not entry:
            raise ValueError("Store task not found")

        target_activity_id = activity_id or entry.activity_id
        target_worker_id = worker_id or entry.worker_id
        activity = self._resolve_activity(target_activity_id)
        worker = self._resolve_worker(target_worker_id, target_activity_id)

        entry.activity_id = activity.id
        entry.activity_name = activity.activity_name
        entry.worker_id = worker.id
        entry.worker_name = worker.worker_name
        entry.work_date = work_date
        entry.start_time = start_time
        entry.end_time = end_time
        entry.duration_minutes = calculate_duration_minutes(
            start_time, end_time, ends_next_day=ends_next_day
        )
        entry.hourly_rate = float(
            worker.default_hourly_rate or activity.default_hourly_expense or 0.0
        )
        entry.labour_cost = self._labour_cost(
            entry.duration_minutes, entry.hourly_rate
        )
        if location_id is not None:
            entry.location_id = location_id or ""
        if location_name is not None:
            entry.location_name = location_name or ""
        entry.notes = notes
        entry.updated_at = utc_now()
        return self._time_repo.save(entry)

    def set_status(self, entry_id: str, status: str) -> StoreTimeEntry:
        entry = self._time_repo.find_by_id(entry_id)
        if not entry:
            raise ValueError("Business task not found")
        activity = self._activity_repo.find_by_id(entry.activity_id)
        allowed = (
            activity.statuses if activity else list(DEFAULT_ACTIVITY_STATUSES)
        )
        if status not in allowed:
            raise ValidationError(f"Invalid status: {status}")
        entry.status = status
        entry.completed_at = utc_now() if status == COMPLETED_STATUS else None
        entry.updated_at = utc_now()
        return self._time_repo.save(entry)

    def complete_task(self, entry_id: str) -> StoreTimeEntry:
        return self.set_status(entry_id, COMPLETED_STATUS)

    def list_all(self) -> List[StoreTimeEntry]:
        return self._time_repo.list_all()

    def get_entry(self, entry_id: str) -> Optional[StoreTimeEntry]:
        return self._time_repo.find_by_id(entry_id)

    def search_entries(
        self,
        worker_name: str = "",
        activity_name: str = "",
        location_id: str = "",
        work_date_from: Optional[date] = None,
        work_date_to: Optional[date] = None,
    ) -> List[StoreTimeEntry]:
        return self._time_repo.search(
            worker_name=worker_name.strip() or None,
            activity_name=activity_name.strip() or None,
            location_id=location_id.strip() or None,
            work_date_from=work_date_from,
            work_date_to=work_date_to,
        )

    def delete_time_entry(self, entry_id: str) -> None:
        self._time_repo.delete(entry_id)
