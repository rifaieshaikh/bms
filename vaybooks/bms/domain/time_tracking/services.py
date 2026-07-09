from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.shared.date_utils import calculate_duration_minutes, minutes_to_hours
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.time_tracking.entities import TimeEntry
from vaybooks.bms.domain.time_tracking.repository import TimeTrackingRepository


class TimeTrackingDomainService:
    def __init__(self, repo: TimeTrackingRepository):
        self._repo = repo

    def create_time_entry(
        self,
        order_id: str,
        order_number: str,
        bill_id: str,
        bill_number: str,
        activity_id: str,
        activity_name: str,
        work_date: date,
        start_time: str,
        end_time: str,
        worker_name: str = "",
        notes: str = "",
        ends_next_day: bool = False,
    ) -> TimeEntry:
        duration = calculate_duration_minutes(
            start_time, end_time, ends_next_day=ends_next_day
        )
        entry = TimeEntry(
            order_id=order_id,
            order_number=order_number,
            bill_id=bill_id,
            bill_number=bill_number,
            activity_id=activity_id,
            activity_name=activity_name,
            work_date=work_date,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            worker_name=worker_name,
            notes=notes,
        )
        return self._repo.save(entry)

    def get_total_minutes(
        self,
        entries: List[TimeEntry],
        activity_name: Optional[str] = None,
        bill_number: Optional[str] = None,
    ) -> int:
        filtered = entries
        if activity_name:
            filtered = [e for e in filtered if e.activity_name == activity_name]
        if bill_number:
            filtered = [e for e in filtered if e.bill_number == bill_number]
        return sum(e.duration_minutes for e in filtered)

    def get_summary(self, entries: List[TimeEntry]) -> dict:
        stitching = self.get_total_minutes(entries, activity_name="Stitching")
        hand_work = self.get_total_minutes(entries, activity_name="Handwork")
        by_bill: dict = {}
        by_activity: dict = {}
        for entry in entries:
            by_bill[entry.bill_number] = (
                by_bill.get(entry.bill_number, 0) + entry.duration_minutes
            )
            by_activity[entry.activity_name] = (
                by_activity.get(entry.activity_name, 0) + entry.duration_minutes
            )
        return {
            "total_stitching_minutes": stitching,
            "total_hand_work_minutes": hand_work,
            "total_stitching_hours": minutes_to_hours(stitching),
            "total_hand_work_hours": minutes_to_hours(hand_work),
            "by_bill": by_bill,
            "by_activity": by_activity,
        }
