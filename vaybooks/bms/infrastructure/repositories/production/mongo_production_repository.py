from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Optional

from pymongo.database import Database

from vaybooks.bms.domain.production.entities import (
    BatchCost,
    BatchIssue,
    BatchOutput,
    BatchStage,
    ProductionBatch,
    ProductionPosting,
    ProductionSettings,
    Recipe,
    RecipeInput,
    RecipeOutput,
    RecipeStage,
)
from vaybooks.bms.domain.shared.enums import (
    ProductionBatchStatus,
    ProductionCostAllocationMethod,
    ProductionOutputRole,
)


def _value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, list):
        return [_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _value(item) for key, item in value.items()}
    return value


def _doc(entity: Any) -> dict:
    payload = _value(asdict(entity))
    payload["_id"] = payload.pop("id")
    return payload


def _date_value(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value or date.today()


class MongoRecipeRepository:
    def __init__(self, db: Database):
        self._collection = db.production_recipes

    @staticmethod
    def _from_doc(doc: dict) -> Recipe:
        return Recipe(
            id=doc["_id"],
            name=doc.get("name", ""),
            code=doc.get("code", ""),
            description=doc.get("description", ""),
            base_quantity=float(doc.get("base_quantity", 1) or 1),
            inputs=[RecipeInput(**line) for line in doc.get("inputs", [])],
            outputs=[
                RecipeOutput(
                    **{
                        **line,
                        "role": ProductionOutputRole(
                            line.get("role", ProductionOutputRole.MAIN.value)
                        ),
                    }
                )
                for line in doc.get("outputs", [])
            ],
            stages=[RecipeStage(**line) for line in doc.get("stages", [])],
            allocation_method=ProductionCostAllocationMethod(
                doc.get(
                    "allocation_method",
                    ProductionCostAllocationMethod.NRV.value,
                )
            ),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, recipe: Recipe) -> Recipe:
        self._collection.replace_one({"_id": recipe.id}, _doc(recipe), upsert=True)
        return recipe

    def find_by_id(self, recipe_id: str) -> Optional[Recipe]:
        doc = self._collection.find_one({"_id": recipe_id})
        return self._from_doc(doc) if doc else None

    def find_by_code(self, code: str) -> Optional[Recipe]:
        doc = self._collection.find_one({"code": (code or "").strip()})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = True) -> list[Recipe]:
        query = {"is_active": True} if active_only else {}
        return [
            self._from_doc(doc)
            for doc in self._collection.find(query).sort("name", 1)
        ]

    def delete(self, recipe_id: str) -> None:
        self._collection.delete_one({"_id": recipe_id})


class MongoProductionBatchRepository:
    def __init__(self, db: Database):
        self._collection = db.production_batches

    @staticmethod
    def _from_doc(doc: dict) -> ProductionBatch:
        posting_doc = doc.get("posting") or {}
        return ProductionBatch(
            id=doc["_id"],
            batch_number=doc.get("batch_number", ""),
            recipe_id=doc.get("recipe_id", ""),
            recipe_name=doc.get("recipe_name", ""),
            batch_date=_date_value(doc.get("batch_date")),
            location_id=doc.get("location_id", ""),
            planned_quantity=float(doc.get("planned_quantity", 1) or 1),
            status=ProductionBatchStatus(
                doc.get("status", ProductionBatchStatus.DRAFT.value)
            ),
            stages=[BatchStage(**line) for line in doc.get("stages", [])],
            issues=[BatchIssue(**line) for line in doc.get("issues", [])],
            outputs=[
                BatchOutput(
                    **{
                        **line,
                        "role": ProductionOutputRole(
                            line.get("role", ProductionOutputRole.MAIN.value)
                        ),
                    }
                )
                for line in doc.get("outputs", [])
            ],
            costs=[BatchCost(**line) for line in doc.get("costs", [])],
            allocation_method=ProductionCostAllocationMethod(
                doc.get(
                    "allocation_method",
                    ProductionCostAllocationMethod.NRV.value,
                )
            ),
            material_cost=float(doc.get("material_cost", 0) or 0),
            expense_cost=float(doc.get("expense_cost", 0) or 0),
            total_cost=float(doc.get("total_cost", 0) or 0),
            expected_sales_value=float(doc.get("expected_sales_value", 0) or 0),
            batch_margin=float(doc.get("batch_margin", 0) or 0),
            notes=doc.get("notes", ""),
            posting=ProductionPosting(**posting_doc),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, batch: ProductionBatch) -> ProductionBatch:
        self._collection.replace_one({"_id": batch.id}, _doc(batch), upsert=True)
        return batch

    def find_by_id(self, batch_id: str) -> Optional[ProductionBatch]:
        doc = self._collection.find_one({"_id": batch_id})
        return self._from_doc(doc) if doc else None

    def find_by_number(self, batch_number: str) -> Optional[ProductionBatch]:
        doc = self._collection.find_one(
            {"batch_number": (batch_number or "").strip()}
        )
        return self._from_doc(doc) if doc else None

    def list_all(
        self,
        status: Optional[ProductionBatchStatus] = None,
        location_filter: dict | None = None,
    ) -> list[ProductionBatch]:
        from vaybooks.bms.domain.identity.location_access import merge_mongo_filters

        query = {"status": status.value} if status else {}
        query = merge_mongo_filters(query, location_filter or {})
        return [
            self._from_doc(doc)
            for doc in self._collection.find(query).sort("batch_date", -1)
        ]

    def delete(self, batch_id: str) -> None:
        self._collection.delete_one({"_id": batch_id})


class MongoProductionSettingsRepository:
    def __init__(self, db: Database):
        self._collection = db.production_settings

    def get(self) -> ProductionSettings:
        doc = self._collection.find_one({"_id": "default"})
        if not doc:
            return ProductionSettings()
        return ProductionSettings(
            id=doc["_id"],
            wip_account_id=doc.get("wip_account_id", ""),
            raw_material_account_id=doc.get("raw_material_account_id", ""),
            finished_goods_account_id=doc.get("finished_goods_account_id", ""),
            manufacturing_overhead_account_id=doc.get(
                "manufacturing_overhead_account_id", ""
            ),
            expense_clearing_account_id=doc.get("expense_clearing_account_id", ""),
            scrap_account_id=doc.get("scrap_account_id", ""),
            default_allocation_method=ProductionCostAllocationMethod(
                doc.get(
                    "default_allocation_method",
                    ProductionCostAllocationMethod.NRV.value,
                )
            ),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, settings: ProductionSettings) -> ProductionSettings:
        self._collection.replace_one(
            {"_id": settings.id}, _doc(settings), upsert=True
        )
        return settings
