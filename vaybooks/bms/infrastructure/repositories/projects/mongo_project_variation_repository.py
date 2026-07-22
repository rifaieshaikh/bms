from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectVariation
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectVariationRepository:
    def __init__(self, db: Database):
        self._collection = db.project_variations

    def _to_doc(self, variation: ProjectVariation) -> dict:
        return {
            "_id": variation.id,
            "project_id": variation.project_id,
            "variation_number": variation.variation_number,
            "variation_date": to_bson_value(variation.variation_date),
            "old_contract_value": float(variation.old_contract_value or 0.0),
            "new_contract_value": float(variation.new_contract_value or 0.0),
            "reason": variation.reason,
            "approved_by": variation.approved_by,
            "approved_at": variation.approved_at,
            "status": variation.status,
            "change_class": variation.change_class,
            "customer_sent": bool(variation.customer_sent),
            "customer_approved": bool(variation.customer_approved),
            "boq_impacts": list(variation.boq_impacts or []),
            "cost_impact": float(variation.cost_impact or 0.0),
            "margin_impact": float(variation.margin_impact or 0.0),
            "executed": bool(getattr(variation, "executed", True)),
            "created_at": variation.created_at,
        }

    def _from_doc(self, doc: dict) -> ProjectVariation:
        return ProjectVariation(
            id=doc["_id"],
            project_id=doc["project_id"],
            variation_number=doc.get("variation_number", ""),
            variation_date=from_bson_date(doc["variation_date"]),
            old_contract_value=float(doc.get("old_contract_value") or 0.0),
            new_contract_value=float(doc.get("new_contract_value") or 0.0),
            reason=doc.get("reason", ""),
            approved_by=doc.get("approved_by", ""),
            approved_at=doc.get("approved_at"),
            status=doc.get("status", "Draft"),
            change_class=doc.get("change_class", "Scope"),
            customer_sent=bool(doc.get("customer_sent", False)),
            customer_approved=bool(doc.get("customer_approved", False)),
            boq_impacts=list(doc.get("boq_impacts") or []),
            cost_impact=float(doc.get("cost_impact") or 0.0),
            margin_impact=float(doc.get("margin_impact") or 0.0),
            executed=bool(doc.get("executed", True)),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, variation: ProjectVariation) -> ProjectVariation:
        self._collection.replace_one(
            {"_id": variation.id}, self._to_doc(variation), upsert=True
        )
        return variation

    def find_by_id(self, variation_id: str) -> Optional[ProjectVariation]:
        doc = self._collection.find_one({"_id": variation_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectVariation]:
        docs = self._collection.find({"project_id": project_id}).sort(
            "variation_date", -1
        )
        return [self._from_doc(d) for d in docs]
