from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.orders.repository import OrderRepository
from vaybooks.bms.domain.shared.date_utils import calculate_duration_minutes, utc_now
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
    ) -> TimeEntry:
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

    def list_all(self) -> List[TimeEntry]:
        return self._time_repo.list_all()

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
    ) -> TimeEntry:
        entry = self._time_repo.find_by_id(entry_id)
        if not entry:
            raise ValueError("Time entry not found")
        entry.work_date = work_date
        entry.start_time = start_time
        entry.end_time = end_time
        entry.duration_minutes = calculate_duration_minutes(start_time, end_time)
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
