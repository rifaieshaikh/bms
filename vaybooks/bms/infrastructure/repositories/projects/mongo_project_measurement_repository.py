from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.measurement import ProjectMeasurement
from vaybooks.bms.domain.shared.enums import ProjectMeasurementStatus
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectMeasurementRepository:
    def __init__(self, db: Database):
        self._collection = db.project_measurements

    def _to_doc(self, measurement: ProjectMeasurement) -> dict:
        return {
            "_id": measurement.id,
            "project_id": measurement.project_id,
            "boq_item_id": measurement.boq_item_id,
            "measurement_date": to_bson_value(measurement.measurement_date),
            "location": measurement.location,
            "dimensions": measurement.dimensions,
            "quantity": float(measurement.quantity or 0.0),
            "cumulative_quantity": float(measurement.cumulative_quantity or 0.0),
            "status": measurement.status.value,
            "override_qty_cap": measurement.override_qty_cap,
            "override_reason": measurement.override_reason,
            "ra_bill_id": measurement.ra_bill_id,
            "notes": measurement.notes,
            "verified_by": measurement.verified_by,
            "certified_by": measurement.certified_by,
            "created_at": measurement.created_at,
            "updated_at": measurement.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectMeasurement:
        return ProjectMeasurement(
            id=doc["_id"],
            project_id=doc["project_id"],
            boq_item_id=doc.get("boq_item_id", ""),
            measurement_date=from_bson_date(doc["measurement_date"]),
            location=doc.get("location", ""),
            dimensions=doc.get("dimensions", ""),
            quantity=float(doc.get("quantity") or 0.0),
            cumulative_quantity=float(doc.get("cumulative_quantity") or 0.0),
            status=ProjectMeasurementStatus(
                doc.get("status", ProjectMeasurementStatus.DRAFT.value)
            ),
            override_qty_cap=bool(doc.get("override_qty_cap", False)),
            override_reason=doc.get("override_reason", ""),
            ra_bill_id=doc.get("ra_bill_id", ""),
            notes=doc.get("notes", ""),
            verified_by=doc.get("verified_by", ""),
            certified_by=doc.get("certified_by", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, measurement: ProjectMeasurement) -> ProjectMeasurement:
        self._collection.replace_one(
            {"_id": measurement.id}, self._to_doc(measurement), upsert=True
        )
        return measurement

    def find_by_id(self, measurement_id: str) -> Optional[ProjectMeasurement]:
        doc = self._collection.find_one({"_id": measurement_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectMeasurement]:
        docs = self._collection.find({"project_id": project_id}).sort(
            "measurement_date", -1
        )
        return [self._from_doc(d) for d in docs]

    def list_by_boq_item(self, boq_item_id: str) -> List[ProjectMeasurement]:
        docs = self._collection.find({"boq_item_id": boq_item_id}).sort(
            "measurement_date", -1
        )
        return [self._from_doc(d) for d in docs]

    def delete(self, measurement_id: str) -> None:
        self._collection.delete_one({"_id": measurement_id})
