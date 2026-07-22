from datetime import date
from typing import List, Optional, Protocol

from vaybooks.bms.domain.boutique.time_tracking.entities import TimeEntry


class TimeTrackingRepository(Protocol):
    def save(self, entry: TimeEntry) -> TimeEntry: ...

    def find_by_id(self, entry_id: str) -> Optional[TimeEntry]: ...

    def find_by_order(self, order_id: str) -> List[TimeEntry]: ...

    def find_by_order_and_activity(
        self, order_id: str, activity_id: str
    ) -> List[TimeEntry]: ...

    def find_by_bill_number(self, bill_number: str) -> List[TimeEntry]: ...

    def search(
        self,
        bill_number: Optional[str] = None,
        order_number: Optional[str] = None,
        worker_name: Optional[str] = None,
        activity_name: Optional[str] = None,
        work_date_from: Optional[date] = None,
        work_date_to: Optional[date] = None,
    ) -> List[TimeEntry]: ...

    def list_all(self) -> List[TimeEntry]: ...

    def delete(self, entry_id: str) -> None: ...
