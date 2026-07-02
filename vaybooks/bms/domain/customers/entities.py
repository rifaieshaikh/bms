from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class Customer:
    customer_name: str
    phone_number: str
    id: str = field(default_factory=lambda: uuid4().hex)
    alternate_phone_number: Optional[str] = None
    address: str = ""
    notes: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()
