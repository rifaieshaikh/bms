from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Optional

from vaybooks.bms.domain.shared.enums import ProductionBatchStatus


class ProductionReportService:
    def __init__(self, production_service: Any) -> None:
        self._production = production_service

    @staticmethod
    def _range(filters: Any) -> tuple[Optional[date], Optional[date]]:
        if filters is None:
            return None, None
        value = (
            filters.get("date_range")
            if isinstance(filters, dict)
            else getattr(filters, "date_range", None)
        )
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return value[0], value[1]
        return None, None

    def _batches(self, filters: Any = None):
        start, end = self._range(filters)
        batch_id = (
            str(filters.get("batch_id") or "")
            if isinstance(filters, dict)
            else str(getattr(filters, "batch_id", "") or "")
        )
        rows = self._production.list_batches()
        return [
            batch
            for batch in rows
            if (not batch_id or batch.id == batch_id)
            if (not start or batch.batch_date >= start)
            and (not end or batch.batch_date <= end)
        ]

    def batch_register_report(self, filters: Any = None) -> list[dict]:
        return [
            {
                "date": batch.batch_date,
                "batch_number": batch.batch_number,
                "recipe": batch.recipe_name,
                "status": batch.status.value,
                "planned_quantity": batch.planned_quantity,
                "material_cost": batch.material_cost,
                "expense_cost": batch.expense_cost,
                "total_cost": batch.total_cost,
                "expected_sales_value": batch.expected_sales_value,
                "margin": batch.batch_margin,
            }
            for batch in self._batches(filters)
        ]

    def batch_cost_sheet_report(self, filters: Any = None) -> list[dict]:
        rows = []
        for batch in self._batches(filters):
            for output in batch.outputs:
                rows.append(
                    {
                        "date": batch.batch_date,
                        "batch_number": batch.batch_number,
                        "recipe": batch.recipe_name,
                        "output": output.product_name,
                        "role": output.role.value,
                        "quantity": output.qty,
                        "allocated_cost": output.allocated_cost,
                        "cost_per_unit": output.unit_cost,
                        "nrv_rate": output.nrv_rate,
                    }
                )
        return rows

    def batch_margin_report(self, filters: Any = None) -> list[dict]:
        return [
            {
                "date": batch.batch_date,
                "batch_number": batch.batch_number,
                "recipe": batch.recipe_name,
                "total_cost": batch.total_cost,
                "expected_sales_value": batch.expected_sales_value,
                "margin": batch.batch_margin,
                "margin_pct": (
                    round(batch.batch_margin / batch.expected_sales_value * 100, 2)
                    if batch.expected_sales_value
                    else 0
                ),
            }
            for batch in self._batches(filters)
            if batch.status == ProductionBatchStatus.POSTED
        ]

    def yield_variance_report(self, filters: Any = None) -> list[dict]:
        rows = []
        for batch in self._batches(filters):
            recipe = self._production.get_recipe(batch.recipe_id)
            if not recipe:
                continue
            scale = batch.planned_quantity / recipe.base_quantity
            expected = {
                line.product_id: float(line.expected_qty) * scale
                for line in recipe.outputs
            }
            for output in batch.outputs:
                expected_qty = expected.get(output.product_id, 0)
                variance = float(output.qty) - expected_qty
                rows.append(
                    {
                        "date": batch.batch_date,
                        "batch_number": batch.batch_number,
                        "output": output.product_name,
                        "expected_qty": expected_qty,
                        "actual_qty": output.qty,
                        "variance": variance,
                        "variance_pct": (
                            round(variance / expected_qty * 100, 2)
                            if expected_qty
                            else 0
                        ),
                    }
                )
        return rows

    def production_expense_report(self, filters: Any = None) -> list[dict]:
        rows = []
        for batch in self._batches(filters):
            activity_names = {stage.id: stage.name for stage in batch.stages}
            for cost in batch.costs:
                rows.append(
                    {
                        "date": batch.batch_date,
                        "batch_number": batch.batch_number,
                        "cost_type": cost.cost_type,
                        "activity": activity_names.get(cost.activity_id, ""),
                        "description": cost.description,
                        "amount": cost.amount,
                    }
                )
        return rows

    def output_summary_report(self, filters: Any = None) -> list[dict]:
        totals: dict[str, dict] = {}
        for batch in self._batches(filters):
            for output in batch.outputs:
                row = totals.setdefault(
                    output.product_id,
                    {
                        "product": output.product_name,
                        "quantity": 0.0,
                        "allocated_cost": 0.0,
                        "expected_value": 0.0,
                    },
                )
                row["quantity"] += float(output.qty)
                row["allocated_cost"] += float(output.allocated_cost)
                row["expected_value"] += float(output.qty) * float(output.nrv_rate)
        return list(totals.values())

    def rm_consumption_report(self, filters: Any = None) -> list[dict]:
        totals: dict[str, dict] = {}
        for batch in self._batches(filters):
            for issue in batch.issues:
                row = totals.setdefault(
                    issue.product_id,
                    {
                        "product": issue.product_name,
                        "quantity": 0.0,
                        "total_cost": 0.0,
                    },
                )
                row["quantity"] += float(issue.qty)
                row["total_cost"] += float(issue.total_cost)
        return list(totals.values())

    def wip_open_batches_report(self, filters: Any = None) -> list[dict]:
        return [
            {
                "date": batch.batch_date,
                "batch_number": batch.batch_number,
                "recipe": batch.recipe_name,
                "status": batch.status.value,
                "wip_value": batch.total_cost,
                "age_days": (date.today() - batch.batch_date).days,
            }
            for batch in self._batches(filters)
            if batch.status
            in {ProductionBatchStatus.DRAFT, ProductionBatchStatus.IN_PROGRESS}
        ]

    def cost_per_unit_trend_report(self, filters: Any = None) -> list[dict]:
        return [
            {
                "date": batch.batch_date,
                "batch_number": batch.batch_number,
                "product": output.product_name,
                "quantity": output.qty,
                "cost_per_unit": output.unit_cost,
            }
            for batch in self._batches(filters)
            for output in batch.outputs
            if batch.status == ProductionBatchStatus.POSTED
        ]

    def recipe_master_report(self, filters: Any = None) -> list[dict]:
        return [
            {
                "code": recipe.code,
                "name": recipe.name,
                "base_quantity": recipe.base_quantity,
                "allocation_method": recipe.allocation_method.value,
                "inputs": len(recipe.inputs),
                "outputs": len(recipe.outputs),
                "activities": len(recipe.stages),
                "active": recipe.is_active,
            }
            for recipe in self._production.list_recipes(active_only=False)
        ]

    @staticmethod
    def to_csv(rows: list[dict]) -> str:
        if not rows:
            return ""
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue()
