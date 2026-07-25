from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now

APPLIES_TO_CUSTOMER = "customer"
APPLIES_TO_VENDOR = "vendor"
VALID_APPLIES_TO = frozenset({APPLIES_TO_CUSTOMER, APPLIES_TO_VENDOR})


@dataclass
class PartySegment:
    name: str
    applies_to: List[str] = field(
        default_factory=lambda: [APPLIES_TO_CUSTOMER, APPLIES_TO_VENDOR]
    )
    is_active: bool = True
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()
