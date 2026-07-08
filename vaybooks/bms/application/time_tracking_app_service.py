from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.orders.repository import OrderRepository
from vaybooks.bms.domain.shared.date_utils import (
    calculate_duration_minutes,
    minutes_to_hours,
    utc_now,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.time_tracking.entities import TimeEntry
from vaybooks.bms.domain.time_tracking.repository import TimeTrackingRepository
from vaybooks.bms.domain.time_tracking.services import TimeTrackingDomainService


class TimeTrackingAppService:
    def __init__(
        self,
        time_repo: TimeTrackingRepository,
        order_repo: OrderRepository,
    ):
        self._time_repo = time_repo
        self._order_repo = order_repo
        self._domain = TimeTrackingDomainService(time_repo)

    def record_time_entry(
        self,
        order_id: str,
        bill_id: str,
        activity_id: str,
        work_date: date,
        start_time: str,
        end_time: str,
        worker_name: str = "",
        notes: str = "",
        ends_next_day: bool = False,
    ) -> TimeEntry:
        missing = []
        if not (start_time or "").strip():
            missing.append("start_time")
        if not (end_time or "").strip():
            missing.append("end_time")
        if missing:
            raise ValidationError(
                "; ".join(f"{field}: This field is required" for field in missing)
            )

        order = self._order_repo.find_by_id(order_id)
        bill = order.get_bill_by_id(bill_id)
        from vaybooks.bms.domain.activities.repository import ActivityRepository

        activity_name = ""
        for oa in order.order_activities:
            if oa.activity_id == activity_id:
                activity_name = oa.activity_name
                break

        return self._domain.create_time_entry(
            order_id=order.id,
            order_number=order.order_number,
            bill_id=bill_id,
            bill_number=bill.bill_number,
            activity_id=activity_id,
            activity_name=activity_name,
            work_date=work_date,
            start_time=start_time,
            end_time=end_time,
            worker_name=worker_name,
            notes=notes,
            ends_next_day=ends_next_day,
        )

    def get_entries_by_order(self, order_id: str) -> List[TimeEntry]:
        return self._time_repo.find_by_order(order_id)

    def get_entries_by_bill(self, bill_number: str) -> List[TimeEntry]:
        return self._time_repo.find_by_bill_number(bill_number)

    def get_summary(self, order_id: Optional[str] = None) -> dict:
        if order_id:
            entries = self._time_repo.find_by_order(order_id)
        else:
            entries = self._time_repo.list_all()
        return self._domain.get_summary(entries)

    def activity_hours_for_order(self, order_id: str) -> dict[str, float]:
        """Per-activity hours for an order, always from current persisted entries."""
        summary = self.get_summary(order_id)
        return {
            name: minutes_to_hours(minutes)
            for name, minutes in summary["by_activity"].items()
        }

    def list_all(self) -> List[TimeEntry]:
        return self._time_repo.list_all()

    def search_entries(
        self,
        bill_number: str = "",
        order_number: str = "",
        worker_name: str = "",
        activity_name: str = "",
        work_date_from: Optional[date] = None,
        work_date_to: Optional[date] = None,
    ) -> List[TimeEntry]:
        return self._time_repo.search(
            bill_number=bill_number.strip() or None,
            order_number=order_number.strip() or None,
            worker_name=worker_name.strip() or None,
            activity_name=activity_name.strip() or None,
            work_date_from=work_date_from,
            work_date_to=work_date_to,
        )

    def get_summary_for_entries(self, entries: List[TimeEntry]) -> dict:
        return self._domain.get_summary(entries)

    def get_entry(self, entry_id: str) -> Optional[TimeEntry]:
        return self._time_repo.find_by_id(entry_id)

    def update_time_entry(
        self,
        entry_id: str,
        work_date: date,
        start_time: str,
        end_time: str,
        worker_name: str = "",
        notes: str = "",
        activity_id: Optional[str] = None,
        activity_name: Optional[str] = None,
        ends_next_day: bool = False,
    ) -> TimeEntry:
        entry = self._time_repo.find_by_id(entry_id)
        if not entry:
            raise ValueError("Time entry not found")
        entry.work_date = work_date
        entry.start_time = start_time
        entry.end_time = end_time
        entry.duration_minutes = calculate_duration_minutes(
            start_time, end_time, ends_next_day=ends_next_day
        )
        entry.worker_name = worker_name
        entry.notes = notes
        if activity_id is not None:
            entry.activity_id = activity_id
            if activity_name is not None:
                entry.activity_name = activity_name
        entry.updated_at = utc_now()
        return self._time_repo.save(entry)

    def delete_time_entry(self, entry_id: str) -> None:
        self._time_repo.delete(entry_id)
