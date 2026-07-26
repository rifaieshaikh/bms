from datetime import date
from typing import List, Optional, Protocol

from vaybooks.bms.domain.store.time_tracking.entities import StoreTimeEntry


class StoreTimeTrackingRepository(Protocol):
    def save(self, entry: StoreTimeEntry) -> StoreTimeEntry: ...

    def find_by_id(self, entry_id: str) -> Optional[StoreTimeEntry]: ...

    def list_all(self) -> List[StoreTimeEntry]: ...

    def search(
        self,
        worker_name: Optional[str] = None,
        activity_name: Optional[str] = None,
        location_id: Optional[str] = None,
        work_date_from: Optional[date] = None,
        work_date_to: Optional[date] = None,
    ) -> List[StoreTimeEntry]: ...

    def delete(self, entry_id: str) -> None: ...
