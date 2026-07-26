"""Inventory schedulers: low, negative, and stranded stock plus stale transfers."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, List, Optional, Tuple

from vaybooks.bms.application.schedulers.jobs._base import (
    BaseJob,
    Deps,
    Outcome,
    business_date,
    cap,
    money,
)
from vaybooks.bms.application.schedulers.protocol import JobContext, JobDefinition
from vaybooks.bms.domain.schedulers.entities import DOMAIN_INVENTORY
from vaybooks.bms.domain.schedulers.schedule import FREQ_WEEKLY

_TRANSFER_OPEN = ("Draft", "Dispatched")


def _status(value: Any) -> str:
    return getattr(value, "value", value) or ""


def _product(deps: Deps, product_id: str):
    repo = deps.repo("inventory_products")
    if repo is None:
        return None
    try:
        return repo.find_by_id(product_id)
    except Exception:
        return None


class LowStockJob(BaseJob):
    """One job covers low and out-of-stock so a product alerts only once."""

    job_id = "inventory.low_stock"
    domain = DOMAIN_INVENTORY
    title = "Low / reorder stock"

    def identify(self, ctx: JobContext) -> List[str]:
        threshold = float(ctx.option("threshold_qty", 2) or 0)
        return self.deps.queries.product_ids_low_stock(threshold, limit=cap(ctx))

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        product = _product(self.deps, candidate_id)
        if product is None or not getattr(product, "is_active", True):
            return None
        qty = money(getattr(product, "current_qty", 0))
        threshold = float(ctx.option("threshold_qty", 2) or 0)
        if qty < 0 or qty > threshold:
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        severity = "out of stock" if qty <= 0 else "low"
        return Outcome(
            recipient_id=recipient,
            title=f"{getattr(product, 'name', candidate_id)} is {severity}",
            message=(
                f"SKU {getattr(product, 'sku', '')} has {qty:g} on hand "
                f"(threshold {threshold:g})"
            ),
            ref_type="inventory_product",
            ref_id=candidate_id,
            metadata={"qty": qty, "severity": severity},
        )


class NegativeStockJob(BaseJob):
    job_id = "inventory.negative_stock"
    domain = DOMAIN_INVENTORY
    title = "Negative stock"

    def identify(self, ctx: JobContext) -> List[str]:
        limit = cap(ctx)
        queries = self.deps.queries
        product_ids = [f"product|{i}" for i in queries.product_ids_negative_stock(limit=limit)]
        balances = [f"balance|{k}" for k in queries.stock_balance_keys_negative(limit=limit)]
        return (product_ids + balances)[:limit]

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        kind, _, rest = candidate_id.partition("|")
        if kind == "product":
            product = _product(self.deps, rest)
            if product is None or money(getattr(product, "current_qty", 0)) >= -0.001:
                return None
            return Outcome(
                recipient_id=recipient,
                title="Negative stock detected",
                message=(
                    f"{getattr(product, 'name', rest)} is at "
                    f"{money(getattr(product, 'current_qty', 0)):g}"
                ),
                ref_type="inventory_product_negative",
                ref_id=rest,
            )
        product_id, _, location_id = rest.partition("|")
        product = _product(self.deps, product_id)
        name = getattr(product, "name", product_id) if product else product_id
        return Outcome(
            recipient_id=recipient,
            title="Negative stock at a location",
            message=f"{name} has a negative balance at location {location_id}",
            ref_type="stock_balance_negative",
            ref_id=rest,
        )


class TransferStaleJob(BaseJob):
    job_id = "inventory.transfer_stale"
    domain = DOMAIN_INVENTORY
    title = "Stale stock transfer"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = business_date(ctx) - timedelta(
            days=max(1, int(ctx.config.threshold_days or 3))
        )
        return self.deps.queries.stock_transfer_ids_stale(
            _TRANSFER_OPEN, boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("stock_transfers")
        transfer = repo.find_by_id(candidate_id) if repo else None
        if transfer is None:
            return None
        status = _status(transfer.status)
        if status not in _TRANSFER_OPEN:
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        detail = (
            "has never been dispatched"
            if status == "Draft"
            else "was dispatched but not received"
        )
        return Outcome(
            recipient_id=recipient,
            title="Stock transfer is stalled",
            message=f"{getattr(transfer, 'transfer_number', candidate_id)} {detail}",
            ref_type="stock_transfer",
            ref_id=candidate_id,
        )


class InactiveWithStockJob(BaseJob):
    job_id = "inventory.inactive_with_stock"
    domain = DOMAIN_INVENTORY
    title = "Inactive product has stock"

    def identify(self, ctx: JobContext) -> List[str]:
        minimum = float(ctx.option("minimum_qty", 0) or 0)
        return self.deps.queries.product_ids_inactive_with_stock(minimum, limit=cap(ctx))

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        product = _product(self.deps, candidate_id)
        if product is None or getattr(product, "is_active", True):
            return None
        qty = money(getattr(product, "current_qty", 0))
        if qty <= float(ctx.option("minimum_qty", 0) or 0):
            return None
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Inactive product still holds stock",
            message=f"{getattr(product, 'name', candidate_id)} has {qty:g} on hand",
            ref_type="inventory_product_inactive",
            ref_id=candidate_id,
        )


def inventory_jobs(deps: Deps) -> List[Tuple[Any, JobDefinition]]:
    return [
        (
            LowStockJob(deps),
            JobDefinition(
                job_id=LowStockJob.job_id,
                domain=DOMAIN_INVENTORY,
                title=LowStockJob.title,
                description="Alert on products at or below the reorder threshold.",
                create_activity=False,
                options={"threshold_qty": 2},
                rule_fields=["threshold_qty"],
            ),
        ),
        (
            NegativeStockJob(deps),
            JobDefinition(
                job_id=NegativeStockJob.job_id,
                domain=DOMAIN_INVENTORY,
                title=NegativeStockJob.title,
                description="Escalate products or locations that have gone negative.",
                create_activity=False,
            ),
        ),
        (
            TransferStaleJob(deps),
            JobDefinition(
                job_id=TransferStaleJob.job_id,
                domain=DOMAIN_INVENTORY,
                title=TransferStaleJob.title,
                description="Chase transfers stuck in draft or in transit.",
                threshold_days=3,
                create_activity=False,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            InactiveWithStockJob(deps),
            JobDefinition(
                job_id=InactiveWithStockJob.job_id,
                domain=DOMAIN_INVENTORY,
                title=InactiveWithStockJob.title,
                description="Review deactivated products that still carry stock.",
                frequency=FREQ_WEEKLY,
                create_activity=False,
                options={"minimum_qty": 0},
                rule_fields=["minimum_qty"],
            ),
        ),
    ]
