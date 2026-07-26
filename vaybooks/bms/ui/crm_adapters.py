"""Tolerant bridge between the CRM UI and the CRM application services.

The CRM services are wired into ``services`` by the bootstrap layer, which
lands separately from this UI. Every CRM call site therefore goes through
:class:`CrmAdapter`, which resolves the first registered service key that
exposes a matching method.

Reads return an empty result when nothing resolves, so pages render their
empty state; writes raise :class:`CrmUnavailable` so the caller can surface an
error instead of silently doing nothing.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Callable, Iterable, Optional, Sequence

_MISSING = object()


class CrmUnavailable(RuntimeError):
    """No CRM service (or no matching method) can satisfy the request."""


# Candidate ``services`` keys per group, most specific first. Only
# ``crm``-prefixed keys are probed: bare names such as ``activities`` and
# ``reports`` already belong to the boutique and finance services.
SERVICE_KEYS: dict[str, tuple[str, ...]] = {
    "leads": ("crm_leads", "crm_lead", "crm"),
    "enquiries": ("crm_enquiries", "crm_enquiry", "crm"),
    "activities": ("crm_activities", "crm_activity", "crm"),
    "dashboard": ("crm_dashboard", "crm"),
    "reports": ("crm_reports", "crm_report", "crm"),
    "settings": ("crm_settings", "crm_config", "crm"),
    "notifications": ("crm_notifications", "crm_notification", "crm"),
    "reminders": (
        "crm_payment_reminder",
        "crm_payment_reminders",
        "crm_reminders",
        "crm",
    ),
}

ALL_SERVICE_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys(key for keys in SERVICE_KEYS.values() for key in keys)
)


# --- record access -----------------------------------------------------------
def field(record: Any, *names: str, default: Any = None) -> Any:
    """Read the first present attribute / dict key from ``record``."""
    if record is None:
        return default
    for name in names:
        if isinstance(record, dict):
            value = record.get(name, _MISSING)
        else:
            value = getattr(record, name, _MISSING)
        if value is not _MISSING and value is not None:
            return value
    return default


def enum_value(value: Any) -> Any:
    """Return ``value.value`` for enums, otherwise ``value`` unchanged."""
    return value.value if isinstance(value, Enum) else value


def text(value: Any, default: str = "") -> str:
    value = enum_value(value)
    if value is None:
        return default
    return str(value).strip() or default


def as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def as_datetime(day: Optional[date], clock: Optional[time] = None) -> Optional[datetime]:
    if day is None:
        return None
    if isinstance(day, datetime):
        return day
    return datetime.combine(day, clock or time(9, 0))


def record_id(record: Any) -> str:
    return text(field(record, "id", "lead_id", "enquiry_id", "activity_id"))


def slug(value: str) -> str:
    """``"Lead Source ROI"`` -> ``"lead_source_roi"``."""
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


def crm_available(services: Optional[dict]) -> bool:
    """Whether at least one CRM service has been wired into ``services``."""
    if not services:
        return False
    return any(services.get(key) is not None for key in ALL_SERVICE_KEYS)


class CrmAdapter:
    """Name-tolerant facade over whichever CRM services are registered.

    ``actor_id`` / ``actor_name`` are attached to every write so audit entries
    and automatic activities carry the signed-in user.
    """

    def __init__(
        self,
        services: Optional[dict] = None,
        *,
        actor_id: str = "",
        actor_name: str = "",
    ):
        self._services: dict = services or {}
        self.actor_id = actor_id or ""
        self.actor_name = actor_name or ""

    # --- resolution ----------------------------------------------------------
    @property
    def services(self) -> dict:
        return self._services

    @property
    def available(self) -> bool:
        return crm_available(self._services)

    def service(self, group: str) -> Any:
        for key in SERVICE_KEYS.get(group, ()):
            service = self._services.get(key)
            if service is not None:
                return service
        return None

    def has(self, group: str) -> bool:
        return self.service(group) is not None

    def _resolve(self, group: str, names: Sequence[str]) -> Optional[Callable]:
        """First callable named in ``names`` on any candidate service."""
        for key in SERVICE_KEYS.get(group, ()):
            service = self._services.get(key)
            if service is None:
                continue
            for name in names:
                candidate = getattr(service, name, None)
                if callable(candidate):
                    return candidate
        return None

    def supports(self, group: str, *names: str) -> bool:
        return self._resolve(group, names) is not None

    def _call(
        self,
        group: str,
        names: Sequence[str],
        *args: Any,
        default: Any = _MISSING,
        **kwargs: Any,
    ) -> Any:
        method = self._resolve(group, names)
        if method is None:
            if default is not _MISSING:
                return default
            raise CrmUnavailable(
                f"CRM {group} service does not expose any of: {', '.join(names)}"
            )
        return method(*args, **kwargs)

    def _read(self, group: str, names: Sequence[str], *args: Any, **kwargs: Any) -> Any:
        """Query call whose failure degrades to ``None`` (empty state)."""
        try:
            return self._call(group, names, *args, default=None, **kwargs)
        except Exception:
            return None

    def _fetch(self, group: str, names: Sequence[str], record_id_: str) -> Any:
        """Read one record; missing ids surface as ``None``, not an exception."""
        if not record_id_:
            return None
        try:
            return self._call(group, names, record_id_, default=None)
        except Exception:
            return None

    def _actor(self) -> dict:
        return {"actor_id": self.actor_id, "actor_name": self.actor_name}

    def _can(self, permission: str) -> bool:
        authorization = self._services.get("crm_access") or self._services.get(
            "authorization"
        )
        users = self._services.get("users")
        if authorization is None or users is None or not self.actor_id:
            return True
        loader = getattr(users, "get_user", None)
        user = loader(self.actor_id) if callable(loader) else None
        checker = getattr(authorization, "can", None)
        return bool(checker(user, permission)) if callable(checker) else True

    def _require(self, permission: str) -> None:
        if not self._can(permission):
            raise CrmUnavailable(f"Permission required: {permission}")

    def can(self, permission: str) -> bool:
        return self._can(permission)

    def _scope_rows(self, rows: Iterable[Any]) -> list:
        values = list(rows or [])
        if self._can("crm.records.view_all") or self._can("crm.records.view_team"):
            return values
        if not self._can("crm.records.view_own"):
            return []
        return [
            row
            for row in values
            if text(field(row, "assigned_user_id", "created_by_id")) == self.actor_id
        ]

    def _scope_record(self, record: Any) -> Any:
        if record is None:
            return None
        return record if self._scope_rows([record]) else None

    def _own_scope_required(self) -> bool:
        return (
            self._can("crm.records.view_own")
            and not self._can("crm.records.view_team")
            and not self._can("crm.records.view_all")
        )

    @staticmethod
    def _clean(payload: dict) -> dict:
        return {k: v for k, v in payload.items() if v is not None}

    # --- leads ---------------------------------------------------------------
    def list_leads(self, **query: Any) -> list:
        rows = self._read("leads", ("list_leads", "list"), **self._clean(query))
        return self._scope_rows(rows or [])

    def get_lead(self, lead_id: str) -> Any:
        return self._scope_record(self._fetch("leads", ("get_lead",), lead_id))

    def create_lead(self, payload: dict) -> Any:
        self._require("crm.leads.create")
        return self._call(
            "leads", ("create_lead",), **self._clean(payload), **self._actor()
        )

    def update_lead(self, lead_id: str, payload: dict) -> Any:
        self._require("crm.leads.edit")
        return self._call(
            "leads", ("update_lead",), lead_id, **self._clean(payload), **self._actor()
        )

    def assign_lead(self, lead_id: str, user_id: str, user_name: str = "") -> Any:
        self._require("crm.leads.assign")
        return self._call(
            "leads", ("assign_lead",), lead_id, user_id, user_name, **self._actor()
        )

    def set_lead_status(self, lead_id: str, status: str, reason: str = "") -> Any:
        self._require("crm.leads.edit")
        return self._call(
            "leads",
            ("update_status", "set_lead_status"),
            lead_id,
            status,
            reason=reason,
            **self._actor(),
        )

    def mark_lead_lost(self, lead_id: str, lost_reason: str) -> Any:
        self._require("crm.leads.edit")
        return self._call("leads", ("mark_lost",), lead_id, lost_reason, **self._actor())

    def reopen_lead(self, lead_id: str, status: str = "") -> Any:
        self._require("crm.leads.edit")
        kwargs = dict(self._actor())
        if status:
            kwargs["status"] = status
        return self._call("leads", ("reopen_lead",), lead_id, **kwargs)

    def convert_lead(self, lead_id: str, *, force_new: bool = False) -> Any:
        self._require("crm.leads.convert")
        return self._call(
            "leads",
            ("convert_to_customer", "convert_lead"),
            lead_id,
            force_new=force_new,
            **self._actor(),
        )

    def link_lead_to_customer(self, lead_id: str, customer_id: str) -> Any:
        self._require("crm.leads.convert")
        return self._call(
            "leads", ("link_to_customer",), lead_id, customer_id, **self._actor()
        )

    def delete_lead(self, lead_id: str) -> Any:
        self._require("crm.leads.delete")
        return self._call(
            "leads", ("soft_delete_lead", "delete_lead"), lead_id, **self._actor()
        )

    def detect_lead_duplicates(
        self,
        *,
        phone: str = "",
        email: str = "",
        gstin: str = "",
        name: str = "",
        exclude_lead_id: str = "",
    ) -> Any:
        return self._call(
            "leads",
            ("detect_duplicates",),
            default=None,
            phone=phone,
            email=email,
            gstin=gstin,
            name=name,
            exclude_lead_id=exclude_lead_id,
        )

    def leads_for_customer(self, customer_id: str) -> list:
        if not customer_id:
            return []
        rows = self.list_leads(limit=1000)
        return [r for r in rows if text(field(r, "customer_id")) == text(customer_id)]

    # --- bulk lead actions ---------------------------------------------------
    def bulk_assign_leads(
        self, lead_ids: Iterable[str], user_id: str, user_name: str = ""
    ) -> tuple[int, int]:
        self._require("crm.leads.assign")
        ids = [text(i) for i in lead_ids if text(i)]
        batch = self._resolve("leads", ("bulk_assign",))
        if batch is not None and ids:
            batch(ids, user_id, user_name, **self._actor())
            return len(ids), 0
        return self._per_item(ids, lambda i: self.assign_lead(i, user_id, user_name))

    def bulk_set_lead_status(
        self, lead_ids: Iterable[str], status: str
    ) -> tuple[int, int]:
        self._require("crm.leads.edit")
        ids = [text(i) for i in lead_ids if text(i)]
        batch = self._resolve("leads", ("bulk_update_status",))
        if batch is not None and ids:
            batch(ids, status, **self._actor())
            return len(ids), 0
        return self._per_item(ids, lambda i: self.set_lead_status(i, status))

    @staticmethod
    def _per_item(ids: Sequence[str], action: Callable[[str], Any]) -> tuple[int, int]:
        """Apply ``action`` per id; return ``(succeeded, failed)``."""
        done = failed = 0
        for lead_id in ids:
            try:
                action(lead_id)
                done += 1
            except Exception:
                failed += 1
        return done, failed

    # --- enquiries -----------------------------------------------------------
    def list_enquiries(self, **query: Any) -> list:
        rows = self._read(
            "enquiries", ("list_enquiries", "list"), **self._clean(query)
        )
        return self._scope_rows(rows or [])

    def get_enquiry(self, enquiry_id: str) -> Any:
        return self._scope_record(
            self._fetch("enquiries", ("get_enquiry",), enquiry_id)
        )

    def create_enquiry(self, payload: dict) -> Any:
        self._require("crm.enquiries.create")
        return self._call(
            "enquiries", ("create_enquiry",), **self._clean(payload), **self._actor()
        )

    def update_enquiry(self, enquiry_id: str, payload: dict) -> Any:
        self._require("crm.enquiries.edit")
        return self._call(
            "enquiries",
            ("update_enquiry",),
            enquiry_id,
            **self._clean(payload),
            **self._actor(),
        )

    def assign_enquiry(self, enquiry_id: str, user_id: str, user_name: str = "") -> Any:
        self._require("crm.enquiries.assign")
        return self._call(
            "enquiries", ("assign_enquiry",), enquiry_id, user_id, user_name, **self._actor()
        )

    def set_enquiry_status(
        self, enquiry_id: str, status: str, lost_reason: str = ""
    ) -> Any:
        self._require("crm.enquiries.edit")
        return self._call(
            "enquiries",
            ("update_status", "set_enquiry_status"),
            enquiry_id,
            status,
            lost_reason=lost_reason,
            **self._actor(),
        )

    def close_enquiry(self, enquiry_id: str) -> Any:
        self._require("crm.enquiries.edit")
        return self._call("enquiries", ("close_enquiry",), enquiry_id, **self._actor())

    def reopen_enquiry(self, enquiry_id: str) -> Any:
        self._require("crm.enquiries.edit")
        return self._call("enquiries", ("reopen_enquiry",), enquiry_id, **self._actor())

    def enquiries_for(self, *, lead_id: str = "", customer_id: str = "") -> list:
        if not (lead_id or customer_id):
            return []
        rows = self.list_enquiries(limit=1000)
        return [
            row
            for row in rows
            if (lead_id and text(field(row, "lead_id")) == text(lead_id))
            or (customer_id and text(field(row, "customer_id")) == text(customer_id))
        ]

    # --- activities ----------------------------------------------------------
    def list_activities(self, **query: Any) -> list:
        rows = self._read(
            "activities", ("list_activities", "list"), **self._clean(query)
        )
        return self._scope_rows(rows or [])

    def get_activity(self, activity_id: str) -> Any:
        return self._scope_record(
            self._fetch("activities", ("get_activity",), activity_id)
        )

    def create_activity(self, payload: dict) -> Any:
        self._require("crm.activities.create")
        return self._call(
            "activities",
            ("create_manual", "create_activity"),
            **self._clean(payload),
            **self._actor(),
        )

    def update_activity(self, activity_id: str, payload: dict) -> Any:
        self._require("crm.activities.edit")
        allow_automatic = self._can("crm.corrections.auto_apply")
        return self._call(
            "activities",
            ("update_activity",),
            activity_id,
            **self._clean(payload),
            allow_automatic=allow_automatic,
            **self._actor(),
        )

    def complete_activity(
        self,
        activity_id: str,
        *,
        outcome: str = "",
        notes: str = "",
        next_action: str = "",
        next_follow_up_at: Optional[datetime] = None,
    ) -> Any:
        self._require("crm.activities.complete")
        return self._call(
            "activities",
            ("complete", "complete_activity"),
            activity_id,
            outcome=outcome,
            notes=notes,
            next_action=next_action,
            next_follow_up_at=next_follow_up_at,
            allow_automatic=self._can("crm.corrections.auto_apply"),
            **self._actor(),
        )

    def reschedule_activity(
        self, activity_id: str, scheduled_at: datetime, reason: str = ""
    ) -> Any:
        self._require("crm.activities.edit")
        return self._call(
            "activities",
            ("reschedule", "reschedule_activity"),
            activity_id,
            scheduled_at,
            reason=reason,
            allow_automatic=self._can("crm.corrections.auto_apply"),
            **self._actor(),
        )

    def cancel_activity(self, activity_id: str, reason: str = "") -> Any:
        self._require("crm.activities.edit")
        return self._call(
            "activities",
            ("cancel", "cancel_activity"),
            activity_id,
            reason=reason,
            allow_automatic=self._can("crm.corrections.auto_apply"),
            **self._actor(),
        )

    def timeline(
        self, *, lead_id: str = "", enquiry_id: str = "", customer_id: str = "", limit: int = 200
    ) -> list:
        rows = self._read(
            "activities",
            ("list_timeline",),
            lead_id=lead_id,
            enquiry_id=enquiry_id,
            customer_id=customer_id,
            limit=limit,
        )
        if rows is not None:
            return list(rows)
        # Fall back to a filtered activity list when no timeline query exists.
        rows = self.list_activities(limit=limit)
        return [
            row
            for row in rows
            if (lead_id and text(field(row, "lead_id")) == text(lead_id))
            or (enquiry_id and text(field(row, "enquiry_id")) == text(enquiry_id))
            or (customer_id and text(field(row, "customer_id")) == text(customer_id))
        ]

    # --- dashboard -----------------------------------------------------------
    def dashboard_snapshot(self, **query: Any) -> Any:
        if self._own_scope_required():
            query["assigned_user_id"] = self.actor_id
        return self._read("dashboard", ("snapshot",), **self._clean(query))

    # --- reports -------------------------------------------------------------
    def list_reports(self) -> list[dict]:
        rows = self._read("reports", ("list_reports",))
        if rows:
            return [dict(row) for row in rows]
        from vaybooks.bms.domain.crm.enums import CRM_REPORT_DEFINITIONS

        return [
            {"id": rid, "title": title, "category": category}
            for rid, title, category in CRM_REPORT_DEFINITIONS
        ]

    def run_report(self, report_id: str, filters: Any = None) -> Any:
        if self._own_scope_required():
            if filters is None:
                from vaybooks.bms.application.crm.reports import CrmReportFilters

                filters = CrmReportFilters(assigned_user_id=self.actor_id)
            elif isinstance(filters, dict):
                filters = {**filters, "assigned_user_id": self.actor_id}
            elif hasattr(filters, "assigned_user_id"):
                filters.assigned_user_id = self.actor_id
        return self._call("reports", ("run_report",), report_id, filters, default=None)

    # --- settings ------------------------------------------------------------
    def get_settings(self) -> Any:
        return self._read("settings", ("get_settings",))

    def update_settings(self, payload: dict) -> Any:
        self._require("crm.settings.edit")
        return self._call(
            "settings", ("update_settings", "save_settings"), **payload, **self._actor()
        )

    # --- notifications -------------------------------------------------------
    def get_notification_preferences(self, user_id: str) -> Any:
        if not user_id:
            return None
        return self._fetch("notifications", ("get_preferences",), user_id)

    def update_notification_preferences(self, user_id: str, payload: dict) -> Any:
        return self._call(
            "notifications", ("update_preferences",), user_id, **payload
        )

    def list_notifications(self, user_id: str, *, unread_only: bool = False) -> list:
        if not user_id:
            return []
        rows = self._read(
            "notifications", ("list_for_user",), user_id, unread_only=unread_only
        )
        return list(rows or [])

    # --- payment reminders ---------------------------------------------------
    def reminder_preview(
        self,
        customer_id: str,
        *,
        phone: str = "",
        outstanding_amount: Optional[float] = None,
        message_override: str = "",
    ) -> Any:
        return self._call(
            "reminders",
            ("preview",),
            customer_id,
            phone=phone,
            outstanding_amount=outstanding_amount,
            message_override=message_override,
        )

    def record_reminder_opened(self, preview: Any, *, lead_id: str = "") -> Any:
        self._require("crm.reminders.whatsapp.send")
        return self._call(
            "reminders",
            ("record_opened",),
            preview,
            default=None,
            lead_id=lead_id,
            **self._actor(),
        )

    def schedule_reminder_tasks(self, payload: dict) -> list:
        self._require("crm.payment_followups.create")
        rows = self._call(
            "reminders",
            ("schedule_reminder_tasks",),
            default=None,
            **self._clean(payload),
            **self._actor(),
        )
        return list(rows or [])

    # --- option sources ------------------------------------------------------
    def owners(self) -> list[tuple[str, str]]:
        """``(user_id, label)`` pairs for assignment dropdowns."""
        users = self._services.get("users") or self._services.get("identity")
        rows: list = []
        if users is not None:
            for name in ("list_users", "list_active_users", "list_all_users"):
                loader = getattr(users, name, None)
                if callable(loader):
                    try:
                        rows = list(loader() or [])
                    except Exception:
                        rows = []
                    break
        options: list[tuple[str, str]] = []
        for row in rows:
            user_id = text(field(row, "id", "user_id"))
            label = text(
                field(row, "display_name", "name", "username"), default=user_id
            )
            if user_id:
                options.append((user_id, label))
        return options

    def owner_name(self, user_id: str) -> str:
        for candidate_id, label in self.owners():
            if candidate_id == user_id:
                return label
        return user_id


def adapter(
    services: Optional[dict], *, actor_id: str = "", actor_name: str = ""
) -> CrmAdapter:
    return CrmAdapter(services, actor_id=actor_id, actor_name=actor_name)
