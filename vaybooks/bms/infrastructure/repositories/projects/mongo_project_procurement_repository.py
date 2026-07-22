from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.procurement import (
    ProjectMaterialRequest,
    ProjectMaterialRequestLine,
    ProjectRfq,
    ProjectRfqQuote,
    ProjectSiteStockMovement,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectMaterialOwnership,
    ProjectMaterialRequestStatus,
    ProjectRfqStatus,
    ProjectStockMovementType,
)
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectProcurementRepository:
    def __init__(self, db: Database):
        self._mrs = db.project_material_requests
        self._rfqs = db.project_rfqs
        self._movements = db.project_site_stock_movements

    def _mr_line_to_doc(self, line: ProjectMaterialRequestLine) -> dict:
        return {
            "id": line.id,
            "description": line.description,
            "quantity": float(line.quantity or 0.0),
            "unit": line.unit,
            "activity_id": line.activity_id,
            "boq_item_id": line.boq_item_id,
        }

    def _mr_line_from_doc(self, doc: dict) -> ProjectMaterialRequestLine:
        return ProjectMaterialRequestLine(
            id=doc.get("id", ""),
            description=doc.get("description", ""),
            quantity=float(doc.get("quantity") or 0.0),
            unit=doc.get("unit", "Nos"),
            activity_id=doc.get("activity_id", ""),
            boq_item_id=doc.get("boq_item_id", ""),
        )

    def _mr_to_doc(self, mr: ProjectMaterialRequest) -> dict:
        return {
            "_id": mr.id,
            "project_id": mr.project_id,
            "request_number": mr.request_number,
            "need_by": to_bson_value(mr.need_by),
            "lines": [self._mr_line_to_doc(line) for line in mr.lines],
            "status": mr.status.value,
            "notes": mr.notes,
            "po_id": mr.po_id,
            "invoice_party": getattr(mr, "invoice_party", "Contractor") or "Contractor",
            "principal_agent": getattr(mr, "principal_agent", "Principal")
            or "Principal",
            "created_at": mr.created_at,
            "updated_at": mr.updated_at,
        }

    def _mr_from_doc(self, doc: dict) -> ProjectMaterialRequest:
        return ProjectMaterialRequest(
            id=doc["_id"],
            project_id=doc["project_id"],
            request_number=doc.get("request_number", ""),
            need_by=from_bson_date(doc.get("need_by")),
            lines=[self._mr_line_from_doc(line) for line in doc.get("lines", [])],
            status=ProjectMaterialRequestStatus(
                doc.get("status", ProjectMaterialRequestStatus.DRAFT.value)
            ),
            notes=doc.get("notes", ""),
            po_id=doc.get("po_id", ""),
            invoice_party=doc.get("invoice_party", "Contractor") or "Contractor",
            principal_agent=doc.get("principal_agent", "Principal") or "Principal",
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def _quote_to_doc(self, quote: ProjectRfqQuote) -> dict:
        return {
            "id": quote.id,
            "vendor_id": quote.vendor_id,
            "vendor_name": quote.vendor_name,
            "unit_price": float(quote.unit_price or 0.0),
            "lead_time_days": int(quote.lead_time_days or 0),
            "notes": quote.notes,
        }

    def _quote_from_doc(self, doc: dict) -> ProjectRfqQuote:
        return ProjectRfqQuote(
            id=doc.get("id", ""),
            vendor_id=doc.get("vendor_id", ""),
            vendor_name=doc.get("vendor_name", ""),
            unit_price=float(doc.get("unit_price") or 0.0),
            lead_time_days=int(doc.get("lead_time_days") or 0),
            notes=doc.get("notes", ""),
        )

    def _rfq_to_doc(self, rfq: ProjectRfq) -> dict:
        return {
            "_id": rfq.id,
            "project_id": rfq.project_id,
            "rfq_number": rfq.rfq_number,
            "description": rfq.description,
            "quantity": float(rfq.quantity or 0.0),
            "unit": rfq.unit,
            "material_request_id": rfq.material_request_id,
            "quotes": [self._quote_to_doc(q) for q in rfq.quotes],
            "awarded_quote_id": rfq.awarded_quote_id,
            "po_id": rfq.po_id,
            "status": rfq.status.value,
            "created_at": rfq.created_at,
            "updated_at": rfq.updated_at,
        }

    def _rfq_from_doc(self, doc: dict) -> ProjectRfq:
        return ProjectRfq(
            id=doc["_id"],
            project_id=doc["project_id"],
            rfq_number=doc.get("rfq_number", ""),
            description=doc.get("description", ""),
            quantity=float(doc.get("quantity") or 0.0),
            unit=doc.get("unit", "Nos"),
            material_request_id=doc.get("material_request_id", ""),
            quotes=[self._quote_from_doc(q) for q in doc.get("quotes", [])],
            awarded_quote_id=doc.get("awarded_quote_id", ""),
            po_id=doc.get("po_id", ""),
            status=ProjectRfqStatus(doc.get("status", ProjectRfqStatus.DRAFT.value)),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def _movement_to_doc(self, movement: ProjectSiteStockMovement) -> dict:
        return {
            "_id": movement.id,
            "project_id": movement.project_id,
            "movement_type": movement.movement_type.value,
            "description": movement.description,
            "quantity": float(movement.quantity or 0.0),
            "unit": movement.unit,
            "unit_cost": float(movement.unit_cost or 0.0),
            "activity_id": movement.activity_id,
            "boq_item_id": movement.boq_item_id,
            "ownership": movement.ownership.value,
            "invoice_party": getattr(movement, "invoice_party", "Contractor")
            or "Contractor",
            "principal_agent": getattr(movement, "principal_agent", "Principal")
            or "Principal",
            "source_ref_type": movement.source_ref_type,
            "source_ref_id": movement.source_ref_id,
            "notes": movement.notes,
            "created_at": movement.created_at,
        }

    def _movement_from_doc(self, doc: dict) -> ProjectSiteStockMovement:
        return ProjectSiteStockMovement(
            id=doc["_id"],
            project_id=doc["project_id"],
            movement_type=ProjectStockMovementType(doc["movement_type"]),
            description=doc.get("description", ""),
            quantity=float(doc.get("quantity") or 0.0),
            unit=doc.get("unit", "Nos"),
            unit_cost=float(doc.get("unit_cost") or 0.0),
            activity_id=doc.get("activity_id", ""),
            boq_item_id=doc.get("boq_item_id", ""),
            ownership=ProjectMaterialOwnership(
                doc.get("ownership", ProjectMaterialOwnership.CONTRACTOR.value)
            ),
            invoice_party=doc.get("invoice_party", "Contractor") or "Contractor",
            principal_agent=doc.get("principal_agent", "Principal") or "Principal",
            source_ref_type=doc.get("source_ref_type", ""),
            source_ref_id=doc.get("source_ref_id", ""),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save_material_request(
        self, mr: ProjectMaterialRequest
    ) -> ProjectMaterialRequest:
        mr.updated_at = utc_now()
        self._mrs.replace_one({"_id": mr.id}, self._mr_to_doc(mr), upsert=True)
        return mr

    def find_material_request_by_id(
        self, mr_id: str
    ) -> Optional[ProjectMaterialRequest]:
        doc = self._mrs.find_one({"_id": mr_id})
        return self._mr_from_doc(doc) if doc else None

    def list_material_requests_by_project(
        self, project_id: str
    ) -> List[ProjectMaterialRequest]:
        docs = self._mrs.find({"project_id": project_id}).sort("created_at", -1)
        return [self._mr_from_doc(d) for d in docs]

    def save_rfq(self, rfq: ProjectRfq) -> ProjectRfq:
        rfq.updated_at = utc_now()
        self._rfqs.replace_one({"_id": rfq.id}, self._rfq_to_doc(rfq), upsert=True)
        return rfq

    def find_rfq_by_id(self, rfq_id: str) -> Optional[ProjectRfq]:
        doc = self._rfqs.find_one({"_id": rfq_id})
        return self._rfq_from_doc(doc) if doc else None

    def list_rfqs_by_project(self, project_id: str) -> List[ProjectRfq]:
        docs = self._rfqs.find({"project_id": project_id}).sort("created_at", -1)
        return [self._rfq_from_doc(d) for d in docs]

    def save_stock_movement(
        self, movement: ProjectSiteStockMovement
    ) -> ProjectSiteStockMovement:
        self._movements.replace_one(
            {"_id": movement.id}, self._movement_to_doc(movement), upsert=True
        )
        return movement

    def find_stock_movement_by_id(
        self, movement_id: str
    ) -> Optional[ProjectSiteStockMovement]:
        doc = self._movements.find_one({"_id": movement_id})
        return self._movement_from_doc(doc) if doc else None

    def list_stock_movements_by_project(
        self, project_id: str
    ) -> List[ProjectSiteStockMovement]:
        docs = self._movements.find({"project_id": project_id}).sort("created_at", -1)
        return [self._movement_from_doc(d) for d in docs]
