"""Access audit trail entity (logins, user/role/entitlement admin)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now

# Known audit actions (UI filter options).
ACCESS_AUDIT_ACTIONS = (
    "login",
    "login_failed",
    "logout",
    "user.create",
    "user.update",
    "user.activate",
    "user.deactivate",
    "user.password_reset",
    "role.create",
    "role.update",
    "role.delete",
    "plan.create",
    "plan.update",
    "plan.delete",
    "plan.set",
    "modules.set",
    "flag.toggle",
)


@dataclass
class AccessAuditEntry:
    action: str
    actor_id: str = ""
    actor_name: str = ""
    target_type: str = ""
    target_id: str = ""
    target_label: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
