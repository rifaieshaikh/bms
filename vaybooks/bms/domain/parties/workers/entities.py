from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class Worker:
    worker_name: str
    activity_ids: List[str] = field(default_factory=list)
    is_active: bool = True
    default_hourly_rate: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(
        self,
        *,
        worker_name: str,
        activity_ids: List[str],
        is_active: bool,
        default_hourly_rate: float = 0.0,
    ) -> None:
        self.worker_name = (worker_name or "").strip()
        self.activity_ids = list(activity_ids or [])
        self.is_active = bool(is_active)
        self.default_hourly_rate = float(default_hourly_rate or 0.0)
        self.updated_at = utc_now()
