from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.store.activities.entities import (
    COMPLETED_STATUS,
    CREATED_STATUS,
)


@dataclass
class StoreTimeEntry:
    """A business task logged against a store activity for one employee.

    Unlike boutique time entries, business tasks are not tied to an
    order/bill — they carry a labour-cost snapshot (rate at recording time)
    instead, and can be moved through the activity's status flow.
    """

    activity_id: str
    activity_name: str
    worker_id: str
    worker_name: str
    work_date: date
    start_time: str
    end_time: str
    duration_minutes: int
    hourly_rate: float = 0.0
    labour_cost: float = 0.0
    location_id: str = ""
    location_name: str = ""
    notes: str = ""
    status: str = CREATED_STATUS
    completed_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def is_completed(self) -> bool:
        return self.status == COMPLETED_STATUS
