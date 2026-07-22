from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectWorkOrder
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectWorkOrderRepository:
    def __init__(self, db: Database):
        self._collection = db.project_work_orders

    def _to_doc(self, work_order: ProjectWorkOrder) -> dict:
        return {
            "_id": work_order.id,
            "project_id": work_order.project_id,
            "wo_number": work_order.wo_number,
            "wo_date": to_bson_value(work_order.wo_date),
            "description": work_order.description,
            "quotation_id": work_order.quotation_id,
            "status": work_order.status,
            "created_at": work_order.created_at,
        }

    def _from_doc(self, doc: dict) -> ProjectWorkOrder:
        return ProjectWorkOrder(
            id=doc["_id"],
            project_id=doc["project_id"],
            wo_number=doc.get("wo_number", ""),
            wo_date=from_bson_date(doc["wo_date"]),
            description=doc.get("description", ""),
            quotation_id=doc.get("quotation_id", ""),
            status=doc.get("status", "Draft"),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, work_order: ProjectWorkOrder) -> ProjectWorkOrder:
        self._collection.replace_one(
            {"_id": work_order.id}, self._to_doc(work_order), upsert=True
        )
        return work_order

    def find_by_id(self, wo_id: str) -> Optional[ProjectWorkOrder]:
        doc = self._collection.find_one({"_id": wo_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectWorkOrder]:
        docs = self._collection.find({"project_id": project_id}).sort("wo_date", -1)
        return [self._from_doc(d) for d in docs]
