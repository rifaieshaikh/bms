"""Boutique schedulers: ETD tracking, activity bottlenecks, and payment due."""

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
    today_bounds,
)
from vaybooks.bms.application.schedulers.protocol import JobContext, JobDefinition
from vaybooks.bms.domain.schedulers.entities import DOMAIN_BOUTIQUE
from vaybooks.bms.domain.schedulers.time import business_date_of
from vaybooks.bms.infrastructure.db.bson_utils import as_date

CLOSED_ORDER_STATUSES = ("Delivered", "Completed", "Cancelled")
OPEN_ACTIVITY_STATUSES = ("Pending", "In Progress")


def _status(value: Any) -> str:
    return getattr(value, "value", value) or ""


def _order(deps: Deps, order_id: str):
    repo = deps.repo("boutique_orders")
    if repo is None:
        return None
    try:
        return repo.find_by_id(order_id)
    except Exception:
        return None


def _order_open(order) -> bool:
    return order is not None and _status(order.order_status) not in CLOSED_ORDER_STATUSES


class EtdTodayJob(BaseJob):
    job_id = "boutique.etd_today"
    domain = DOMAIN_BOUTIQUE
    title = "Order ETD today"

    def identify(self, ctx: JobContext) -> List[str]:
        start, end = today_bounds(ctx)
        return self.deps.queries.boutique_order_ids_by_etd(
            CLOSED_ORDER_STATUSES, start, end, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        order = _order(self.deps, candidate_id)
        if not _order_open(order):
            return None
        etd = as_date(getattr(order, "expected_delivery_date", None))
        if etd != business_date(ctx):
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Boutique order is due today",
            message=(
                f"{getattr(order, 'order_number', candidate_id)} for "
                f"{getattr(order, 'customer_name', '') or 'customer'}"
            ),
            ref_type="customization_order",
            ref_id=f"{candidate_id}:{etd.isoformat()}",
        )


