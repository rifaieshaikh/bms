"""Sales schedulers: quotation/estimate expiry, order and delivery aging."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, List, Optional, Tuple

from vaybooks.bms.application.schedulers.jobs._base import (
    BaseJob,
    Deps,
    Outcome,
    aging_bucket,
    business_date,
    cap,
    day_bucket,
    fmt_money,
    money,
    resolve_recipient,
    week_bucket,
)
from vaybooks.bms.application.schedulers.protocol import JobContext, JobDefinition
from vaybooks.bms.domain.schedulers.entities import DOMAIN_SALES
from vaybooks.bms.domain.schedulers.schedule import FREQ_WEEKDAYS
from vaybooks.bms.infrastructure.db.bson_utils import as_date

_QUOTATION_OPEN = ("Sent", "Accepted")
_ESTIMATE_OPEN = ("Sent", "Accepted")
_ORDER_OPEN = ("Confirmed", "Partially Delivered")


def _status(value: Any) -> str:
    return getattr(value, "value", value) or ""


def _customer_assignee(deps: Deps, customer_id: str) -> str:
    repo = deps.repo("customers")
    if repo is None or not customer_id:
        return ""
    try:
        customer = repo.find_by_id(customer_id)
    except Exception:
        return ""
    return getattr(customer, "assigned_user_id", "") or ""


class _ExpiringDocumentJob(BaseJob):
    """Shared behaviour for quotations and estimates approaching validity end."""

    domain = DOMAIN_SALES
    collection = ""
    repo_key = ""
    open_statuses: Tuple[str, ...] = ()
    label = "Document"

    def identify(self, ctx: JobContext) -> List[str]:
        offsets = [int(o) for o in (ctx.config.reminder_offsets_days or [7, 3, 0])]
        horizon = business_date(ctx) + timedelta(days=max(offsets or [0]))
        return self.deps.queries.sales_document_ids_expiring(
            self.collection, self.open_statuses, horizon, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo(self.repo_key)
        doc = repo.find_by_id(candidate_id) if repo else None
        if doc is None or _status(doc.status) not in self.open_statuses:
            return None
        valid_until = as_date(getattr(doc, "valid_until", None))
        if valid_until is None:
            return None
        days_left = (valid_until - business_date(ctx)).days
        # Ascending, so the tightest offset already reached wins; each offset is a
        # distinct dedupe bucket, giving one reminder per configured milestone.
        offsets = sorted(int(o) for o in (ctx.config.reminder_offsets_days or [7, 3, 0]))
        matched = next((o for o in offsets if days_left <= o), None)
        if matched is None:
            return None
        recipient = resolve_recipient(
            ctx, _customer_assignee(self.deps, getattr(doc, "customer_id", ""))
        )
        if not recipient:
            return None
        state = "has expired" if days_left < 0 else f"expires in {days_left} day(s)"
        return Outcome(
            recipient_id=recipient,
            title=f"{self.label} {state}",
            message=(
                f"{getattr(doc, 'customer_name', '') or 'Customer'} — valid until "
                f"{valid_until.isoformat()}"
            ),
            ref_type=self.collection,
            ref_id=f"{candidate_id}:{valid_until.isoformat()}:{matched}",
            activity_label="General Follow-up",
            activity_customer_id=getattr(doc, "customer_id", "") or "",
            activity_source_id=f"{candidate_id}:{valid_until.isoformat()}:{matched}",
        )


class QuotationExpiringJob(_ExpiringDocumentJob):
    job_id = "sales.quotation_expiring"
    title = "Quotations expiring"
    collection = "quotations"
    repo_key = "quotations"
    open_statuses = _QUOTATION_OPEN
    label = "Quotation"


class EstimateExpiringJob(_ExpiringDocumentJob):
    job_id = "sales.estimate_expiring"
    title = "Estimates expiring"
    collection = "estimates"
    repo_key = "estimates"
    open_statuses = _ESTIMATE_OPEN
    label = "Estimate"


class OrderOverdueJob(BaseJob):
    job_id = "sales.order_overdue"
    domain = DOMAIN_SALES
    title = "Expected delivery overdue"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = business_date(ctx) - timedelta(days=max(0, int(ctx.config.grace_days)))
        return self.deps.queries.sales_order_ids_overdue(
            _ORDER_OPEN, boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("sales_orders")
        order = repo.find_by_id(candidate_id) if repo else None
        if order is None or _status(order.status) not in _ORDER_OPEN:
            return None
        expected = as_date(getattr(order, "expected_date", None))
        if expected is None or expected >= business_date(ctx):
            return None
        pending = sum(
            max(0.0, money(getattr(line, "qty", 0)) - money(getattr(line, "qty_delivered", 0)))
            for line in getattr(order, "lines", []) or []
        )
        if pending <= 0:
            return None
        customer_id = getattr(order, "customer_id", "") or ""
        recipient = resolve_recipient(ctx, _customer_assignee(self.deps, customer_id))
        if not recipient:
            return None
        ref_id = f"{candidate_id}:{expected.isoformat()}"
        return Outcome(
            recipient_id=recipient,
            title="Sales order overdue",
            message=(
                f"{getattr(order, 'order_number', candidate_id)} was due "
                f"{expected.isoformat()} with {pending:g} pending"
            ),
            ref_type="sales_order",
            ref_id=ref_id,
            activity_label="Contacted for Order",
            activity_customer_id=customer_id,
            activity_source_id=ref_id,
        )


class OrderNoProgressJob(BaseJob):
    job_id = "sales.order_no_progress"
    domain = DOMAIN_SALES
    title = "Confirmed order without delivery progress"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = business_date(ctx) - timedelta(days=max(1, int(ctx.config.threshold_days or 7)))
        return self.deps.queries.sales_order_ids_without_progress(
            ("Confirmed",), boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("sales_orders")
        order = repo.find_by_id(candidate_id) if repo else None
        if order is None or _status(order.status) != "Confirmed":
            return None
        delivered = sum(
            money(getattr(line, "qty_delivered", 0))
            for line in getattr(order, "lines", []) or []
        )
        if delivered > 0:
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Confirmed order has no delivery progress",
            message=f"{getattr(order, 'order_number', candidate_id)} has not started dispatch",
            ref_type="sales_order",
            ref_id=f"{candidate_id}:{week_bucket(business_date(ctx))}",
        )


class DeliveryNoteStaleJob(BaseJob):
    job_id = "sales.delivery_note_stale"
    domain = DOMAIN_SALES
    title = "Draft delivery note aging"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = business_date(ctx) - timedelta(days=max(1, int(ctx.config.threshold_days or 3)))
        return self.deps.queries.sales_document_ids_by_status_before(
            "delivery_notes", ("Draft",), "delivery_date", boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("delivery_notes")
        note = repo.find_by_id(candidate_id) if repo else None
        if note is None or _status(note.status) != "Draft":
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Draft delivery note is aging",
            message=(
                f"{getattr(note, 'dn_number', '') or candidate_id} is still a draft "
                f"from {day_bucket(as_date(getattr(note, 'delivery_date', None)))}"
            ),
            ref_type="delivery_note",
            ref_id=candidate_id,
        )


class ReturnPendingApprovalJob(BaseJob):
    job_id = "sales.return_pending_approval"
    domain = DOMAIN_SALES
    title = "Return approval aging"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = business_date(ctx) - timedelta(days=max(1, int(ctx.config.threshold_days or 1)))
        return self.deps.queries.sales_document_ids_by_status_before(
            "sales_returns", ("Pending Approval",), "return_date", boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("sales_returns")
        sales_return = repo.find_by_id(candidate_id) if repo else None
        if sales_return is None or _status(sales_return.status) != "Pending Approval":
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Sales return awaits approval",
            message=f"{getattr(sales_return, 'return_number', '') or candidate_id} is pending approval",
            ref_type="sales_return",
            ref_id=candidate_id,
        )


class InvoiceAgingJob(BaseJob):
    """Customer-level open invoice aging for Accounts."""

    job_id = "sales.invoice_aging"
    domain = DOMAIN_SALES
    title = "Open invoice aging"

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
        grace = max(0, int(ctx.config.grace_days))
        today = business_date(ctx)
        aged = []
        oldest_age = 0
        for invoice in invoices:
            invoice_date = as_date(invoice.get("invoice_date"))
            if invoice_date is None:
                continue
            age = (today - invoice_date).days - grace
            if age >= max(0, int(ctx.config.threshold_days or 7)):
                aged.append(invoice)
                oldest_age = max(oldest_age, age)
        if not aged:
            return None
        total = sum(money(i.get("outstanding")) for i in aged)
        oldest = min(aged, key=lambda i: as_date(i.get("invoice_date")) or today)
        oldest_id = str(oldest.get("voucher_id") or oldest.get("reference") or "")
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title=f"Invoices aged {aging_bucket(oldest_age)} days",
            message=(
                f"{len(aged)} open invoice(s) totalling {fmt_money(total)} for "
                f"customer {candidate_id}"
            ),
            ref_type="customer_invoice_aging",
            ref_id=f"{candidate_id}:{aging_bucket(oldest_age)}:{oldest_id}",
            metadata={"total": total, "count": len(aged)},
        )


def sales_jobs(deps: Deps) -> List[Tuple[Any, JobDefinition]]:
    return [
        (
            QuotationExpiringJob(deps),
            JobDefinition(
                job_id=QuotationExpiringJob.job_id,
                domain=DOMAIN_SALES,
                title=QuotationExpiringJob.title,
                description="Chase quotations approaching or past their validity date.",
                reminder_offsets_days=[7, 3, 0],
                rule_fields=["reminder_offsets_days"],
            ),
        ),
        (
            EstimateExpiringJob(deps),
            JobDefinition(
                job_id=EstimateExpiringJob.job_id,
                domain=DOMAIN_SALES,
                title=EstimateExpiringJob.title,
                description="Chase estimates approaching or past their validity date.",
                reminder_offsets_days=[7, 3, 0],
                rule_fields=["reminder_offsets_days"],
            ),
        ),
        (
            OrderOverdueJob(deps),
            JobDefinition(
                job_id=OrderOverdueJob.job_id,
                domain=DOMAIN_SALES,
                title=OrderOverdueJob.title,
                description="Flag sales orders past their expected delivery date.",
                grace_days=0,
                rule_fields=["grace_days"],
            ),
        ),
        (
            OrderNoProgressJob(deps),
            JobDefinition(
                job_id=OrderNoProgressJob.job_id,
                domain=DOMAIN_SALES,
                title=OrderNoProgressJob.title,
                description="Surface confirmed orders with nothing dispatched yet.",
                frequency=FREQ_WEEKDAYS,
                threshold_days=7,
                create_activity=False,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            DeliveryNoteStaleJob(deps),
            JobDefinition(
                job_id=DeliveryNoteStaleJob.job_id,
                domain=DOMAIN_SALES,
                title=DeliveryNoteStaleJob.title,
                description="Remind dispatch about delivery notes stuck in draft.",
                frequency=FREQ_WEEKDAYS,
                threshold_days=3,
                create_activity=False,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            ReturnPendingApprovalJob(deps),
            JobDefinition(
                job_id=ReturnPendingApprovalJob.job_id,
                domain=DOMAIN_SALES,
                title=ReturnPendingApprovalJob.title,
                description="Escalate sales returns waiting on approval.",
                frequency=FREQ_WEEKDAYS,
                threshold_days=1,
                create_activity=False,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            InvoiceAgingJob(deps),
            JobDefinition(
                job_id=InvoiceAgingJob.job_id,
                domain=DOMAIN_SALES,
                title=InvoiceAgingJob.title,
                description="Accounts view of aged open invoices, rolled up per customer.",
                threshold_days=7,
                grace_days=0,
                minimum_amount=1.0,
                # CRM payment jobs already create the customer-facing activity.
                create_activity=False,
                rule_fields=["threshold_days", "grace_days", "minimum_amount"],
            ),
        ),
    ]
