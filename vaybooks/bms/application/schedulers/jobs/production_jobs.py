"""Production scheduler alerts for stale work, yield, margin, and materials."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from vaybooks.bms.application.schedulers.jobs._base import (
    BaseJob,
    Deps,
    Outcome,
    business_date,
    cap,
)
from vaybooks.bms.application.schedulers.protocol import JobContext, JobDefinition
from vaybooks.bms.domain.schedulers.entities import DOMAIN_PRODUCTION


def _batch(deps: Deps, batch_id: str):
    repo = deps.repo("production_batches")
    return repo.find_by_id(batch_id) if repo else None


def _outcome(ctx: JobContext, batch, title: str, message: str, **metadata):
    recipient = ctx.config.fallback_user_id
    if not recipient:
        return None
    return Outcome(
        recipient_id=recipient,
        title=title,
        message=message,
        ref_type="production_batch",
        ref_id=batch.id,
        metadata={"batch_number": batch.batch_number, **metadata},
    )


class StaleDraftBatchJob(BaseJob):
    job_id = "production.batch_stale_draft"
    domain = DOMAIN_PRODUCTION
    title = "Stale production draft"

    def identify(self, ctx: JobContext) -> list[str]:
        boundary = business_date(ctx) - timedelta(
            days=max(1, int(ctx.config.threshold_days or 3))
        )
        return self.deps.queries.production_batch_ids_by_status_before(
            ["Draft"], boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        batch = _batch(self.deps, candidate_id)
        if not batch or batch.status.value != "Draft":
            return None
        return _outcome(
            ctx,
            batch,
            "Production batch is still a draft",
            f"{batch.batch_number} has not entered production.",
        )


class UnpostedBatchJob(BaseJob):
    job_id = "production.batch_unposted"
    domain = DOMAIN_PRODUCTION
    title = "Unposted production batch"

    def identify(self, ctx: JobContext) -> list[str]:
        boundary = business_date(ctx) - timedelta(
            days=max(1, int(ctx.config.threshold_days or 2))
        )
        return self.deps.queries.production_batch_ids_by_status_before(
            ["In Progress"], boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        batch = _batch(self.deps, candidate_id)
        if not batch or batch.status.value != "In Progress" or not batch.outputs:
            return None
        return _outcome(
            ctx,
            batch,
            "Production batch needs posting",
            f"{batch.batch_number} has outputs but is not posted.",
        )


class YieldBelowTargetJob(BaseJob):
    job_id = "production.yield_below_target"
    domain = DOMAIN_PRODUCTION
    title = "Production yield below target"

    def identify(self, ctx: JobContext) -> list[str]:
        return self.deps.queries.production_batch_ids_by_status(
            ["Posted"], limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        batch = _batch(self.deps, candidate_id)
        production = self.deps.service("production")
        recipe = production.get_recipe(batch.recipe_id) if batch and production else None
        if not batch or not recipe:
            return None
        expected = sum(line.expected_qty for line in recipe.outputs)
        expected *= batch.planned_quantity / recipe.base_quantity
        actual = sum(line.qty for line in batch.outputs)
        variance_pct = (actual - expected) / expected * 100 if expected else 0
        floor = -abs(float(ctx.option("variance_pct", 10) or 10))
        if variance_pct >= floor:
            return None
        return _outcome(
            ctx,
            batch,
            "Production yield below target",
            f"{batch.batch_number} yield is {abs(variance_pct):.1f}% below recipe.",
            variance_pct=round(variance_pct, 2),
        )


class NegativeMarginJob(BaseJob):
    job_id = "production.negative_margin"
    domain = DOMAIN_PRODUCTION
    title = "Production margin below floor"

    def identify(self, ctx: JobContext) -> list[str]:
        floor = float(ctx.option("margin_floor", 0) or 0)
        return self.deps.queries.production_batch_ids_margin_below(
            floor, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        batch = _batch(self.deps, candidate_id)
        floor = float(ctx.option("margin_floor", 0) or 0)
        if not batch or batch.batch_margin >= floor:
            return None
        return _outcome(
            ctx,
            batch,
            "Production margin below floor",
            f"{batch.batch_number} margin is ₹{batch.batch_margin:,.2f}.",
            margin=batch.batch_margin,
        )


class WipAgingJob(BaseJob):
    job_id = "production.wip_aging"
    domain = DOMAIN_PRODUCTION
    title = "Aged production WIP"

    def identify(self, ctx: JobContext) -> list[str]:
        boundary = business_date(ctx) - timedelta(
            days=max(1, int(ctx.config.threshold_days or 7))
        )
        return self.deps.queries.production_batch_ids_by_status_before(
            ["Draft", "In Progress"], boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        batch = _batch(self.deps, candidate_id)
        if not batch or batch.status.value not in {"Draft", "In Progress"}:
            return None
        return _outcome(
            ctx,
            batch,
            "Production WIP is aging",
            f"{batch.batch_number} holds ₹{batch.total_cost:,.2f} in open WIP.",
            wip_value=batch.total_cost,
        )


class RawMaterialShortageJob(BaseJob):
    job_id = "production.rm_shortage"
    domain = DOMAIN_PRODUCTION
    title = "Production raw material shortage"

    def identify(self, ctx: JobContext) -> list[str]:
        return self.deps.queries.production_batch_ids_by_status(
            ["Draft", "In Progress"], limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        batch = _batch(self.deps, candidate_id)
        inventory = self.deps.service("inventory")
        if not batch or not inventory:
            return None
        shortages = []
        buffer_qty = float(ctx.option("threshold_qty", 0) or 0)
        for issue in batch.issues:
            available = inventory.get_stock_balance(
                issue.product_id, issue.location_id or batch.location_id
            )
            if available + buffer_qty < issue.qty:
                shortages.append(issue.product_name or issue.product_id)
        if not shortages:
            return None
        return _outcome(
            ctx,
            batch,
            "Raw material shortage for production",
            f"{batch.batch_number} is short of: {', '.join(shortages[:4])}.",
            shortage_count=len(shortages),
        )


def production_jobs(deps: Deps) -> list[tuple[Any, JobDefinition]]:
    specs = [
        (
            StaleDraftBatchJob,
            "Alert when a production batch remains in draft.",
            3,
            {},
            ["threshold_days"],
        ),
        (
            UnpostedBatchJob,
            "Alert when a completed production run is not posted.",
            2,
            {},
            ["threshold_days"],
        ),
        (
            YieldBelowTargetJob,
            "Alert when actual output is below recipe yield.",
            0,
            {"variance_pct": 10},
            ["variance_pct"],
        ),
        (
            NegativeMarginJob,
            "Alert when posted batch margin is below the configured floor.",
            0,
            {"margin_floor": 0},
            ["margin_floor"],
        ),
        (
            WipAgingJob,
            "Alert on production WIP held open too long.",
            7,
            {},
            ["threshold_days"],
        ),
        (
            RawMaterialShortageJob,
            "Alert when planned production lacks raw materials.",
            0,
            {"threshold_qty": 0},
            ["threshold_qty"],
        ),
    ]
    return [
        (
            cls(deps),
            JobDefinition(
                job_id=cls.job_id,
                domain=DOMAIN_PRODUCTION,
                title=cls.title,
                description=description,
                threshold_days=threshold_days,
                options=options,
                rule_fields=fields,
                create_activity=False,
            ),
        )
        for cls, description, threshold_days, options, fields in specs
    ]
