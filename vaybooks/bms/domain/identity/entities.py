"""Identity domain entities: User and Role."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class Role:
    name: str
    permission_keys: List[str] = field(default_factory=list)
    description: str = ""
    is_system: bool = False
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


@dataclass
class User:
    username: str
    display_name: str = ""
    password_hash: str = ""
    role_ids: List[str] = field(default_factory=list)
    # Empty = unrestricted (all locations). Non-empty = only these location ids.
    location_ids: List[str] = field(default_factory=list)
    active: bool = True
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()
