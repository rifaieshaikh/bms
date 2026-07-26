"""CRM settings application service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from vaybooks.bms.domain.crm.entities import CrmAuditEntry, CrmSettings
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError


class CrmSettingsAppService:
    def __init__(self, settings_repo, audit_repo=None):
        self._settings = settings_repo
        self._audit = audit_repo

    def get_settings(self) -> CrmSettings:
        return self._settings.get()

    def update_settings(
        self,
        *,
        actor_id: str = "",
        actor_name: str = "",
        **updates: Any,
    ) -> CrmSettings:
        settings = self._settings.get()
        before = {
            "default_inactivity_days": settings.default_inactivity_days,
            "default_follow_up_days": settings.default_follow_up_days,
            "order_trigger_status": settings.order_trigger_status,
            "payment_trigger": settings.payment_trigger,
        }
        allowed = {
            "lead_sources",
            "lead_statuses",
            "enquiry_statuses",
            "activity_types",
            "activity_outcomes",
            "lost_reasons",
            "default_inactivity_days",
            "default_follow_up_days",
            "order_trigger_status",
            "payment_trigger",
            "business_display_name",
            "payment_reminder_template",
            "payment_reminder_due_offsets_days",
        }
        for key, value in updates.items():
            if key not in allowed:
                raise ValidationError(f"Unknown settings field: {key}")
            if value is not None:
                setattr(settings, key, value)
        settings.updated_by_id = actor_id
        settings.updated_by_name = actor_name
        settings.updated_at = utc_now()
        saved = self._settings.save(settings)
        if self._audit:
            self._audit.save(
                CrmAuditEntry(
                    entity_type="crm_settings",
                    entity_id=saved.id,
                    action="update_settings",
                    actor_id=actor_id,
                    actor_name=actor_name,
                    before=before,
                    after={
                        "default_inactivity_days": saved.default_inactivity_days,
                        "default_follow_up_days": saved.default_follow_up_days,
                        "order_trigger_status": saved.order_trigger_status,
                        "payment_trigger": saved.payment_trigger,
                    },
                )
            )
        return saved

    def active_labels(self, catalog: List[Dict[str, Any]]) -> List[str]:
        return [
            item.get("label", "")
            for item in catalog or []
            if item.get("active", True) and item.get("label")
        ]
