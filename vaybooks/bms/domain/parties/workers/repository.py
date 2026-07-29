from typing import List, Optional, Protocol

from vaybooks.bms.domain.parties.workers.entities import (
    SOURCE_CUSTOMIZATION,
    Worker,
)


class WorkerRepository(Protocol):
    def save(self, worker: Worker) -> Worker: ...

    def find_by_id(self, worker_id: str) -> Optional[Worker]: ...

    def list_all(
        self,
        active_only: bool = True,
        location_filter: dict | None = None,
    ) -> List[Worker]: ...

    def list_by_activity(
        self,
        activity_id: str,
        source: str = SOURCE_CUSTOMIZATION,
        active_only: bool = True,
    ) -> List[Worker]: ...