class EtdOverdueJob(BaseJob):
    job_id = "boutique.etd_overdue"
    domain = DOMAIN_BOUTIQUE
    title = "Order ETD overdue"

    def identify(self, ctx: JobContext) -> List[str]:
        start, _ = today_bounds(ctx)
        boundary = start - timedelta(days=max(0, int(ctx.config.grace_days)))
        return self.deps.queries.boutique_order_ids_etd_before(
            CLOSED_ORDER_STATUSES, boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        order = _order(self.deps, candidate_id)
        if not _order_open(order):
            return None
        etd = as_date(getattr(order, "expected_delivery_date", None))
        if etd is None or etd >= business_date(ctx):
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        overdue = (business_date(ctx) - etd).days
        return Outcome(
            recipient_id=recipient,
            title="Boutique order is overdue",
            message=(
                f"{getattr(order, 'order_number', candidate_id)} is {overdue} day(s) "
                f"past its ETD of {etd.isoformat()}"
            ),
            ref_type="customization_order_overdue",
            ref_id=candidate_id,
            activity_label="Boutique ETD Overdue",
            activity_customer_id=getattr(order, "customer_id", "") or "",
            activity_source_id=candidate_id,
        )


class ItemEtdJob(BaseJob):
    job_id = "boutique.item_etd"
    domain = DOMAIN_BOUTIQUE
    title = "Item ETD due or overdue"

    def identify(self, ctx: JobContext) -> List[str]:
        _, end = today_bounds(ctx)
        return self.deps.queries.boutique_item_refs_due(
            CLOSED_ORDER_STATUSES, end, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        order_id, _, bill_number = candidate_id.partition("|")
        order = _order(self.deps, order_id)
        if not _order_open(order):
            return None
        item = next(
            (
                i
                for i in (getattr(order, "customization_items", []) or [])
                if str(getattr(i, "bill_number", "")) == bill_number
            ),
            None,
        )
        if item is None or getattr(item, "is_cancellation_charge", False):
            return None
        item_etd = as_date(getattr(item, "expected_delivery_date", None))
        order_etd = as_date(getattr(order, "expected_delivery_date", None))
        effective = item_etd or order_etd
        if effective is None or effective > business_date(ctx):
            return None
        if ctx.option("skip_if_same_as_order_etd", True) and item_etd == order_etd:
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Boutique item is due",
            message=f"Bill {bill_number} on order {getattr(order, 'order_number', order_id)}",
            ref_type="customization_item",
            ref_id=f"{order_id}:{bill_number}:{effective.isoformat()}",
        )


class ActivityBottleneckJob(BaseJob):
    """Aggregates pending activities by name and digests each bottleneck once."""

    job_id = "boutique.activity_bottleneck"
    domain = DOMAIN_BOUTIQUE
    title = "Activity bottleneck digest"

    def identify(self, ctx: JobContext) -> List[str]:
        counts = self.deps.queries.boutique_activity_bottlenecks(
            CLOSED_ORDER_STATUSES, OPEN_ACTIVITY_STATUSES
        )
        pending_threshold = int(ctx.option("pending_threshold", 10) or 10)
        overdue_threshold = int(ctx.option("overdue_threshold", 1) or 1)
        self._counts = counts
        return [
            name
            for name, (pending, overdue) in counts.items()
            if pending >= pending_threshold or overdue >= overdue_threshold
        ][: cap(ctx)]

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        counts = getattr(self, "_counts", {})
        pending, overdue = counts.get(candidate_id, (0, 0))
        recipient = ctx.config.fallback_user_id
        if not recipient or (pending == 0 and overdue == 0):
            return None
        return Outcome(
            recipient_id=recipient,
            title=f"{candidate_id} is a bottleneck",
            message=f"{pending} pending, {overdue} on overdue orders",
            ref_type="boutique_activity_bottleneck",
            ref_id=f"{candidate_id}:{day_bucket(business_date(ctx))}",
            metadata={"pending": pending, "overdue": overdue},
        )


class ActivityOverdueJob(BaseJob):
    job_id = "boutique.activity_overdue"
    domain = DOMAIN_BOUTIQUE
    title = "Actionable overdue activity"

    def identify(self, ctx: JobContext) -> List[str]:
        start, _ = today_bounds(ctx)
        return self.deps.queries.boutique_activity_refs_overdue(
            CLOSED_ORDER_STATUSES, OPEN_ACTIVITY_STATUSES, start, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        order_id, _, activity_name = candidate_id.partition("|")
        order = _order(self.deps, order_id)
        if not _order_open(order):
            return None
        activity = next(
            (
                a
                for a in (getattr(order, "order_activities", []) or [])
                if str(getattr(a, "activity_name", "")) == activity_name
                and _status(getattr(a, "activity_status", "")) in OPEN_ACTIVITY_STATUSES
            ),
            None,
        )
        if activity is None:
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Overdue boutique activity",
            message=(
                f"{activity_name} is still open on "
                f"{getattr(order, 'order_number', order_id)}"
            ),
            ref_type="boutique_order_activity",
            ref_id=f"{order_id}:{activity_name}",
        )


class BillsPendingInvoiceJob(BaseJob):
    job_id = "boutique.bills_pending_invoice"
    domain = DOMAIN_BOUTIQUE
    title = "Completed bills pending invoice"

    def identify(self, ctx: JobContext) -> List[str]:
        return self.deps.queries.boutique_order_ids_pending_invoice(
            ("Cancelled",), limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        order = _order(self.deps, candidate_id)
        if order is None or _status(order.order_status) == "Cancelled":
            return None
        gating = set(
            ctx.option(
                "ready_statuses",
                ["Completed", "Ready for Delivery", "Invoice Generated"],
            )
        )
        pending = [
            i
            for i in (getattr(order, "customization_items", []) or [])
            if not getattr(i, "is_cancellation_charge", False)
            and _status(getattr(i, "item_status", "")) in gating
        ]
        if not pending:
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Bills are pending invoice",
            message=(
                f"{len(pending)} completed item(s) on "
                f"{getattr(order, 'order_number', candidate_id)} are not invoiced"
            ),
            ref_type="boutique_pending_invoice",
            ref_id=candidate_id,
            metadata={"pending": len(pending)},
        )


class BillsPendingDeliveryJob(BaseJob):
    job_id = "boutique.bills_pending_delivery"
    domain = DOMAIN_BOUTIQUE
    title = "Completed bills pending delivery"

    def identify(self, ctx: JobContext) -> List[str]:
        return self.deps.queries.boutique_order_ids_pending_delivery(
            ("Cancelled",), limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        order = _order(self.deps, candidate_id)
        if order is None or _status(order.order_status) == "Cancelled":
            return None
        gating = set(
            ctx.option(
                "ready_statuses",
                ["Completed", "Ready for Delivery", "Invoice Generated"],
            )
        )
        pending = [
            i
            for i in (getattr(order, "customization_items", []) or [])
            if not getattr(i, "is_cancellation_charge", False)
            and _status(getattr(i, "item_status", "")) in gating
        ]
        if not pending:
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Bills are pending delivery",
            message=(
                f"{len(pending)} item(s) on "
                f"{getattr(order, 'order_number', candidate_id)} are awaiting delivery"
            ),
            ref_type="boutique_pending_delivery",
            ref_id=candidate_id,
            metadata={"pending": len(pending)},
        )


class PaymentDueJob(BaseJob):
    """Fires only from a boutique invoice with a linked posted voucher."""

    job_id = "boutique.payment_due"
    domain = DOMAIN_BOUTIQUE
    title = "Boutique invoice payment due"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = ctx.now - timedelta(days=max(0, int(ctx.config.threshold_days or 7)))
        return self.deps.queries.boutique_invoice_ids_with_outstanding(
            boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        invoice_repo = self.deps.repo("boutique_invoices")
        voucher_repo = self.deps.repo("vouchers")
        if invoice_repo is None or voucher_repo is None:
            return None
        try:
            invoice = invoice_repo.find_by_id(candidate_id)
            voucher = voucher_repo.find_by_reference_invoice(candidate_id)
        except Exception:
            return None
        if invoice is None or voucher is None:
            return None
        outstanding = money(
            getattr(voucher, "outstanding", None)
            if getattr(voucher, "outstanding", None) is not None
            else getattr(invoice, "outstanding", 0)
        )
        if outstanding <= 0:
            return None
        invoice_date = business_date_of(getattr(invoice, "invoice_date", None))
        age = (business_date(ctx) - invoice_date).days if invoice_date else 0
        if age < max(0, int(ctx.config.threshold_days or 7)):
            return None
        customer_id = getattr(invoice, "customer_id", "") or ""
        recipient = ctx.config.fallback_user_id or self._customer_owner(customer_id)
        if not recipient:
            return None
        ref_id = f"{candidate_id}:{aging_bucket(age)}"
        return Outcome(
            recipient_id=recipient,
            title="Boutique invoice payment due",
            message=(
                f"{getattr(invoice, 'invoice_number', candidate_id)} has "
                f"{fmt_money(outstanding)} outstanding for {age} day(s)"
            ),
            ref_type="boutique_invoice",
            ref_id=ref_id,
            activity_label="Payment Reminder",
            activity_customer_id=customer_id,
            activity_source_id=ref_id,
        )

    def _customer_owner(self, customer_id: str) -> str:
        repo = self.deps.repo("customers")
        if repo is None or not customer_id:
            return ""
        try:
            customer = repo.find_by_id(customer_id)
        except Exception:
            return ""
        return getattr(customer, "assigned_user_id", "") or ""


def boutique_jobs(deps: Deps) -> List[Tuple[Any, JobDefinition]]:
    return [
        (
            EtdTodayJob(deps),
            JobDefinition(
                job_id=EtdTodayJob.job_id,
                domain=DOMAIN_BOUTIQUE,
                title=EtdTodayJob.title,
                description="Notify operations about orders due today.",
                create_activity=False,
            ),
        ),
        (
            EtdOverdueJob(deps),
            JobDefinition(
                job_id=EtdOverdueJob.job_id,
                domain=DOMAIN_BOUTIQUE,
                title=EtdOverdueJob.title,
                description="Escalate orders past their expected delivery date.",
                grace_days=0,
                rule_fields=["grace_days"],
            ),
        ),
        (
            ItemEtdJob(deps),
            JobDefinition(
                job_id=ItemEtdJob.job_id,
                domain=DOMAIN_BOUTIQUE,
                title=ItemEtdJob.title,
                description="Track item-level delivery dates separately from the order.",
                create_activity=False,
                options={"skip_if_same_as_order_etd": True},
                rule_fields=["skip_if_same_as_order_etd"],
            ),
        ),
        (
            ActivityBottleneckJob(deps),
            JobDefinition(
                job_id=ActivityBottleneckJob.job_id,
                domain=DOMAIN_BOUTIQUE,
                title=ActivityBottleneckJob.title,
                description="Digest workshop stages that are piling up.",
                create_activity=False,
                options={"pending_threshold": 10, "overdue_threshold": 1},
                rule_fields=["pending_threshold", "overdue_threshold"],
            ),
        ),
        (
            ActivityOverdueJob(deps),
            JobDefinition(
                job_id=ActivityOverdueJob.job_id,
                domain=DOMAIN_BOUTIQUE,
                title=ActivityOverdueJob.title,
                description="Raise a review task per open activity on an overdue order.",
                create_activity=False,
            ),
        ),
        (
            BillsPendingInvoiceJob(deps),
            JobDefinition(
                job_id=BillsPendingInvoiceJob.job_id,
                domain=DOMAIN_BOUTIQUE,
                title=BillsPendingInvoiceJob.title,
                description="Find completed items that were never invoiced.",
                create_activity=False,
                options={
                    "ready_statuses": [
                        "Completed",
                        "Ready for Delivery",
                        "Invoice Generated",
                    ]
                },
            ),
        ),
        (
            BillsPendingDeliveryJob(deps),
            JobDefinition(
                job_id=BillsPendingDeliveryJob.job_id,
                domain=DOMAIN_BOUTIQUE,
                title=BillsPendingDeliveryJob.title,
                description="Find invoiced items that were never delivered.",
                create_activity=False,
                options={
                    "ready_statuses": [
                        "Completed",
                        "Ready for Delivery",
                        "Invoice Generated",
                    ]
                },
            ),
        ),
        (
            PaymentDueJob(deps),
            JobDefinition(
                job_id=PaymentDueJob.job_id,
                domain=DOMAIN_BOUTIQUE,
                title=PaymentDueJob.title,
                description="Chase boutique invoices with an outstanding posted voucher.",
                threshold_days=7,
                rule_fields=["threshold_days"],
            ),
        ),
    ]
