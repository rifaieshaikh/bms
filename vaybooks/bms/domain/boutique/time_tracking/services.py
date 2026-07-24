from datetime import date
from typing import List, Optional, Union

from vaybooks.bms.domain.boutique.deliveries.entities import Delivery
from vaybooks.bms.domain.boutique.orders.entities import CustomizationItem, CustomizationOrder
from vaybooks.bms.domain.shared.date_utils import (
    calculate_duration_minutes,
    minutes_to_hours,
    utc_now,
)
from vaybooks.bms.domain.boutique.time_tracking.entities import (
    DELIVERY_ACTIVITY_NAME,
    ETD_ACTIVITY_ID,
    ETD_ACTIVITY_NAME,
    TaskType,
    TimeEntry,
)
from vaybooks.bms.domain.boutique.time_tracking.repository import TimeTrackingRepository


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
        task_type: TaskType = TaskType.ACTIVITY,
        duration_minutes: Optional[int] = None,
    ) -> TimeEntry:
        if duration_minutes is None:
            duration = calculate_duration_minutes(
                start_time, end_time, ends_next_day=ends_next_day
            )
        else:
            duration = duration_minutes
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
            task_type=task_type,
        )
        return self._repo.save(entry)

    def upsert_etd_task(
        self, order: CustomizationOrder, item: CustomizationItem
    ) -> Optional[TimeEntry]:
        etd = item.expected_delivery_date or order.expected_delivery_date
        if not etd:
            return None
        existing = next(
            (
                e
                for e in self._repo.find_by_order(order.id)
                if e.task_type == TaskType.ETD and e.bill_id == item.item_id
            ),
            None,
        )
        if existing:
            if existing.work_date == etd and existing.bill_number == item.bill_number:
                return existing
            existing.work_date = etd
            existing.bill_number = item.bill_number
            existing.order_number = order.order_number
            existing.updated_at = utc_now()
            return self._repo.save(existing)
        return self.create_time_entry(
            order_id=order.id,
            order_number=order.order_number,
            bill_id=item.item_id,
            bill_number=item.bill_number,
            activity_id=ETD_ACTIVITY_ID,
            activity_name=ETD_ACTIVITY_NAME,
            work_date=etd,
            start_time="",
            end_time="",
            duration_minutes=0,
            task_type=TaskType.ETD,
            notes="System ETD task",
        )

    def sync_etd_tasks_for_order(self, order: CustomizationOrder) -> List[TimeEntry]:
        return [
            entry
            for item in order.customization_items
            if (entry := self.upsert_etd_task(order, item)) is not None
        ]

    def create_delivery_task(
        self, order: CustomizationOrder, delivery: Delivery
    ) -> TimeEntry:
        bill_ids = list(delivery.bill_ids or [])
        primary_bill_id = bill_ids[0] if bill_ids else ""
        bill = order.get_bill_by_id(primary_bill_id) if primary_bill_id else None
        bill_number = bill.bill_number if bill else ""
        bill_labels = []
        for bid in bill_ids:
            item = order.get_item_by_id(bid) if hasattr(order, "get_item_by_id") else None
            if item is None:
                item = order.get_bill_by_id(bid)
            if item:
                bill_labels.append(item.bill_number)
            else:
                bill_labels.append(bid)
        notes = f"Delivery {delivery.id}"
        if bill_labels:
            notes = f"{notes}: {', '.join(bill_labels)}"
        if delivery.delivery_notes:
            notes = f"{notes}. {delivery.delivery_notes}"
        existing = next(
            (
                e
                for e in self._repo.find_by_order(order.id)
                if e.task_type == TaskType.DELIVERY
                and e.activity_id == f"delivery:{delivery.id}"
            ),
            None,
        )
        if existing:
            existing.work_date = delivery.delivery_date
            existing.bill_id = primary_bill_id
            existing.bill_number = bill_number
            existing.notes = notes
            existing.updated_at = utc_now()
            return self._repo.save(existing)
        return self.create_time_entry(
            order_id=order.id,
            order_number=order.order_number,
            bill_id=primary_bill_id,
            bill_number=bill_number,
            activity_id=f"delivery:{delivery.id}",
            activity_name=DELIVERY_ACTIVITY_NAME,
            work_date=delivery.delivery_date,
            start_time="",
            end_time="",
            duration_minutes=0,
            task_type=TaskType.DELIVERY,
            notes=notes,
        )

    def get_total_minutes(
        self,
        entries: List[TimeEntry],
        activity_name: Optional[str] = None,
        bill_number: Optional[str] = None,
    ) -> int:
        filtered = [e for e in entries if e.task_type == TaskType.ACTIVITY]
        if activity_name:
            filtered = [e for e in filtered if e.activity_name == activity_name]
        if bill_number:
            filtered = [e for e in filtered if e.bill_number == bill_number]
        return sum(e.duration_minutes for e in filtered)

    def get_summary(self, entries: List[TimeEntry]) -> dict:
        activity_entries = [e for e in entries if e.task_type == TaskType.ACTIVITY]
        stitching = self.get_total_minutes(activity_entries, activity_name="Stitching")
        hand_work = self.get_total_minutes(activity_entries, activity_name="Handwork")
        by_bill: dict = {}
        by_activity: dict = {}
        for entry in activity_entries:
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

    def list_for_calendar(
        self,
        start_date: date,
        end_date: date,
        task_type: Optional[Union[TaskType, str]] = None,
        worker_name: Optional[str] = None,
        activity_name: Optional[str] = None,
    ) -> List[TimeEntry]:
        entries = self._repo.search(
            work_date_from=start_date, work_date_to=end_date
        )
        if task_type and task_type != "all":
            resolved = (
                task_type
                if isinstance(task_type, TaskType)
                else TaskType(str(task_type))
            )
            entries = [e for e in entries if e.task_type == resolved]
        if activity_name:
            needle = activity_name.strip().lower()
            entries = [
                e
                for e in entries
                if e.task_type == TaskType.ACTIVITY
                and (e.activity_name or "").strip().lower() == needle
            ]
        if worker_name:
            needle = worker_name.strip().lower()
            entries = [
                e for e in entries if (e.worker_name or "").strip().lower() == needle
            ]
        return sorted(entries, key=lambda e: (e.work_date, e.activity_name))

