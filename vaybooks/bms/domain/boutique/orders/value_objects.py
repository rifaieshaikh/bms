from dataclasses import dataclass
from datetime import datetime

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class BillRegistryEntry:
    bill_number: str
    order_id: str
    bill_id: str
    id: str = ""
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = utc_now()
