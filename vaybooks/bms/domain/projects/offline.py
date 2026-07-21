"""Offline site capture drafts and customer portal tokens (Wave 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class ProjectOfflineDraft:
    project_id: str
    section: str
    payload: Dict[str, Any] = field(default_factory=dict)
    device_id: str = ""
    synced: bool = False
    synced_at: Optional[datetime] = None
    created_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectPortalToken:
    project_id: str
    token: str
    scope: str = "quote"
    expires_at: Optional[datetime] = None
    revoked: bool = False
    label: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectNotification:
    user_id: str
    kind: str
    title: str
    project_id: str = ""
    ref_id: str = ""
    ref_type: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
