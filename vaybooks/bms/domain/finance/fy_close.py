"""Financial year close / carry-forward entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now

FY_MODE_BALANCES_ONLY = "balances_only"
FY_MODE_FULL_PENDING = "full_pending"
FY_MODES = (FY_MODE_BALANCES_ONLY, FY_MODE_FULL_PENDING)

FY_STATUS_SUCCESS = "success"
FY_STATUS_FAILED = "failed"

FY_CARRY_FORWARD_TAG = "FY_CARRY_FORWARD"
FY_OPENING_TAG = "FY_OPENING"
FY_CLEARING_ACCOUNT_NAME = "FY Carry Forward Clearing"


@dataclass
class FyCloseRecord:
    from_fy: str
    to_fy: str
    mode: str
    status: str = FY_STATUS_SUCCESS
    id: str = field(default_factory=lambda: uuid4().hex)
    closed_at: datetime = field(default_factory=utc_now)
    totals: Dict[str, Any] = field(default_factory=dict)
    backup_path: str = ""
    error: str = ""
    account_snapshots: List[Dict[str, Any]] = field(default_factory=list)
    pending_receivables: List[Dict[str, Any]] = field(default_factory=list)
    pending_payables: List[Dict[str, Any]] = field(default_factory=list)

    def key(self) -> str:
        return f"{self.from_fy}->{self.to_fy}"
