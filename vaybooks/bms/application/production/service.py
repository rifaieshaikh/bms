from __future__ import annotations

from datetime import date
from typing import Any, Optional

from vaybooks.bms.domain.production.entities import (
    BatchCost,
    ProductionBatch,
    ProductionSettings,
    Recipe,
)
from vaybooks.bms.domain.production.repository import (
    ProductionBatchRepository,
    ProductionSettingsRepository,
    RecipeRepository,
)
from vaybooks.bms.domain.production.services import ProductionDomainService
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProductionBatchStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProductionAppService:
    def __init__(
        self,
        recipe_repo: RecipeRepository,
        batch_repo: ProductionBatchRepository,
        settings_repo: ProductionSettingsRepository,
        inventory_service: Any,
        accounting_service: Any,
    ) -> None:
        self._recipe_repo = recipe_repo
        self._batch_repo = batch_repo
        self._settings_repo = settings_repo
        self._inventory = inventory_service
        self._accounting = accounting_service
        self._domain = ProductionDomainService(recipe_repo, batch_repo)

    def list_recipes(self, active_only: bool = False) -> list[Recipe]:
        return self._recipe_repo.list_all(active_only=active_only)

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        return self._recipe_repo.find_by_id(recipe_id)

    def save_recipe(self, recipe: Recipe) -> Recipe:
        return self._domain.save_recipe(recipe)

    def delete_recipe(self, recipe_id: str) -> None:
        if any(batch.recipe_id == recipe_id for batch in self._batch_repo.list_all()):
            raise ValidationError("Recipe is used by production batches")
        self._recipe_repo.delete(recipe_id)

    def list_batches(
        self, status: Optional[ProductionBatchStatus] = None
    ) -> list[ProductionBatch]:
        return self._batch_repo.list_all(status)

    def get_batch(self, batch_id: str) -> Optional[ProductionBatch]:
        return self._batch_repo.find_by_id(batch_id)

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
        return self._domain.create_batch(
            batch_number=batch_number,
            recipe_id=recipe_id,
            batch_date=batch_date,
            location_id=location_id,
            planned_quantity=planned_quantity,
            notes=notes,
        )

    def save_batch(self, batch: ProductionBatch) -> ProductionBatch:
        self._snapshot_issue_costs(batch)
        return self._domain.save_batch(batch)

    def add_cost(self, batch_id: str, cost: BatchCost) -> ProductionBatch:
        batch = self._required_batch(batch_id)
        self._domain.add_cost(batch, cost)
        self._snapshot_issue_costs(batch)
        self._domain.calculate_costs(batch)
        return self._batch_repo.save(batch)

    def remove_cost(self, batch_id: str, cost_id: str) -> ProductionBatch:
        batch = self._required_batch(batch_id)
        self._domain.remove_cost(batch, cost_id)
        self._domain.calculate_costs(batch)
        return self._batch_repo.save(batch)

    def complete_stage(
        self, batch_id: str, stage_id: str, notes: Optional[str] = None
    ) -> ProductionBatch:
        batch = self._required_batch(batch_id)
        self._domain.complete_stage(batch, stage_id, notes=notes)
        return self._batch_repo.save(batch)

    def get_settings(self) -> ProductionSettings:
        return self._settings_repo.get()

    def save_settings(self, settings: ProductionSettings) -> ProductionSettings:
        settings.updated_at = utc_now()
        return self._settings_repo.save(settings)

    def post_batch(self, batch_id: str, posted_by: str = "") -> ProductionBatch:
        batch = self._required_batch(batch_id)
        self._snapshot_issue_costs(batch)
        self._domain.calculate_costs(batch)
        self._domain.validate_for_post(batch)
        self._validate_stock(batch)
        settings = self._settings_repo.get()
        journal_specs = self._journal_specs(batch, settings)

        issue_lines = [
            {
                "product_id": line.product_id,
                "qty": line.qty,
                "location_id": line.location_id or batch.location_id,
                "description": f"Production issue {batch.batch_number}",
            }
            for line in batch.issues
        ]
        output_lines = [
            {
                "product_id": line.product_id,
                "qty": line.qty,
                "location_id": line.location_id or batch.location_id,
                "description": f"Production receipt {batch.batch_number}",
            }
            for line in batch.outputs
        ]

        movements = []
        vouchers = []
        try:
            movements.extend(
                self._inventory.apply_production_issue(
                    batch.id, issue_lines, batch.batch_date
                )
            )
            movements.extend(
                self._inventory.apply_production_receive(
                    batch.id, output_lines, batch.batch_date
                )
            )
            self._inventory.apply_landed_cost(
                [
                    {
                        "product_id": line.product_id,
                        "qty": line.qty,
                        "unit_cost": line.unit_cost,
                    }
                    for line in batch.outputs
                ]
            )
            for description, lines in journal_specs:
                vouchers.append(
                    self._accounting.create_journal_entry(
                        description=description,
                        lines=lines,
                        voucher_date=batch.batch_date,
                        reference_production_batch_id=batch.id,
                    )
                )
        except Exception:
            if movements:
                self._inventory.reverse_movements_by_reference(batch.id)
            raise

        batch.posting.movement_ids = [movement.id for movement in movements]
        batch.posting.voucher_ids = [voucher.id for voucher in vouchers]
        batch.posting.posted_at = utc_now()
        batch.posting.posted_by = posted_by
        batch.status = ProductionBatchStatus.POSTED
        batch.touch()
        return self._batch_repo.save(batch)

    def cancel_batch(self, batch_id: str) -> ProductionBatch:
        batch = self._required_batch(batch_id)
        if batch.status == ProductionBatchStatus.POSTED:
            raise ValidationError("Posted batches cannot be cancelled")
        batch.status = ProductionBatchStatus.CANCELLED
        batch.touch()
        return self._batch_repo.save(batch)

    def dashboard_summary(self) -> dict[str, Any]:
        batches = self._batch_repo.list_all()
        posted = [
            batch for batch in batches if batch.status == ProductionBatchStatus.POSTED
        ]
        open_batches = [
            batch
            for batch in batches
            if batch.status
            in {ProductionBatchStatus.DRAFT, ProductionBatchStatus.IN_PROGRESS}
        ]
        return {
            "total_batches": len(batches),
            "open_batches": len(open_batches),
            "posted_batches": len(posted),
            "wip_value": round(sum(batch.total_cost for batch in open_batches), 2),
            "output_value": round(
                sum(batch.expected_sales_value for batch in posted), 2
            ),
            "margin": round(sum(batch.batch_margin for batch in posted), 2),
        }

    def day_book(self, start: date, end: date) -> list[dict[str, Any]]:
        rows = []
        for batch in self._batch_repo.list_all():
            if start <= batch.batch_date <= end:
                rows.append(
                    {
                        "date": batch.batch_date,
                        "type": "Production Batch",
                        "number": batch.batch_number,
                        "description": batch.recipe_name,
                        "status": batch.status.value,
                        "debit": batch.total_cost if batch.status.value == "Posted" else 0,
                        "credit": batch.total_cost if batch.status.value == "Posted" else 0,
                        "reference_id": batch.id,
                    }
                )
        list_vouchers = getattr(self._accounting, "list_vouchers", None)
        if list_vouchers:
            for voucher in list_vouchers():
                voucher_date = voucher.voucher_date.date()
                if start <= voucher_date <= end:
                    rows.append(
                        {
                            "date": voucher_date,
                            "type": voucher.voucher_type.value,
                            "number": voucher.voucher_number,
                            "description": voucher.description,
                            "status": "Posted",
                            "debit": voucher.total_debit,
                            "credit": voucher.total_credit,
                            "reference_id": voucher.id,
                        }
                    )
        return sorted(rows, key=lambda row: (row["date"], row["number"]), reverse=True)

    def _required_batch(self, batch_id: str) -> ProductionBatch:
        batch = self._batch_repo.find_by_id(batch_id)
        if not batch:
            raise ValidationError("Production batch not found")
        return batch

    def _snapshot_issue_costs(self, batch: ProductionBatch) -> None:
        for issue in batch.issues:
            product = self._inventory.get_product(issue.product_id)
            if not product:
                raise ValidationError(f"Product not found: {issue.product_id}")
            issue.product_name = issue.product_name or product.name
            issue.unit = issue.unit or product.unit
            issue.unit_cost = round(float(product.weighted_avg_cost or 0), 4)
            issue.total_cost = round(float(issue.qty) * issue.unit_cost, 2)
        for output in batch.outputs:
            product = self._inventory.get_product(output.product_id)
            if not product:
                raise ValidationError(f"Product not found: {output.product_id}")
            output.product_name = output.product_name or product.name
            output.unit = output.unit or product.unit
            if not output.nrv_rate:
                output.nrv_rate = float(product.selling_rate or 0)

    def _validate_stock(self, batch: ProductionBatch) -> None:
        for issue in batch.issues:
            product = self._inventory.get_product(issue.product_id)
            available = (
                self._inventory.get_stock_balance(
                    issue.product_id, issue.location_id or batch.location_id
                )
                if issue.location_id or batch.location_id
                else float(product.current_qty if product else 0)
            )
            if available < float(issue.qty) - 0.001:
                raise ValidationError(
                    f"Insufficient stock for {issue.product_name or issue.product_id} "
                    f"(available {available:g}, need {issue.qty:g})"
                )

    def _account(self, account_id: str, label: str):
        if not account_id:
            raise ValidationError(f"{label} account is not configured")
        account = self._accounting.get_account(account_id)
        if not account:
            raise ValidationError(f"{label} account not found")
        return account

    def _journal_specs(
        self, batch: ProductionBatch, settings: ProductionSettings
    ) -> list[tuple[str, list[dict]]]:
        if batch.total_cost <= 0:
            return []
        wip = self._account(settings.wip_account_id, "WIP")
        raw = self._account(settings.raw_material_account_id, "Raw material")
        fg = self._account(settings.finished_goods_account_id, "Finished goods")
        specs: list[tuple[str, list[dict]]] = []
        if batch.material_cost > 0:
            specs.append(
                (
                    f"Production material issue {batch.batch_number}",
                    [
                        {
                            "account_id": wip.id,
                            "account_name": wip.account_name,
                            "debit_amount": batch.material_cost,
                        },
                        {
                            "account_id": raw.id,
                            "account_name": raw.account_name,
                            "credit_amount": batch.material_cost,
                        },
                    ],
                )
            )
        if batch.expense_cost > 0:
            clearing = self._account(
                settings.expense_clearing_account_id, "Expense clearing"
            )
            credits: dict[str, dict] = {}
            for cost in batch.costs:
                account = (
                    self._account(cost.account_id, "Production expense")
                    if cost.account_id
                    else clearing
                )
                line = credits.setdefault(
                    account.id,
                    {
                        "account_id": account.id,
                        "account_name": account.account_name,
                        "credit_amount": 0.0,
                    },
                )
                line["credit_amount"] = round(
                    float(line["credit_amount"]) + float(cost.amount), 2
                )
            specs.append(
                (
                    f"Production expenses {batch.batch_number}",
                    [
                        {
                            "account_id": wip.id,
                            "account_name": wip.account_name,
                            "debit_amount": batch.expense_cost,
                        },
                        *credits.values(),
                    ],
                )
            )
        specs.append(
            (
                f"Production completion {batch.batch_number}",
                [
                    {
                        "account_id": fg.id,
                        "account_name": fg.account_name,
                        "debit_amount": batch.total_cost,
                    },
                    {
                        "account_id": wip.id,
                        "account_name": wip.account_name,
                        "credit_amount": batch.total_cost,
                    },
                ],
            )
        )
        return specs
