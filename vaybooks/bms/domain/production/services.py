from __future__ import annotations

from datetime import date
from typing import Optional

from vaybooks.bms.domain.production.entities import (
    BatchCost,
    BatchIssue,
    BatchOutput,
    BatchStage,
    ProductionBatch,
    Recipe,
)
from vaybooks.bms.domain.production.repository import (
    ProductionBatchRepository,
    RecipeRepository,
)
from vaybooks.bms.domain.shared.enums import (
    ProductionBatchStatus,
    ProductionCostAllocationMethod,
    ProductionOutputRole,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProductionDomainService:
    def __init__(
        self,
        recipe_repo: RecipeRepository,
        batch_repo: ProductionBatchRepository,
    ) -> None:
        self._recipe_repo = recipe_repo
        self._batch_repo = batch_repo

    def save_recipe(self, recipe: Recipe) -> Recipe:
        recipe.name = recipe.name.strip()
        recipe.code = recipe.code.strip()
        if not recipe.name:
            raise ValidationError("Recipe name is required")
        if recipe.base_quantity <= 0:
            raise ValidationError("Recipe base quantity must be positive")
        if not recipe.inputs:
            raise ValidationError("At least one recipe input is required")
        if not recipe.outputs:
            raise ValidationError("At least one recipe output is required")
        if any(float(line.qty) <= 0 for line in recipe.inputs):
            raise ValidationError("Recipe input quantities must be positive")
        if any(float(line.expected_qty) <= 0 for line in recipe.outputs):
            raise ValidationError("Recipe output quantities must be positive")
        if not any(line.role == ProductionOutputRole.MAIN for line in recipe.outputs):
            raise ValidationError("Recipe requires a main output")
        if recipe.allocation_method == ProductionCostAllocationMethod.PERCENTAGE:
            total = sum(float(line.allocation_pct or 0) for line in recipe.outputs)
            if abs(total - 100.0) > 0.01:
                raise ValidationError("Output allocation percentages must total 100")
        duplicate = self._recipe_repo.find_by_code(recipe.code) if recipe.code else None
        if duplicate and duplicate.id != recipe.id:
            raise ValidationError("Recipe code already exists")
        recipe.stages.sort(key=lambda item: item.sequence)
        recipe.update()
        return self._recipe_repo.save(recipe)

    def create_batch(
        self,
        *,
        batch_number: str,
        recipe_id: str,
        batch_date: date,
        location_id: str,
        planned_quantity: float = 1.0,
        notes: str = "",
    ) -> ProductionBatch:
        number = batch_number.strip()
        if not number:
            raise ValidationError("Batch number is required")
        if self._batch_repo.find_by_number(number):
            raise ValidationError("Batch number already exists")
        recipe = self._recipe_repo.find_by_id(recipe_id)
        if not recipe or not recipe.is_active:
            raise ValidationError("Active recipe not found")
        if not location_id:
            raise ValidationError("Production location is required")
        if planned_quantity <= 0:
            raise ValidationError("Planned quantity must be positive")
        scale = float(planned_quantity) / float(recipe.base_quantity)
        batch = ProductionBatch(
            batch_number=number,
            recipe_id=recipe.id,
            recipe_name=recipe.name,
            batch_date=batch_date,
            location_id=location_id,
            planned_quantity=float(planned_quantity),
            allocation_method=recipe.allocation_method,
            notes=notes.strip(),
            stages=[
                BatchStage(
                    recipe_stage_id=stage.id,
                    name=stage.name,
                    sequence=stage.sequence,
                    notes=stage.notes,
                )
                for stage in recipe.stages
            ],
            issues=[
                BatchIssue(
                    product_id=line.product_id,
                    product_name=line.product_name,
                    unit=line.unit,
                    qty=round(float(line.qty) * scale, 4),
                    location_id=location_id,
                )
                for line in recipe.inputs
            ],
            outputs=[
                BatchOutput(
                    product_id=line.product_id,
                    product_name=line.product_name,
                    unit=line.unit,
                    qty=round(float(line.expected_qty) * scale, 4),
                    role=line.role,
                    allocation_pct=float(line.allocation_pct or 0),
                    nrv_rate=float(line.nrv_rate or 0),
                    location_id=location_id,
                )
                for line in recipe.outputs
            ],
        )
        return self._batch_repo.save(batch)

    def save_batch(self, batch: ProductionBatch) -> ProductionBatch:
        if not batch.is_editable:
            raise ValidationError("Posted or cancelled batches cannot be edited")
        if not batch.issues:
            raise ValidationError("At least one material issue is required")
        if not batch.outputs:
            raise ValidationError("At least one output is required")
        if any(float(line.qty) <= 0 for line in batch.issues + batch.outputs):
            raise ValidationError("Issue and output quantities must be positive")
        if any(float(cost.amount) < 0 for cost in batch.costs):
            raise ValidationError("Expense amounts cannot be negative")
        batch.status = ProductionBatchStatus.IN_PROGRESS
        batch.touch()
        self.calculate_costs(batch)
        return self._batch_repo.save(batch)

    def calculate_costs(self, batch: ProductionBatch) -> ProductionBatch:
        batch.material_cost = round(
            sum(
                float(line.total_cost or (line.qty * line.unit_cost))
                for line in batch.issues
            ),
            2,
        )
        batch.expense_cost = round(sum(float(line.amount) for line in batch.costs), 2)
        batch.total_cost = round(batch.material_cost + batch.expense_cost, 2)
        self._allocate_output_cost(batch)
        batch.expected_sales_value = round(
            sum(float(line.qty) * float(line.nrv_rate) for line in batch.outputs), 2
        )
        batch.batch_margin = round(
            batch.expected_sales_value - batch.total_cost, 2
        )
        return batch

    def validate_for_post(self, batch: ProductionBatch) -> None:
        if batch.status == ProductionBatchStatus.POSTED:
            raise ValidationError("Batch is already posted")
        if batch.status == ProductionBatchStatus.CANCELLED:
            raise ValidationError("Cancelled batch cannot be posted")
        if not batch.issues or not batch.outputs:
            raise ValidationError("Batch requires both material issues and outputs")
        if any(float(line.qty) <= 0 for line in batch.issues + batch.outputs):
            raise ValidationError("Issue and output quantities must be positive")
        if batch.total_cost < 0:
            raise ValidationError("Batch total cost cannot be negative")

    @staticmethod
    def add_cost(batch: ProductionBatch, cost: BatchCost) -> None:
        if not batch.is_editable:
            raise ValidationError("Batch is not editable")
        if float(cost.amount) < 0:
            raise ValidationError("Expense amount cannot be negative")
        batch.costs.append(cost)
        batch.touch()

    @staticmethod
    def remove_cost(batch: ProductionBatch, cost_id: str) -> None:
        if not batch.is_editable:
            raise ValidationError("Batch is not editable")
        batch.costs = [cost for cost in batch.costs if cost.id != cost_id]
        batch.touch()

    @staticmethod
    def complete_stage(
        batch: ProductionBatch, stage_id: str, *, notes: Optional[str] = None
    ) -> None:
        from vaybooks.bms.domain.shared.date_utils import utc_now

        if not batch.is_editable:
            raise ValidationError("Batch is not editable")
        stage = next((item for item in batch.stages if item.id == stage_id), None)
        if not stage:
            raise ValidationError("Production activity not found")
        stage.completed = True
        stage.completed_at = utc_now()
        if notes is not None:
            stage.notes = notes.strip()
        batch.status = ProductionBatchStatus.IN_PROGRESS
        batch.touch()

    def _allocate_output_cost(self, batch: ProductionBatch) -> None:
        outputs = batch.outputs
        if not outputs:
            return
        total_cost = float(batch.total_cost)
        weights: list[float]
        if batch.allocation_method == ProductionCostAllocationMethod.PERCENTAGE:
            weights = [max(0.0, float(line.allocation_pct)) for line in outputs]
        elif (
            batch.allocation_method
            == ProductionCostAllocationMethod.PRIMARY_ABSORBS_ALL
        ):
            primary_indexes = [
                index
                for index, line in enumerate(outputs)
                if line.role == ProductionOutputRole.MAIN
            ]
            primary = primary_indexes[0] if primary_indexes else 0
            weights = [1.0 if index == primary else 0.0 for index in range(len(outputs))]
        else:
            weights = [
                max(0.0, float(line.qty) * float(line.nrv_rate)) for line in outputs
            ]
            if sum(weights) <= 0:
                weights = [max(0.0, float(line.qty)) for line in outputs]
        denominator = sum(weights)
        if denominator <= 0:
            weights = [1.0 for _ in outputs]
            denominator = float(len(outputs))
        allocated = 0.0
        for index, line in enumerate(outputs):
            amount = (
                round(total_cost - allocated, 2)
                if index == len(outputs) - 1
                else round(total_cost * weights[index] / denominator, 2)
            )
            allocated += amount
            line.allocated_cost = amount
            line.unit_cost = round(amount / float(line.qty), 4) if line.qty else 0.0
