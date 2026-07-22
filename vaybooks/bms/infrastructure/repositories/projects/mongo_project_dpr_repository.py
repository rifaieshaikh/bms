from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.dpr import ProjectDpr, ProjectDprLine
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectDprStatus
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectDprRepository:
    def __init__(self, db: Database):
        self._collection = db.project_dprs

    def _line_to_doc(self, line: ProjectDprLine) -> dict:
        return {
            "id": line.id,
            "activity_id": line.activity_id,
            "quantity": float(line.quantity or 0.0),
            "hours": float(line.hours or 0.0),
            "labour_count": int(line.labour_count or 0),
            "notes": line.notes,
            "issues": line.issues,
        }

    def _line_from_doc(self, doc: dict) -> ProjectDprLine:
        return ProjectDprLine(
            id=doc.get("id", ""),
            activity_id=doc.get("activity_id", ""),
            quantity=float(doc.get("quantity") or 0.0),
            hours=float(doc.get("hours") or 0.0),
            labour_count=int(doc.get("labour_count") or 0),
            notes=doc.get("notes", ""),
            issues=doc.get("issues", ""),
        )

    def _to_doc(self, dpr: ProjectDpr) -> dict:
        return {
            "_id": dpr.id,
            "project_id": dpr.project_id,
            "report_date": to_bson_value(dpr.report_date),
            "weather": dpr.weather,
            "notes": dpr.notes,
            "lines": [self._line_to_doc(line) for line in dpr.lines],
            "photo_document_ids": list(dpr.photo_document_ids or []),
            "status": dpr.status.value,
            "applied": bool(dpr.applied),
            "idempotency_key": dpr.idempotency_key,
            "created_at": dpr.created_at,
            "updated_at": dpr.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectDpr:
        return ProjectDpr(
            id=doc["_id"],
            project_id=doc["project_id"],
            report_date=from_bson_date(doc["report_date"]),
            weather=doc.get("weather", ""),
            notes=doc.get("notes", ""),
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            photo_document_ids=list(doc.get("photo_document_ids") or []),
            status=ProjectDprStatus(doc.get("status", ProjectDprStatus.DRAFT.value)),
            applied=bool(doc.get("applied", False)),
            idempotency_key=doc.get("idempotency_key", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, dpr: ProjectDpr) -> ProjectDpr:
        dpr.updated_at = utc_now()
        self._collection.replace_one({"_id": dpr.id}, self._to_doc(dpr), upsert=True)
        return dpr

    def find_by_id(self, dpr_id: str) -> Optional[ProjectDpr]:
        doc = self._collection.find_one({"_id": dpr_id})
        return self._from_doc(doc) if doc else None

    def find_by_idempotency_key(self, key: str) -> Optional[ProjectDpr]:
        if not key:
            return None
        doc = self._collection.find_one({"idempotency_key": key})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectDpr]:
        docs = self._collection.find({"project_id": project_id}).sort("report_date", -1)
        return [self._from_doc(d) for d in docs]
