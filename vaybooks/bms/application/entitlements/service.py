"""Feature flag, plan, and org entitlement application services."""

from __future__ import annotations

from typing import List, Optional

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    ALL_MODULES,
    PLAN_DEFINITIONS,
)
from vaybooks.bms.domain.entitlements.entities import FeatureFlag, OrgEntitlement, Plan
from vaybooks.bms.domain.shared.exceptions import ValidationError


def _safe_record(audit, action: str, **kwargs) -> None:
    if audit is None:
        return
    try:
        audit.record(action, **kwargs)
    except Exception:
        pass  # auditing must never break the operation


class FeatureFlagAppService:
    def __init__(self, flag_repo, authorization=None, audit=None):
        self._flag_repo = flag_repo
        self._auth = authorization
        self._audit = audit

    def list_flags(self) -> List[FeatureFlag]:
        return self._flag_repo.list_all()

    def set_enabled(self, key: str, enabled: bool) -> FeatureFlag:
        flag = self._flag_repo.find_by_key(key)
        if flag is None:
            flag = FeatureFlag(key=key, enabled=enabled, description=key)
        else:
            flag.enabled = bool(enabled)
        saved = self._flag_repo.save(flag)
        if self._auth:
            self._auth.bump_org_version()
        _safe_record(
            self._audit,
            "flag.toggle",
            target_type="feature_flag",
            target_id=key,
            target_label=key,
            detail={"enabled": bool(enabled)},
        )
        return saved


class PlanAppService:
    def __init__(self, plan_repo, org_repo, authorization=None, audit=None):
        self._plan_repo = plan_repo
        self._org_repo = org_repo
        self._auth = authorization
        self._audit = audit

    def list_plans(self) -> List[Plan]:
        plans = self._plan_repo.list_all()
        known = {p.id for p in plans}
        # Catalog plans stay visible even before/without a seed migration.
        plans.extend(
            self._catalog_plan(pid) for pid in PLAN_DEFINITIONS if pid not in known
        )
        plans.sort(key=lambda p: (not p.is_system, p.name.lower()))
        return plans

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        plan = self._plan_repo.find_by_id(plan_id)
        if plan is None and plan_id in PLAN_DEFINITIONS:
            return self._catalog_plan(plan_id)
        return plan

    @staticmethod
    def _catalog_plan(plan_id: str) -> Plan:
        meta = PLAN_DEFINITIONS[plan_id]
        return Plan(
            id=meta["id"],
            name=meta["name"],
            description=meta.get("description", ""),
            feature_keys=list(meta.get("feature_keys") or []),
            is_system=True,
        )

    def create_plan(
        self,
        *,
        name: str,
        feature_keys: Optional[List[str]] = None,
        description: str = "",
        clone_from_plan_id: str = "",
    ) -> Plan:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Plan name is required")
        existing = self.list_plans()
        if any(p.name.strip().lower() == name.lower() for p in existing):
            raise ValidationError(f"Plan name already exists: {name}")
        keys = list(feature_keys or [])
        if not keys and clone_from_plan_id:
            source = self.get_plan(clone_from_plan_id)
            if source:
                keys = list(source.feature_keys or [])
        keys = self._clean_keys(keys)
        plan = Plan(
            id=self._slug(name, {p.id for p in existing}),
            name=name,
            description=(description or "").strip(),
            feature_keys=keys,
            is_system=False,
        )
        saved = self._plan_repo.save(plan)
        _safe_record(
            self._audit,
            "plan.create",
            target_type="plan",
            target_id=saved.id,
            target_label=saved.name,
            detail={"features": len(keys)},
        )
        return saved

    def update_plan(
        self,
        plan_id: str,
        *,
        name: Optional[str] = None,
        feature_keys: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> Plan:
        plan = self.get_plan(plan_id)
        if plan is None:
            raise ValidationError("Plan not found")
        if plan.is_system:
            raise ValidationError("Built-in plans cannot be modified")
        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationError("Plan name is required")
            clash = any(
                p.id != plan.id and p.name.strip().lower() == name.lower()
                for p in self.list_plans()
            )
            if clash:
                raise ValidationError(f"Plan name already exists: {name}")
            plan.name = name
        if description is not None:
            plan.description = description.strip()
        if feature_keys is not None:
            plan.feature_keys = self._clean_keys(list(feature_keys))
        saved = self._plan_repo.save(plan)
        if self._auth and self.get_org_entitlement().plan_id == plan.id:
            self._auth.bump_org_version()
        _safe_record(
            self._audit,
            "plan.update",
            target_type="plan",
            target_id=saved.id,
            target_label=saved.name,
            detail={"features": len(saved.feature_keys)},
        )
        return saved

    def delete_plan(self, plan_id: str) -> None:
        plan = self.get_plan(plan_id)
        if plan is None:
            raise ValidationError("Plan not found")
        if plan.is_system:
            raise ValidationError("Built-in plans cannot be deleted")
        if self.get_org_entitlement().plan_id == plan.id:
            raise ValidationError(
                "This plan is currently active. Switch to another plan before deleting it."
            )
        self._plan_repo.delete(plan.id)
        _safe_record(
            self._audit,
            "plan.delete",
            target_type="plan",
            target_id=plan.id,
            target_label=plan.name,
        )

    @staticmethod
    def _clean_keys(keys: List[str]) -> List[str]:
        cleaned = {(k or "").strip() for k in keys}
        cleaned.discard("")
        unknown = cleaned - set(ALL_FEATURE_KEYS)
        if unknown:
            raise ValidationError(
                "Unknown feature keys: " + ", ".join(sorted(unknown)[:8])
            )
        if not cleaned:
            raise ValidationError("A plan must include at least one feature")
        return sorted(cleaned)

    @staticmethod
    def _slug(name: str, taken: set) -> str:
        base = "".join(c if c.isalnum() else "_" for c in name.strip().lower())
        base = "_".join(part for part in base.split("_") if part) or "plan"
        candidate, suffix = base, 2
        while candidate in taken:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def get_org_entitlement(self) -> OrgEntitlement:
        ent = self._org_repo.get()
        return ent or OrgEntitlement()

    def set_plan(self, plan_id: str) -> OrgEntitlement:
        plan = self._plan_repo.find_by_id(plan_id)
        if plan is None and plan_id not in PLAN_DEFINITIONS:
            raise ValidationError(f"Unknown plan: {plan_id}")
        ent = self.get_org_entitlement()
        ent.plan_id = plan_id
        ent.bump_version()
        saved = self._org_repo.save(ent)
        _safe_record(
            self._audit,
            "plan.set",
            target_type="plan",
            target_id=plan_id,
            target_label=plan_id,
        )
        return saved

    def set_enabled_modules(self, modules: List[str]) -> OrgEntitlement:
        cleaned = []
        for m in modules or []:
            m = (m or "").strip()
            if m in ALL_MODULES and m not in cleaned:
                cleaned.append(m)
        if not cleaned:
            raise ValidationError("At least one module must be enabled")
        # core + settings should stay available for admin
        for required in ("core", "settings"):
            if required not in cleaned:
                cleaned.insert(0, required)
        ent = self.get_org_entitlement()
        ent.enabled_modules = cleaned
        ent.bump_version()
        saved = self._org_repo.save(ent)
        _safe_record(
            self._audit,
            "modules.set",
            target_type="org_entitlement",
            target_id=saved.id,
            target_label="enabled_modules",
            detail={"modules": cleaned},
        )
        return saved
