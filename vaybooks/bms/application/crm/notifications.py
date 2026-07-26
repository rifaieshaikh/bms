"""CRM notifications application service."""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime, timedelta

from vaybooks.bms.domain.crm.entities import CrmNotification, CrmNotificationPreferences
from vaybooks.bms.domain.crm.enums import NotificationKind
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError


class CrmNotificationAppService:
    def __init__(
        self,
        notification_repo,
        preferences_repo=None,
        activity_repo=None,
        lead_repo=None,
        settings_repo=None,
    ):
        self._notifications = notification_repo
        self._preferences = preferences_repo
        self._activities = activity_repo
        self._leads = lead_repo
        self._settings = settings_repo

    def get_preferences(self, user_id: str) -> CrmNotificationPreferences:
        if not user_id:
            raise ValidationError("user_id is required")
        if self._preferences:
            existing = self._preferences.find_by_user_id(user_id)
            if existing:
                return existing
            prefs = CrmNotificationPreferences(user_id=user_id)
            return self._preferences.save(prefs)
        return CrmNotificationPreferences(user_id=user_id)

    def update_preferences(
        self, user_id: str, **updates
    ) -> CrmNotificationPreferences:
        prefs = self.get_preferences(user_id)
        for key, value in updates.items():
            if hasattr(prefs, key) and value is not None:
                setattr(prefs, key, value)
        prefs.updated_at = utc_now()
        if self._preferences:
            return self._preferences.save(prefs)
        return prefs

    def create(
        self,
        *,
        recipient_id: str,
        kind: str | NotificationKind,
        title: str,
        message: str = "",
        ref_type: str = "",
        ref_id: str = "",
        state: str = "open",
        branch: str = "",
    ) -> CrmNotification:
        kind_val = kind.value if isinstance(kind, NotificationKind) else str(kind)
        dedupe = CrmNotification.build_dedupe_key(
            recipient_id, kind_val, ref_type, ref_id, state
        )
        existing = self._notifications.find_by_dedupe_key(dedupe)
        if existing:
            return existing
        notification = CrmNotification(
            recipient_id=recipient_id,
            kind=kind_val,
            title=title,
            message=message,
            ref_type=ref_type,
            ref_id=ref_id,
            state=state,
            dedupe_key=dedupe,
            branch=branch,
        )
        return self._notifications.save(notification)

    def list_for_user(
        self, user_id: str, *, unread_only: bool = False, limit: int = 100
    ) -> List[CrmNotification]:
        return self._notifications.list_for_recipient(
            user_id, unread_only=unread_only, limit=limit
        )

    def mark_read(self, notification_id: str) -> Optional[CrmNotification]:
        finder = getattr(self._notifications, "find_by_id", None)
        notification = finder(notification_id) if callable(finder) else None
        if notification is None:
            return None
        notification.read_at = utc_now()
        notification.state = "read"
        return self._notifications.save(notification)

    def generate_due_notifications(
        self,
        *,
        as_of: Optional[datetime] = None,
        recipient_id: str = "",
        branch: str = "",
    ) -> List[CrmNotification]:
        """Create deduplicated notifications for due CRM work."""
        now = as_of or utc_now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        created: List[CrmNotification] = []
        if self._activities:
            activities = self._activities.list(
                assigned_user_id=recipient_id or None,
                branch=branch or None,
                limit=5000,
            )
            for activity in activities:
                if activity.status not in {"Scheduled", "In Progress"}:
                    continue
                recipient = activity.assigned_user_id
                if not recipient:
                    continue
                prefs = self.get_preferences(recipient)
                kind = None
                title = ""
                due = activity.scheduled_at
                if due and due < day_start and prefs.overdue_follow_ups:
                    kind = NotificationKind.OVERDUE_FOLLOW_UP
                    title = "CRM follow-up overdue"
                elif (
                    due
                    and day_start <= due < day_end
                    and prefs.activity_due_today
                ):
                    kind = NotificationKind.ACTIVITY_DUE_TODAY
                    title = "CRM activity due today"
                elif (
                    due
                    and "visit" in (activity.activity_type or "").lower()
                    and day_end <= due <= day_end + timedelta(days=7)
                    and prefs.upcoming_visits
                ):
                    kind = NotificationKind.UPCOMING_VISIT
                    title = "Upcoming customer visit"
                elif (
                    activity.promised_date
                    and day_start <= activity.promised_date <= day_end + timedelta(days=7)
                    and prefs.payment_promises
                ):
                    kind = NotificationKind.PAYMENT_PROMISE
                    title = "Upcoming payment promise"
                if kind is not None:
                    created.append(
                        self.create(
                            recipient_id=recipient,
                            kind=kind,
                            title=title,
                            message=activity.party_name or activity.activity_type,
                            ref_type="crm_activity",
                            ref_id=activity.id,
                            branch=activity.branch,
                        )
                    )

        if self._leads:
            inactivity_days = 7
            if self._settings:
                inactivity_days = min(
                    int(self._settings.get().default_inactivity_days or 7), 7
                )
            cutoff = now - timedelta(days=inactivity_days)
            leads = self._leads.list(
                assigned_user_id=recipient_id or None,
                branch=branch or None,
                limit=5000,
            )
            for lead in leads:
                if (
                    lead.priority not in {"High", "Urgent"}
                    or not lead.assigned_user_id
                    or lead.status in {"Converted", "Lost"}
                    or (lead.last_activity_at and lead.last_activity_at >= cutoff)
                ):
                    continue
                prefs = self.get_preferences(lead.assigned_user_id)
                if prefs.high_priority_idle:
                    created.append(
                        self.create(
                            recipient_id=lead.assigned_user_id,
                            kind=NotificationKind.HIGH_PRIORITY_IDLE,
                            title="High-priority lead needs attention",
                            message=lead.name,
                            ref_type="crm_lead",
                            ref_id=lead.id,
                            branch=lead.branch,
                        )
                    )
        return created
