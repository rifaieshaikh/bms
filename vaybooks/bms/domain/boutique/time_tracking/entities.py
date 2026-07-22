from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class TimeEntry:
    order_id: str
    order_number: str
    bill_id: str
    bill_number: str
    activity_id: str
    activity_name: str
    work_date: date
    start_time: str
    end_time: str
    duration_minutes: int
    worker_name: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
