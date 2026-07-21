from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectCostTransfer


class MongoProjectCostTransferRepository:
    def __init__(self, db: Database):
        self._collection = db.project_cost_transfers

    def _to_doc(self, transfer: ProjectCostTransfer) -> dict:
        return {
            "_id": transfer.id,
            "from_project_id": transfer.from_project_id,
            "to_project_id": transfer.to_project_id,
            "amount": float(transfer.amount or 0.0),
            "reason": transfer.reason,
            "from_activity_id": transfer.from_activity_id,
            "to_activity_id": transfer.to_activity_id,
            "transferred_by": transfer.transferred_by,
            "created_at": transfer.created_at,
        }

    def _from_doc(self, doc: dict) -> ProjectCostTransfer:
        return ProjectCostTransfer(
            id=doc["_id"],
            from_project_id=doc["from_project_id"],
            to_project_id=doc["to_project_id"],
            amount=float(doc.get("amount") or 0.0),
            reason=doc.get("reason", ""),
            from_activity_id=doc.get("from_activity_id", ""),
            to_activity_id=doc.get("to_activity_id", ""),
            transferred_by=doc.get("transferred_by", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, transfer: ProjectCostTransfer) -> ProjectCostTransfer:
        self._collection.replace_one(
            {"_id": transfer.id}, self._to_doc(transfer), upsert=True
        )
        return transfer

    def find_by_id(self, transfer_id: str) -> Optional[ProjectCostTransfer]:
        doc = self._collection.find_one({"_id": transfer_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectCostTransfer]:
        docs = self._collection.find(
            {"$or": [{"from_project_id": project_id}, {"to_project_id": project_id}]}
        ).sort("created_at", -1)
        return [self._from_doc(d) for d in docs]
