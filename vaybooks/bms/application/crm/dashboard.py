"""CRM dashboard KPI queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from vaybooks.bms.domain.crm.enums import ActivityStatus, EnquiryStatus, LeadStatus
from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class CrmDashboardSnapshot:
    total_active_leads: int = 0
    new_leads_in_period: int = 0
    unassigned_leads: int = 0
    open_enquiries: int = 0
    follow_ups_due_today: int = 0
    overdue_follow_ups: int = 0
    visits_scheduled_today: int = 0
    customers_contacted_in_period: int = 0
    customers_not_contacted_recently: int = 0
    leads_converted_in_period: int = 0
    orders_generated_from_crm_leads: int = 0
    payments_collected_after_followups: float = 0.0
    sales_representative_activity_summary: List[Dict[str, Any]] = field(
        default_factory=list
    )
    my_tasks_today: List[Any] = field(default_factory=list)
    upcoming_visits: List[Any] = field(default_factory=list)
    overdue_activities: List[Any] = field(default_factory=list)
    recently_added_leads: List[Any] = field(default_factory=list)
    leads_requiring_attention: List[Any] = field(default_factory=list)
    customers_with_outstanding_balances: List[Dict[str, Any]] = field(
        default_factory=list
    )
    recent_activity_timeline: List[Any] = field(default_factory=list)
    kpi_filters: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class CrmDashboardAppService:
    def __init__(
        self,
        lead_repo,
        enquiry_repo=None,
        activity_repo=None,
        customer_service=None,
        sales_service=None,
        accounting_service=None,
        settings_repo=None,
    ):
        self._leads = lead_repo
        self._enquiries = enquiry_repo
        self._activities = activity_repo
        self._customers = customer_service
        self._sales = sales_service
        self._accounting = accounting_service
        self._settings = settings_repo

    def snapshot(
        self,
        *,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        assigned_user_id: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> CrmDashboardSnapshot:
        now = utc_now()
        start = period_start or (now - timedelta(days=30))
        end = period_end or now
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        leads = self._leads.list(
            assigned_user_id=assigned_user_id, branch=branch, limit=2000
        )
        active_statuses = {
            LeadStatus.NEW.value,
            LeadStatus.CONTACTED.value,
            LeadStatus.QUALIFIED.value,
            LeadStatus.FOLLOW_UP_REQUIRED.value,
            LeadStatus.INTERESTED.value,
            LeadStatus.ON_HOLD.value,
        }
        snap = CrmDashboardSnapshot()
        snap.total_active_leads = sum(1 for l in leads if l.status in active_statuses)
        snap.new_leads_in_period = sum(
            1 for l in leads if l.created_at and start <= l.created_at <= end
        )
        snap.unassigned_leads = sum(1 for l in leads if not l.assigned_user_id)
        snap.leads_converted_in_period = sum(
            1
            for l in leads
            if l.status == LeadStatus.CONVERTED.value
            and l.converted_at
            and start <= l.converted_at <= end
        )
        snap.recently_added_leads = sorted(
            leads, key=lambda l: l.created_at or now, reverse=True
        )[:10]
        customer_rows = (
            self._customers.list_all_customers() if self._customers else []
        )
        if assigned_user_id:
            customer_rows = [
                customer
                for customer in customer_rows
                if getattr(customer, "assigned_user_id", "") == assigned_user_id
            ]
        if branch:
            customer_rows = [
                customer
                for customer in customer_rows
                if not getattr(customer, "branch", "")
                or getattr(customer, "branch", "") == branch
            ]
        snap.leads_requiring_attention = [
            lead
            for lead in leads
            if lead.status not in {LeadStatus.CONVERTED.value, LeadStatus.LOST.value}
            and (
                not lead.assigned_user_id
                or (lead.next_follow_up_at and lead.next_follow_up_at < now)
                or (
                    lead.priority in {"High", "Urgent"}
                    and not lead.last_activity_at
                )
            )
        ][:20]

        if self._enquiries:
            enquiries = self._enquiries.list(
                assigned_user_id=assigned_user_id, branch=branch, limit=2000
            )
            open_set = {
                EnquiryStatus.OPEN.value,
                EnquiryStatus.ASSIGNED.value,
                EnquiryStatus.IN_PROGRESS.value,
                EnquiryStatus.QUOTATION_REQUIRED.value,
                EnquiryStatus.QUOTATION_SENT.value,
                EnquiryStatus.NEGOTIATION.value,
                EnquiryStatus.ON_HOLD.value,
            }
            snap.open_enquiries = sum(1 for e in enquiries if e.status in open_set)

        if self._activities:
            activities = self._activities.list(
                assigned_user_id=assigned_user_id, branch=branch, limit=2000
            )
            open_act = {
                ActivityStatus.SCHEDULED.value,
                ActivityStatus.IN_PROGRESS.value,
            }
            snap.follow_ups_due_today = sum(
                1
                for a in activities
                if a.status in open_act
                and a.scheduled_at
                and today_start <= a.scheduled_at < today_end
            )
            snap.overdue_follow_ups = sum(
                1
                for a in activities
                if a.status in open_act and a.scheduled_at and a.scheduled_at < today_start
            )
            snap.visits_scheduled_today = sum(
                1
                for a in activities
                if a.status in open_act
                and "visit" in (a.activity_type or "").lower()
                and a.scheduled_at
                and today_start <= a.scheduled_at < today_end
            )
            contacted_customers = {
                a.customer_id
                for a in activities
                if a.customer_id
                and a.activity_at
                and start <= a.activity_at <= end
                and a.status == ActivityStatus.COMPLETED.value
            }
            snap.customers_contacted_in_period = len(contacted_customers)
            inactivity_days = 30
            if self._settings:
                inactivity_days = (
                    self._settings.get().default_inactivity_days or inactivity_days
                )
            cutoff = now - timedelta(days=inactivity_days)
            manual_last: Dict[str, datetime] = {}
            for activity in activities:
                if (
                    activity.customer_id
                    and activity.origin != "Automatic"
                    and activity.activity_at
                ):
                    previous = manual_last.get(activity.customer_id)
                    if previous is None or activity.activity_at > previous:
                        manual_last[activity.customer_id] = activity.activity_at
            customer_ids = {
                customer.id for customer in customer_rows
            }
            snap.customers_not_contacted_recently = sum(
                1
                for customer_id in customer_ids
                if customer_id not in manual_last
                or manual_last[customer_id] < cutoff
            )
            snap.my_tasks_today = [
                a
                for a in activities
                if a.status in open_act
                and a.scheduled_at
                and today_start <= a.scheduled_at < today_end
            ][:20]
            snap.upcoming_visits = [
                a
                for a in activities
                if a.status in open_act
                and "visit" in (a.activity_type or "").lower()
                and a.scheduled_at
                and a.scheduled_at >= today_start
            ][:20]
            snap.overdue_activities = [
                a
                for a in activities
                if a.status in open_act and a.scheduled_at and a.scheduled_at < today_start
            ][:20]
            snap.recent_activity_timeline = sorted(
                activities,
                key=lambda activity: activity.activity_at
                or activity.scheduled_at
                or activity.created_at,
                reverse=True,
            )[:30]
            by_rep: Dict[str, Dict[str, Any]] = {}
            for activity in activities:
                key = activity.assigned_user_id or "unassigned"
                row = by_rep.setdefault(
                    key,
                    {
                        "assigned_user_id": activity.assigned_user_id,
                        "assigned_user_name": activity.assigned_user_name
                        or "Unassigned",
                        "total": 0,
                        "completed": 0,
                        "overdue": 0,
                    },
                )
                row["total"] += 1
                if activity.status == ActivityStatus.COMPLETED.value:
                    row["completed"] += 1
                if (
                    activity.status in open_act
                    and activity.scheduled_at
                    and activity.scheduled_at < now
                ):
                    row["overdue"] += 1
            snap.sales_representative_activity_summary = list(by_rep.values())
            payment_activities = [
                activity
                for activity in activities
                if activity.activity_type == "Payment Received"
                and activity.customer_id
            ]
            credit_activities = [
                activity
                for activity in activities
                if activity.activity_type == "Contacted for Credit"
                and activity.customer_id
            ]
            for payment in payment_activities:
                if any(
                    credit.customer_id == payment.customer_id
                    and credit.activity_at
                    and payment.activity_at
                    and credit.activity_at < payment.activity_at
                    for credit in credit_activities
                ):
                    try:
                        amount = float(
                            (payment.notes or "")
                            .split("Amount:", 1)[1]
                            .split(";", 1)[0]
                            .strip()
                        )
                    except (IndexError, ValueError):
                        amount = 0.0
                    snap.payments_collected_after_followups += amount

        converted_customer_ids = {
            lead.customer_id for lead in leads if lead.customer_id
        }
        if self._sales:
            try:
                snap.orders_generated_from_crm_leads = sum(
                    1
                    for order in self._sales.list_sales_orders()
                    if order.customer_id in converted_customer_ids
                    and start.date() <= order.order_date <= end.date()
                )
            except Exception:
                pass
        if self._accounting:
            try:
                balances = self._accounting.customer_balances_by_customer()
                customer_names = {
                    customer.id: customer.customer_name
                    for customer in customer_rows
                }
                allowed_customer_ids = set(customer_names)
                snap.customers_with_outstanding_balances = sorted(
                    [
                        {
                            "customer_id": customer_id,
                            "customer_name": customer_names.get(customer_id, ""),
                            "outstanding_balance": float(balance or 0),
                        }
                        for customer_id, balance in balances.items()
                        if float(balance or 0) > 0
                        and (
                            not (assigned_user_id or branch)
                            or customer_id in allowed_customer_ids
                        )
                    ],
                    key=lambda row: row["outstanding_balance"],
                    reverse=True,
                )[:20]
            except Exception:
                pass

        snap.kpi_filters = {
            "total_active_leads": {"status_in": list(active_statuses)},
            "unassigned_leads": {"assigned_user_id": ""},
            "follow_ups_due_today": {"due": "today"},
            "overdue_follow_ups": {"due": "overdue"},
            "open_enquiries": {"open": True},
            "customers_not_contacted_recently": {"inactive": True},
            "orders_generated_from_crm_leads": {"from_crm_lead": True},
        }
        return snap
