from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.subcontract import (
    ProjectSubcontractLine,
    ProjectSubcontractOrder,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectSubcontractStatus
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectSubcontractRepository:
    def __init__(self, db: Database):
        self._collection = db.project_subcontract_orders

    def _line_to_doc(self, line: ProjectSubcontractLine) -> dict:
        return {
            "id": line.id,
            "description": line.description,
            "quantity": float(line.quantity or 0.0),
            "rate": float(line.rate or 0.0),
            "unit": line.unit,
            "boq_item_id": line.boq_item_id,
            "measured_qty": float(line.measured_qty or 0.0),
            "certified_qty": float(line.certified_qty or 0.0),
            "settled_qty": float(line.settled_qty or 0.0),
        }

    def _line_from_doc(self, doc: dict) -> ProjectSubcontractLine:
        return ProjectSubcontractLine(
            id=doc.get("id", ""),
            description=doc.get("description", ""),
            quantity=float(doc.get("quantity") or 0.0),
            rate=float(doc.get("rate") or 0.0),
            unit=doc.get("unit", "Nos"),
            boq_item_id=doc.get("boq_item_id", ""),
            measured_qty=float(doc.get("measured_qty") or 0.0),
            certified_qty=float(doc.get("certified_qty") or 0.0),
            settled_qty=float(doc.get("settled_qty") or 0.0),
        )

    def _to_doc(self, order: ProjectSubcontractOrder) -> dict:
        return {
            "_id": order.id,
            "project_id": order.project_id,
            "order_number": order.order_number,
            "vendor_id": order.vendor_id,
            "vendor_name": order.vendor_name,
            "order_date": to_bson_value(order.order_date),
            "description": order.description,
            "retention_pct": float(order.retention_pct or 0.0),
            "lines": [self._line_to_doc(line) for line in order.lines],
            "status": order.status.value,
            "notes": order.notes,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectSubcontractOrder:
        return ProjectSubcontractOrder(
            id=doc["_id"],
            project_id=doc["project_id"],
            order_number=doc.get("order_number", ""),
            vendor_id=doc.get("vendor_id", ""),
            vendor_name=doc.get("vendor_name", ""),
            order_date=from_bson_date(doc["order_date"]),
            description=doc.get("description", ""),
            retention_pct=float(doc.get("retention_pct") or 0.0),
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            status=ProjectSubcontractStatus(
                doc.get("status", ProjectSubcontractStatus.DRAFT.value)
            ),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, order: ProjectSubcontractOrder) -> ProjectSubcontractOrder:
        order.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": order.id}, self._to_doc(order), upsert=True
        )
        return order

    def find_by_id(self, order_id: str) -> Optional[ProjectSubcontractOrder]:
        doc = self._collection.find_one({"_id": order_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectSubcontractOrder]:
        docs = self._collection.find({"project_id": project_id}).sort("order_date", -1)
        return [self._from_doc(d) for d in docs]
