"""CRM schedulers: follow-ups, inactivity, visits, promises, and collections."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

from vaybooks.bms.application.schedulers.jobs._base import (
    BaseJob,
    Deps,
    Outcome,
    aging_bucket,
    business_date,
    cap,
    day_bucket,
    days_before,
    first_non_empty,
    fmt_money,
    money,
    month_bucket,
    resolve_recipient,
    today_bounds,
    week_bucket,
)
from vaybooks.bms.application.schedulers.protocol import JobContext, JobDefinition
from vaybooks.bms.domain.schedulers.entities import DOMAIN_CRM
from vaybooks.bms.domain.schedulers.schedule import FREQ_WEEKLY
from vaybooks.bms.domain.schedulers.time import business_date_of

TERMINAL_LEAD_STATUSES = ("Converted", "Lost", "Not Interested")
OPEN_ACTIVITY_STATUSES = ("Scheduled", "In Progress")


def _customer_assignee(deps: Deps, customer_id: str) -> str:
    repo = deps.repo("customers")
    if repo is None or not customer_id:
        return ""
    try:
        customer = repo.find_by_id(customer_id)
    except Exception:
        return ""
    return getattr(customer, "assigned_user_id", "") or ""


def _customer_name(deps: Deps, customer_id: str) -> str:
    repo = deps.repo("customers")
    if repo is None or not customer_id:
        return customer_id
    try:
        customer = repo.find_by_id(customer_id)
    except Exception:
        return customer_id
    return getattr(customer, "customer_name", "") or customer_id


class ActivityDueTodayJob(BaseJob):
    job_id = "crm.activity_due_today"
    domain = DOMAIN_CRM
    title = "Activities due today"

    def identify(self, ctx: JobContext) -> List[str]:
        start, end = today_bounds(ctx)
        return self.deps.queries.crm_activity_ids_scheduled_between(
            start, end, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("crm_activities")
        activity = repo.find_by_id(candidate_id) if repo else None
        if activity is None or activity.status not in OPEN_ACTIVITY_STATUSES:
            return None
        recipient = resolve_recipient(ctx, activity.assigned_user_id)
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="CRM activity due today",
            message=f"{activity.activity_type} for {activity.party_name or 'a contact'}",
            ref_type="crm_activity",
            ref_id=activity.id,
            metadata={"activity_id": activity.id},
        )


class FollowUpOverdueJob(BaseJob):
    """Overdue activities plus leads and enquiries with a lapsed follow-up date."""

    job_id = "crm.follow_up_overdue"
    domain = DOMAIN_CRM
    title = "Overdue follow-ups"

    def identify(self, ctx: JobContext) -> List[str]:
        start, _ = today_bounds(ctx)
        limit = cap(ctx)
        queries = self.deps.queries
        out = [
            f"activity|{i}"
            for i in queries.crm_activity_ids_overdue(start, limit=limit)
        ]
        out += [
            f"lead|{i}"
            for i in queries.crm_lead_ids_follow_up_due(ctx.now, limit=limit)
        ]
        return out[:limit]

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        kind, _, entity_id = candidate_id.partition("|")
        if kind == "activity":
            return self._activity_outcome(ctx, entity_id)
        return self._lead_outcome(ctx, entity_id)

    def _activity_outcome(self, ctx: JobContext, activity_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("crm_activities")
        activity = repo.find_by_id(activity_id) if repo else None
        if activity is None or activity.status not in OPEN_ACTIVITY_STATUSES:
            return None
        scheduled = activity.scheduled_at
        if scheduled is None or business_date_of(scheduled) >= business_date(ctx):
            return None
        recipient = resolve_recipient(ctx, activity.assigned_user_id)
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Follow-up overdue",
            message=f"{activity.activity_type} was due {day_bucket(scheduled)}",
            ref_type="crm_activity",
            ref_id=activity.id,
        )

    def _lead_outcome(self, ctx: JobContext, lead_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("crm_leads")
        lead = repo.find_by_id(lead_id) if repo else None
        if lead is None or lead.is_deleted or lead.status in TERMINAL_LEAD_STATUSES:
            return None
        follow_up = getattr(lead, "next_follow_up_at", None)
        if follow_up is None or follow_up >= ctx.now:
            return None
        recipient = resolve_recipient(ctx, lead.assigned_user_id)
        if not recipient:
            return None
        # The follow-up date is part of the reference so rescheduling produces a
        # fresh task instead of being suppressed by dedupe.
        ref_id = f"{lead.id}:{day_bucket(follow_up)}"
        return Outcome(
            recipient_id=recipient,
            title="Lead follow-up overdue",
            message=f"{lead.name} was due {day_bucket(follow_up)}",
            ref_type="crm_lead",
            ref_id=ref_id,
            activity_label="General Follow-up",
            activity_lead_id=lead.id,
            activity_source_id=ref_id,
        )


class UpcomingVisitsJob(BaseJob):
    job_id = "crm.upcoming_visits"
    domain = DOMAIN_CRM
    title = "Upcoming customer visits"

    def identify(self, ctx: JobContext) -> List[str]:
        start, _ = today_bounds(ctx)
        horizon = start + timedelta(days=max(1, int(ctx.config.warning_days or 7)))
        type_keys = ctx.option("visit_type_keys") or ["sales_representative_visit"]
        return self.deps.queries.crm_activity_ids_by_type_scheduled_between(
            type_keys, start, horizon, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("crm_activities")
        activity = repo.find_by_id(candidate_id) if repo else None
        if activity is None or activity.status not in OPEN_ACTIVITY_STATUSES:
            return None
        recipient = resolve_recipient(ctx, activity.assigned_user_id)
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Upcoming customer visit",
            message=(
                f"{activity.party_name or 'Customer'} visit on "
                f"{day_bucket(activity.scheduled_at)}"
            ),
            ref_type="crm_activity",
            ref_id=activity.id,
        )


class PaymentPromiseDueJob(BaseJob):
    job_id = "crm.payment_promise_due"
    domain = DOMAIN_CRM
    title = "Payment promise due"

    def identify(self, ctx: JobContext) -> List[str]:
        _, end = today_bounds(ctx)
        boundary = end + timedelta(days=max(0, int(ctx.config.warning_days)))
        return self.deps.queries.crm_activity_ids_promise_due(boundary, limit=cap(ctx))

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("crm_activities")
        activity = repo.find_by_id(candidate_id) if repo else None
        if activity is None or activity.status in ("Cancelled", "Reversed"):
            return None
        promised = getattr(activity, "promised_date", None)
        if promised is None:
            return None
        recipient = resolve_recipient(
            ctx,
            activity.assigned_user_id,
            _customer_assignee(self.deps, activity.customer_id),
        )
        if not recipient:
            return None
        overdue_days = (business_date(ctx) - business_date_of(promised)).days
        label = "overdue" if overdue_days > 0 else "due"
        outcome = Outcome(
            recipient_id=recipient,
            title=f"Payment promise {label}",
            message=(
                f"{activity.party_name or 'Customer'} promised "
                f"{fmt_money(getattr(activity, 'promised_amount', 0))} "
                f"by {day_bucket(promised)}"
            ),
            ref_type="crm_activity_promise",
            ref_id=f"{activity.id}:{day_bucket(promised)}",
        )
        if overdue_days > max(0, int(ctx.config.grace_days or 1)):
            outcome.activity_label = "Contacted for Credit"
            outcome.activity_customer_id = activity.customer_id
            outcome.activity_source_id = outcome.ref_id
        return outcome


class HighPriorityLeadIdleJob(BaseJob):
    job_id = "crm.high_priority_lead_idle"
    domain = DOMAIN_CRM
    title = "High-priority idle lead"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = days_before(ctx, ctx.config.threshold_days or 7)
        priorities = ctx.option("priorities") or ["High", "Urgent"]
        return self.deps.queries.crm_lead_ids_high_priority_idle(
            priorities, boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("crm_leads")
        lead = repo.find_by_id(candidate_id) if repo else None
        if lead is None or lead.is_deleted or lead.status in TERMINAL_LEAD_STATUSES:
            return None
        recipient = resolve_recipient(ctx, lead.assigned_user_id)
        if not recipient:
            return None
        # Bucketed by week so an idle lead nudges again next week.
        ref_id = f"{lead.id}:{week_bucket(business_date(ctx))}"
        return Outcome(
            recipient_id=recipient,
            title="High-priority lead has gone quiet",
            message=f"{lead.name} has had no activity recently",
            ref_type="crm_lead",
            ref_id=ref_id,
            activity_label="General Follow-up",
            activity_lead_id=lead.id,
            activity_source_id=ref_id,
        )


class CustomerInactiveJob(BaseJob):
    job_id = "crm.customer_inactive"
    domain = DOMAIN_CRM
    title = "Customer inactivity"

    def identify(self, ctx: JobContext) -> List[str]:
        since = days_before(ctx, ctx.config.threshold_days or 30)
        return self.deps.queries.crm_customer_ids_without_activity_since(
            since, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        recipient = resolve_recipient(
            ctx, _customer_assignee(self.deps, candidate_id)
        )
        if not recipient:
            return None
        ref_id = f"{candidate_id}:{week_bucket(business_date(ctx))}"
        return Outcome(
            recipient_id=recipient,
            title="Customer has been inactive",
            message=(
                f"No contact with {_customer_name(self.deps, candidate_id)} in "
                f"{ctx.config.threshold_days or 30} days"
            ),
            ref_type="customer",
            ref_id=ref_id,
            activity_label=str(ctx.option("activity_label") or "General Follow-up"),
            activity_customer_id=candidate_id,
            activity_source_id=ref_id,
        )


class CustomerNotVisitedJob(BaseJob):
    job_id = "crm.customer_not_visited"
    domain = DOMAIN_CRM
    title = "Customer not visited"

    def identify(self, ctx: JobContext) -> List[str]:
        since = days_before(ctx, ctx.config.threshold_days or 14)
        type_keys = ctx.option("visit_type_keys") or ["sales_representative_visit"]
        return self.deps.queries.crm_customer_ids_without_visit_since(
            type_keys, since, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        recipient = resolve_recipient(
            ctx, _customer_assignee(self.deps, candidate_id)
        )
        if not recipient:
            return None
        ref_id = f"{candidate_id}:{month_bucket(business_date(ctx))}"
        return Outcome(
            recipient_id=recipient,
            title="Customer visit is due",
            message=f"{_customer_name(self.deps, candidate_id)} has not been visited recently",
            ref_type="customer",
            ref_id=ref_id,
            activity_label="Sales Representative Visit",
            activity_customer_id=candidate_id,
            activity_source_id=ref_id,
        )


class LeadUnassignedJob(BaseJob):
    job_id = "crm.lead_unassigned"
    domain = DOMAIN_CRM
    title = "Unassigned lead aging"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = days_before(ctx, ctx.config.threshold_days or 1)
        return self.deps.queries.crm_lead_ids_unassigned(boundary, limit=cap(ctx))

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("crm_leads")
        lead = repo.find_by_id(candidate_id) if repo else None
        if lead is None or lead.is_deleted or lead.assigned_user_id:
            return None
        # Never auto-assign: a manager is notified and decides.
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Lead is still unassigned",
            message=f"{lead.name} has had no owner since {day_bucket(lead.created_at)}",
            ref_type="crm_lead",
            ref_id=lead.id,
        )


class EnquiryStaleJob(BaseJob):
    job_id = "crm.enquiry_stale"
    domain = DOMAIN_CRM
    title = "Stale open enquiry"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = days_before(ctx, ctx.config.threshold_days or 7)
        return self.deps.queries.crm_enquiry_ids_stale(boundary, limit=cap(ctx))

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("crm_enquiries")
        enquiry = repo.find_by_id(candidate_id) if repo else None
        if enquiry is None or getattr(enquiry, "is_deleted", False):
            return None
        recipient = resolve_recipient(ctx, getattr(enquiry, "assigned_user_id", ""))
        if not recipient:
            return None
        moved_at = getattr(enquiry, "updated_at", None)
        ref_id = f"{enquiry.id}:{day_bucket(moved_at)}"
        return Outcome(
            recipient_id=recipient,
            title="Enquiry has not moved",
            message=f"No movement since {day_bucket(moved_at)}",
            ref_type="crm_enquiry",
            ref_id=ref_id,
            activity_label="General Follow-up",
            activity_enquiry_id=enquiry.id,
            activity_source_id=ref_id,
        )


class CollectionOutstandingIdleJob(BaseJob):
    job_id = "crm.collection_outstanding_idle"
    domain = DOMAIN_CRM
    title = "Outstanding with no collection activity"

    def identify(self, ctx: JobContext) -> List[str]:
        minimum = max(1.0, float(ctx.config.minimum_amount or 1.0))
        queries = self.deps.queries
        receivable = queries.receivable_customer_ids(minimum, limit=cap(ctx))
        if not receivable:
            return []
        since = days_before(ctx, ctx.config.threshold_days or 14)
        type_keys = ctx.option("collection_type_keys") or [
            "contacted_for_credit",
            "payment_reminder",
        ]
        contacted = set(
            queries.crm_customer_ids_with_recent_collection(type_keys, since)
        )
        return [cid for cid in receivable if cid not in contacted]

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        recipient = resolve_recipient(
            ctx, _customer_assignee(self.deps, candidate_id)
        )
        if not recipient:
            return None
        ref_id = f"{candidate_id}:{week_bucket(business_date(ctx))}"
        return Outcome(
            recipient_id=recipient,
            title="Collection follow-up needed",
            message=(
                f"{_customer_name(self.deps, candidate_id)} has an outstanding "
                "balance and no recent collection activity"
            ),
            ref_type="customer",
            ref_id=ref_id,
            activity_label="Contacted for Credit",
            activity_customer_id=candidate_id,
            activity_source_id=ref_id,
        )


class InvoicePaymentPendingJob(BaseJob):
    """Invoice-driven payment reminders rolled up per customer."""

    job_id = "crm.invoice_payment_pending"
    domain = DOMAIN_CRM
    title = "Aged open invoices"

    def identify(self, ctx: JobContext) -> List[str]:
        minimum = max(1.0, float(ctx.config.minimum_amount or 1.0))
        return self.deps.queries.receivable_customer_ids(minimum, limit=cap(ctx))

    def _open_invoices(self, customer_id: str) -> List[dict]:
        reminders = self.deps.service("crm_payment_reminders")
        if reminders is None:
            return []
        try:
            return list(reminders.open_invoices(customer_id) or [])
        except Exception:
            return []

    def _aged(self, ctx: JobContext, invoices: List[dict]) -> Tuple[List[dict], int]:
        grace = max(0, int(ctx.config.grace_days))
        threshold = max(0, int(ctx.config.threshold_days or 7))
        today = business_date(ctx)
        aged: List[dict] = []
        oldest_age = 0
        for invoice in invoices:
            invoice_date = invoice.get("invoice_date")
            due = business_date_of(invoice_date) if invoice_date else None
            if due is None:
                continue
            age = (today - due).days - grace
            if age >= threshold:
                aged.append(invoice)
                oldest_age = max(oldest_age, age)
        return aged, oldest_age

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        invoices = self._open_invoices(candidate_id)
        aged, oldest_age = self._aged(ctx, invoices)
        if not aged:
            return None
        total = sum(money(i.get("outstanding")) for i in aged)
        if total < max(1.0, float(ctx.config.minimum_amount or 1.0)):
            return None
        oldest = min(aged, key=lambda i: i.get("invoice_date") or business_date(ctx))
        oldest_id = str(oldest.get("voucher_id") or oldest.get("reference") or "")
        refs = ", ".join(str(i.get("reference") or "") for i in aged[:5])
        recipient = resolve_recipient(
            ctx, _customer_assignee(self.deps, candidate_id)
        )
        if not recipient:
            return None
        ref_id = f"{candidate_id}:{aging_bucket(oldest_age)}:{oldest_id}"
        return Outcome(
            recipient_id=recipient,
            title="Invoice payment pending",
            message=(
                f"{_customer_name(self.deps, candidate_id)} has {len(aged)} open "
                f"invoice(s) totalling {fmt_money(total)}. Oldest "
                f"{day_bucket(oldest.get('invoice_date'))}. Refs: {refs}"
            ),
            ref_type="customer_invoice_aging",
            ref_id=ref_id,
            metadata={"total": total, "count": len(aged)},
            activity_label="Payment Reminder",
            activity_customer_id=candidate_id,
            activity_source_id=ref_id,
        )


class PaymentReminderOffsetsJob(BaseJob):
    """Prepare-only reminder tasks at configured offsets; never sends anything."""

    job_id = "crm.payment_reminder_offsets"
    domain = DOMAIN_CRM
    title = "Payment reminder offsets"

    def identify(self, ctx: JobContext) -> List[str]:
        minimum = max(1.0, float(ctx.config.minimum_amount or 1.0))
        return self.deps.queries.receivable_customer_ids(minimum, limit=cap(ctx))

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        reminders = self.deps.service("crm_payment_reminders")
        if reminders is None:
            return None
        try:
            invoices = list(reminders.open_invoices(candidate_id) or [])
        except Exception:
            return None
        if not invoices:
            return None
        offsets = [int(o) for o in (ctx.config.reminder_offsets_days or [0, 3, 7])]
        grace = max(0, int(ctx.config.grace_days))
        today = business_date(ctx)
        oldest = min(
            invoices, key=lambda i: i.get("invoice_date") or today
        )
        due = business_date_of(oldest.get("invoice_date"))
        if due is None:
            return None
        age = (today - due).days - grace
        matched = [o for o in offsets if o == age]
        if not matched:
            return None
        offset = matched[0]
        recipient = resolve_recipient(
            ctx, _customer_assignee(self.deps, candidate_id)
        )
        if not recipient:
            return None
        oldest_id = str(oldest.get("voucher_id") or oldest.get("reference") or "")
        ref_id = f"{candidate_id}:{oldest_id}:{offset}"
        total = sum(money(i.get("outstanding")) for i in invoices)
        return Outcome(
            recipient_id=recipient,
            title="Prepare a payment reminder",
            message=(
                f"Day {offset} reminder for {_customer_name(self.deps, candidate_id)}: "
                f"{len(invoices)} invoice(s), {fmt_money(total)} outstanding"
            ),
            ref_type="customer_reminder_offset",
            ref_id=ref_id,
            metadata={"offset": offset, "total": total},
            activity_label="Payment Reminder",
            activity_customer_id=candidate_id,
            activity_source_id=ref_id,
        )


def crm_jobs(deps: Deps) -> List[Tuple[Any, JobDefinition]]:
    return [
        (
            ActivityDueTodayJob(deps),
            JobDefinition(
                job_id=ActivityDueTodayJob.job_id,
                domain=DOMAIN_CRM,
                title=ActivityDueTodayJob.title,
                description="Notify assignees about CRM activities scheduled for today.",
                create_activity=False,
            ),
        ),
        (
            FollowUpOverdueJob(deps),
            JobDefinition(
                job_id=FollowUpOverdueJob.job_id,
                domain=DOMAIN_CRM,
                title=FollowUpOverdueJob.title,
                description="Chase overdue activities and lapsed lead follow-ups.",
            ),
        ),
        (
            UpcomingVisitsJob(deps),
            JobDefinition(
                job_id=UpcomingVisitsJob.job_id,
                domain=DOMAIN_CRM,
                title=UpcomingVisitsJob.title,
                description="Warn about customer visits scheduled in the next few days.",
                warning_days=7,
                create_activity=False,
                options={"visit_type_keys": ["sales_representative_visit"]},
                rule_fields=["warning_days"],
            ),
        ),
        (
            PaymentPromiseDueJob(deps),
            JobDefinition(
                job_id=PaymentPromiseDueJob.job_id,
                domain=DOMAIN_CRM,
                title=PaymentPromiseDueJob.title,
                description="Track promised payments as they fall due or slip.",
                warning_days=0,
                grace_days=1,
                rule_fields=["warning_days", "grace_days"],
            ),
        ),
        (
            HighPriorityLeadIdleJob(deps),
            JobDefinition(
                job_id=HighPriorityLeadIdleJob.job_id,
                domain=DOMAIN_CRM,
                title=HighPriorityLeadIdleJob.title,
                description="Nudge owners of high-priority leads with no recent activity.",
                threshold_days=7,
                options={"priorities": ["High", "Urgent"]},
                rule_fields=["threshold_days"],
            ),
        ),
        (
            CustomerInactiveJob(deps),
            JobDefinition(
                job_id=CustomerInactiveJob.job_id,
                domain=DOMAIN_CRM,
                title=CustomerInactiveJob.title,
                description="Flag customers with no manual contact for a while.",
                frequency=FREQ_WEEKLY,
                threshold_days=30,
                options={"activity_label": "General Follow-up"},
                rule_fields=["threshold_days"],
            ),
        ),
        (
            CustomerNotVisitedJob(deps),
            JobDefinition(
                job_id=CustomerNotVisitedJob.job_id,
                domain=DOMAIN_CRM,
                title=CustomerNotVisitedJob.title,
                description="Schedule a visit for customers not seen recently.",
                frequency=FREQ_WEEKLY,
                threshold_days=14,
                options={"visit_type_keys": ["sales_representative_visit"]},
                rule_fields=["threshold_days"],
            ),
        ),
        (
            LeadUnassignedJob(deps),
            JobDefinition(
                job_id=LeadUnassignedJob.job_id,
                domain=DOMAIN_CRM,
                title=LeadUnassignedJob.title,
                description="Escalate leads that still have no owner.",
                threshold_days=1,
                create_activity=False,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            EnquiryStaleJob(deps),
            JobDefinition(
                job_id=EnquiryStaleJob.job_id,
                domain=DOMAIN_CRM,
                title=EnquiryStaleJob.title,
                description="Re-open enquiries that have stopped progressing.",
                threshold_days=7,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            CollectionOutstandingIdleJob(deps),
            JobDefinition(
                job_id=CollectionOutstandingIdleJob.job_id,
                domain=DOMAIN_CRM,
                title=CollectionOutstandingIdleJob.title,
                description="Chase receivables with no recent collection activity.",
                frequency=FREQ_WEEKLY,
                threshold_days=14,
                minimum_amount=1.0,
                rule_fields=["threshold_days", "minimum_amount"],
            ),
        ),
        (
            InvoicePaymentPendingJob(deps),
            JobDefinition(
                job_id=InvoicePaymentPendingJob.job_id,
                domain=DOMAIN_CRM,
                title=InvoicePaymentPendingJob.title,
                description="Roll aged open invoices into one reminder per customer.",
                threshold_days=7,
                grace_days=0,
                minimum_amount=1.0,
                rule_fields=["threshold_days", "grace_days", "minimum_amount"],
            ),
        ),
        (
            PaymentReminderOffsetsJob(deps),
            JobDefinition(
                job_id=PaymentReminderOffsetsJob.job_id,
                domain=DOMAIN_CRM,
                title=PaymentReminderOffsetsJob.title,
                description="Create prepare-only reminder tasks at day 0, 3, and 7.",
                reminder_offsets_days=[0, 3, 7],
                grace_days=0,
                minimum_amount=1.0,
                rule_fields=["reminder_offsets_days", "grace_days", "minimum_amount"],
            ),
        ),
    ]
