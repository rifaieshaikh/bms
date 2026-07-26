"""Purchases schedulers: PO receipt aging, GRN drafts, and payable aging."""

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
    fmt_money,
    money,
    week_bucket,
)
from vaybooks.bms.application.schedulers.protocol import JobContext, JobDefinition
from vaybooks.bms.domain.schedulers.entities import DOMAIN_PURCHASES
from vaybooks.bms.domain.schedulers.schedule import FREQ_WEEKDAYS
from vaybooks.bms.infrastructure.db.bson_utils import as_date

_PO_OPEN = ("Sent", "Partially Received")


def _status(value: Any) -> str:
    return getattr(value, "value", value) or ""


class PurchaseOrderOverdueJob(BaseJob):
    job_id = "purchases.order_overdue"
    domain = DOMAIN_PURCHASES
    title = "Purchase order receipt overdue"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = business_date(ctx) - timedelta(days=max(0, int(ctx.config.grace_days)))
        return self.deps.queries.purchase_order_ids_overdue(
            _PO_OPEN, boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("purchase_orders")
        order = repo.find_by_id(candidate_id) if repo else None
        if order is None or _status(order.status) not in _PO_OPEN:
            return None
        expected = as_date(getattr(order, "expected_date", None))
        if expected is None or expected >= business_date(ctx):
            return None
        recipient = ctx.config.fallback_user_id or getattr(order, "project_owner_id", "")
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Purchase order overdue",
            message=(
                f"{getattr(order, 'po_number', candidate_id)} from "
                f"{getattr(order, 'vendor_name', '') or 'vendor'} was due "
                f"{expected.isoformat()}"
            ),
            ref_type="purchase_order",
            ref_id=f"{candidate_id}:{expected.isoformat()}",
        )


class PurchaseOrderNoReceiptJob(BaseJob):
    job_id = "purchases.order_no_receipt"
    domain = DOMAIN_PURCHASES
    title = "Sent PO with no GRN"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = business_date(ctx) - timedelta(
            days=max(1, int(ctx.config.threshold_days or 7))
        )
        return self.deps.queries.purchase_order_ids_without_receipt(
            ("Sent",), boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("purchase_orders")
        order = repo.find_by_id(candidate_id) if repo else None
        if order is None or _status(order.status) != "Sent":
            return None
        received = sum(
            money(getattr(line, "qty_received", 0))
            for line in getattr(order, "lines", []) or []
        )
        if received > 0:
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Purchase order has no receipt yet",
            message=f"{getattr(order, 'po_number', candidate_id)} has no goods received",
            ref_type="purchase_order",
            ref_id=f"{candidate_id}:{week_bucket(business_date(ctx))}",
        )


class GrnStaleJob(BaseJob):
    job_id = "purchases.grn_stale"
    domain = DOMAIN_PURCHASES
    title = "Draft GRN needs confirmation"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = business_date(ctx) - timedelta(
            days=max(1, int(ctx.config.threshold_days or 2))
        )
        return self.deps.queries.sales_document_ids_by_status_before(
            "goods_receipts", ("Draft",), "receipt_date", boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("goods_receipts")
        grn = repo.find_by_id(candidate_id) if repo else None
        if grn is None or _status(grn.status) != "Draft":
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Draft goods receipt needs confirmation",
            message=f"{getattr(grn, 'grn_number', '') or candidate_id} is still a draft",
            ref_type="goods_receipt",
            ref_id=candidate_id,
        )


class BillPayableAgingJob(BaseJob):
    job_id = "purchases.bill_payable_aging"
    domain = DOMAIN_PURCHASES
    title = "Vendor bills aging"

    def identify(self, ctx: JobContext) -> List[str]:
        minimum = max(1.0, float(ctx.config.minimum_amount or 1.0))
        return self.deps.queries.vendor_ids_with_open_bills(minimum, limit=cap(ctx))

    def _open_bills(self, vendor_id: str) -> List[dict]:
        accounting = self.deps.service("accounting")
        if accounting is None:
            return []
        for method in ("open_vendor_bills", "vendor_open_bills", "open_bills"):
            fn = getattr(accounting, method, None)
            if callable(fn):
                try:
                    return list(fn(vendor_id) or [])
                except Exception:
                    return []
        return []

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        bills = self._open_bills(candidate_id)
        today = business_date(ctx)
        grace = max(0, int(ctx.config.grace_days))
        aged = []
        oldest_age = 0
        for bill in bills:
            bill_date = as_date(bill.get("bill_date") or bill.get("voucher_date"))
            if bill_date is None:
                continue
            age = (today - bill_date).days - grace
            if age >= max(0, int(ctx.config.threshold_days or 7)):
                aged.append(bill)
                oldest_age = max(oldest_age, age)
        if bills and not aged:
            return None
        total = sum(money(b.get("outstanding")) for b in aged)
        oldest = (
            min(aged, key=lambda b: as_date(b.get("bill_date") or b.get("voucher_date")) or today)
            if aged
            else {}
        )
        oldest_id = str(oldest.get("voucher_id") or oldest.get("reference") or "balance")
        vendor_name = self._vendor_name(candidate_id)
        return Outcome(
            recipient_id=recipient,
            title=f"Vendor payables aged {aging_bucket(oldest_age)} days",
            message=(
                f"{vendor_name} has {len(aged) or 'an'} open bill(s)"
                + (f" totalling {fmt_money(total)}" if total else "")
            ),
            ref_type="vendor_payable_aging",
            ref_id=f"{candidate_id}:{aging_bucket(oldest_age)}:{oldest_id}",
            metadata={"total": total, "count": len(aged)},
        )

    def _vendor_name(self, vendor_id: str) -> str:
        repo = self.deps.repo("vendors")
        if repo is None:
            return vendor_id
        try:
            vendor = repo.find_by_id(vendor_id)
        except Exception:
            return vendor_id
        return getattr(vendor, "vendor_name", "") or vendor_id


def purchase_jobs(deps: Deps) -> List[Tuple[Any, JobDefinition]]:
    return [
        (
            PurchaseOrderOverdueJob(deps),
            JobDefinition(
                job_id=PurchaseOrderOverdueJob.job_id,
                domain=DOMAIN_PURCHASES,
                title=PurchaseOrderOverdueJob.title,
                description="Chase purchase orders past their expected receipt date.",
                grace_days=0,
                create_activity=False,
                rule_fields=["grace_days"],
            ),
        ),
        (
            PurchaseOrderNoReceiptJob(deps),
            JobDefinition(
                job_id=PurchaseOrderNoReceiptJob.job_id,
                domain=DOMAIN_PURCHASES,
                title=PurchaseOrderNoReceiptJob.title,
                description="Surface sent purchase orders with nothing received.",
                frequency=FREQ_WEEKDAYS,
                threshold_days=7,
                create_activity=False,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            GrnStaleJob(deps),
            JobDefinition(
                job_id=GrnStaleJob.job_id,
                domain=DOMAIN_PURCHASES,
                title=GrnStaleJob.title,
                description="Remind the warehouse about unconfirmed goods receipts.",
                frequency=FREQ_WEEKDAYS,
                threshold_days=2,
                create_activity=False,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            BillPayableAgingJob(deps),
            JobDefinition(
                job_id=BillPayableAgingJob.job_id,
                domain=DOMAIN_PURCHASES,
                title=BillPayableAgingJob.title,
                description="Accounts view of aged vendor bills, rolled up per vendor.",
                threshold_days=7,
                grace_days=0,
                minimum_amount=1.0,
                create_activity=False,
                rule_fields=["threshold_days", "grace_days", "minimum_amount"],
            ),
        ),
    ]
