"""Entitlement domain entities: FeatureFlag, Plan, OrgEntitlement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_MODULES,
    ORG_ENTITLEMENT_ID,
    PLAN_ENTERPRISE,
)
from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class FeatureFlag:
    key: str
    enabled: bool = True
    description: str = ""
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class Plan:
    id: str
    name: str
    feature_keys: List[str] = field(default_factory=list)
    description: str = ""
    is_system: bool = False
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class OrgEntitlement:
    plan_id: str = PLAN_ENTERPRISE
    enabled_modules: List[str] = field(default_factory=lambda: list(ALL_MODULES))
    version: int = 1
    id: str = ORG_ENTITLEMENT_ID
    updated_at: datetime = field(default_factory=utc_now)

    def bump_version(self) -> None:
        self.version = int(self.version or 0) + 1
        self.updated_at = utc_now()
