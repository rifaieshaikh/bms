from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.cash_flow import ProjectCashFlowPlan
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectCashFlowRepository:
    def __init__(self, db: Database):
        self._collection = db.project_cash_flow_plans

    def _to_doc(self, plan: ProjectCashFlowPlan) -> dict:
        return {
            "_id": plan.id,
            "project_id": plan.project_id,
            "period_start": to_bson_value(plan.period_start),
            "period_end": to_bson_value(plan.period_end),
            "cash_in_planned": float(plan.cash_in_planned or 0.0),
            "cash_out_planned": float(plan.cash_out_planned or 0.0),
            "notes": plan.notes,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectCashFlowPlan:
        return ProjectCashFlowPlan(
            id=doc["_id"],
            project_id=doc["project_id"],
            period_start=from_bson_date(doc["period_start"]),
            period_end=from_bson_date(doc["period_end"]),
            cash_in_planned=float(doc.get("cash_in_planned") or 0.0),
            cash_out_planned=float(doc.get("cash_out_planned") or 0.0),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, plan: ProjectCashFlowPlan) -> ProjectCashFlowPlan:
        plan.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": plan.id}, self._to_doc(plan), upsert=True
        )
        return plan

    def find_by_id(self, plan_id: str) -> Optional[ProjectCashFlowPlan]:
        doc = self._collection.find_one({"_id": plan_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectCashFlowPlan]:
        docs = self._collection.find({"project_id": project_id}).sort(
            "period_start", 1
        )
        return [self._from_doc(d) for d in docs]
