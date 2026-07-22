from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.boq import ProjectBoqItem
from vaybooks.bms.domain.shared.enums import ProjectBoqItemType


class MongoProjectBoqRepository:
    def __init__(self, db: Database):
        self._collection = db.project_boq_items

    def _to_doc(self, item: ProjectBoqItem) -> dict:
        return {
            "_id": item.id,
            "project_id": item.project_id,
            "code": item.code,
            "description": item.description,
            "item_type": item.item_type.value,
            "parent_id": item.parent_id,
            "unit": item.unit,
            "sort_order": int(item.sort_order or 0),
            "estimated_qty": float(item.estimated_qty or 0.0),
            "material_cost": float(item.material_cost or 0.0),
            "labour_cost": float(item.labour_cost or 0.0),
            "equipment_cost": float(item.equipment_cost or 0.0),
            "subcon_cost": float(item.subcon_cost or 0.0),
            "overhead_cost": float(item.overhead_cost or 0.0),
            "contingency_cost": float(item.contingency_cost or 0.0),
            "selling_rate": float(item.selling_rate or 0.0),
            "hsn_sac": item.hsn_sac,
            "contracted_qty": float(item.contracted_qty or 0.0),
            "contracted_rate": float(item.contracted_rate or 0.0),
            "varied_qty": float(item.varied_qty or 0.0),
            "executed_qty": float(item.executed_qty or 0.0),
            "measured_qty": float(item.measured_qty or 0.0),
            "certified_qty": float(item.certified_qty or 0.0),
            "billed_qty": float(item.billed_qty or 0.0),
            "rate_override_reason": item.rate_override_reason,
            "activity_id": item.activity_id,
            "phase_id": item.phase_id,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectBoqItem:
        return ProjectBoqItem(
            id=doc["_id"],
            project_id=doc["project_id"],
            code=doc.get("code", ""),
            description=doc.get("description", ""),
            item_type=ProjectBoqItemType(
                doc.get("item_type", ProjectBoqItemType.ITEM.value)
            ),
            parent_id=doc.get("parent_id"),
            unit=doc.get("unit", "Nos"),
            sort_order=int(doc.get("sort_order") or 0),
            estimated_qty=float(doc.get("estimated_qty") or 0.0),
            material_cost=float(doc.get("material_cost") or 0.0),
            labour_cost=float(doc.get("labour_cost") or 0.0),
            equipment_cost=float(doc.get("equipment_cost") or 0.0),
            subcon_cost=float(doc.get("subcon_cost") or 0.0),
            overhead_cost=float(doc.get("overhead_cost") or 0.0),
            contingency_cost=float(doc.get("contingency_cost") or 0.0),
            selling_rate=float(doc.get("selling_rate") or 0.0),
            hsn_sac=doc.get("hsn_sac", ""),
            contracted_qty=float(doc.get("contracted_qty") or 0.0),
            contracted_rate=float(doc.get("contracted_rate") or 0.0),
            varied_qty=float(doc.get("varied_qty") or 0.0),
            executed_qty=float(doc.get("executed_qty") or 0.0),
            measured_qty=float(doc.get("measured_qty") or 0.0),
            certified_qty=float(doc.get("certified_qty") or 0.0),
            billed_qty=float(doc.get("billed_qty") or 0.0),
            rate_override_reason=doc.get("rate_override_reason", ""),
            activity_id=doc.get("activity_id"),
            phase_id=doc.get("phase_id"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, item: ProjectBoqItem) -> ProjectBoqItem:
        self._collection.replace_one({"_id": item.id}, self._to_doc(item), upsert=True)
        return item

    def save_many(self, items: List[ProjectBoqItem]) -> List[ProjectBoqItem]:
        for item in items:
            self.save(item)
        return items

    def find_by_id(self, item_id: str) -> Optional[ProjectBoqItem]:
        doc = self._collection.find_one({"_id": item_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectBoqItem]:
        docs = self._collection.find({"project_id": project_id}).sort(
            [("sort_order", 1), ("code", 1)]
        )
        return [self._from_doc(d) for d in docs]

    def delete(self, item_id: str) -> None:
        self._collection.delete_one({"_id": item_id})
