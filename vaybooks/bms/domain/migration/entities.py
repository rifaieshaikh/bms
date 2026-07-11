from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class ImportMappingProfile:
    name: str
    entity_type: str
    mapping: Dict[str, str]
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update_mapping(self, mapping: Dict[str, str]) -> None:
        self.mapping = dict(mapping)
        self.updated_at = utc_now()
