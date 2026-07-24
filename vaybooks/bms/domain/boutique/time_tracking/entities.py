from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


class TaskType(str, Enum):
    ACTIVITY = "activity"
    ETD = "etd"
    DELIVERY = "delivery"


ETD_ACTIVITY_ID = "system:etd"
ETD_ACTIVITY_NAME = "ETD"
DELIVERY_ACTIVITY_NAME = "Delivery"


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
    task_type: TaskType = TaskType.ACTIVITY
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
