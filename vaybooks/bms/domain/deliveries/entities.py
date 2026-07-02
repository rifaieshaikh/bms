from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class Delivery:
    order_id: str
    order_number: str
    bill_ids: List[str]
    delivery_date: date
    delivery_notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
