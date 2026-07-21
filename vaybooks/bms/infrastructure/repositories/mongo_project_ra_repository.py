from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.measurement import ProjectRABill, ProjectRABillLine
from vaybooks.bms.domain.shared.enums import ProjectRABillStatus
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectRABillRepository:
    _LEGACY_STATUS = {
        "Approved": ProjectRABillStatus.CERTIFIED,
        "Converted": ProjectRABillStatus.INVOICED,
    }

    def __init__(self, db: Database):
        self._collection = db.project_ra_bills

    @classmethod
    def _parse_status(cls, raw: str) -> ProjectRABillStatus:
        if raw in cls._LEGACY_STATUS:
            return cls._LEGACY_STATUS[raw]
        return ProjectRABillStatus(raw)

    def _line_to_doc(self, line: ProjectRABillLine) -> dict:
        return {
            "id": line.id,
            "boq_item_id": line.boq_item_id,
            "description": line.description,
            "unit": line.unit,
            "previous_qty": float(line.previous_qty or 0.0),
            "current_claimed_qty": float(line.current_claimed_qty or 0.0),
            "cumulative_claimed_qty": float(line.cumulative_claimed_qty or 0.0),
            "current_certified_qty": float(line.current_certified_qty or 0.0),
            "cumulative_certified_qty": float(line.cumulative_certified_qty or 0.0),
            "rate": float(line.rate or 0.0),
            "measurement_ids": list(line.measurement_ids or []),
        }

    def _line_from_doc(self, doc: dict) -> ProjectRABillLine:
        return ProjectRABillLine(
            id=doc.get("id", ""),
            boq_item_id=doc.get("boq_item_id", ""),
            description=doc.get("description", ""),
            unit=doc.get("unit", ""),
            previous_qty=float(doc.get("previous_qty") or 0.0),
            current_claimed_qty=float(doc.get("current_claimed_qty") or 0.0),
            cumulative_claimed_qty=float(doc.get("cumulative_claimed_qty") or 0.0),
            current_certified_qty=float(doc.get("current_certified_qty") or 0.0),
            cumulative_certified_qty=float(doc.get("cumulative_certified_qty") or 0.0),
            rate=float(doc.get("rate") or 0.0),
            measurement_ids=list(doc.get("measurement_ids") or []),
        )

    def _to_doc(self, ra_bill: ProjectRABill) -> dict:
        return {
            "_id": ra_bill.id,
            "project_id": ra_bill.project_id,
            "ra_number": ra_bill.ra_number,
            "ra_date": to_bson_value(ra_bill.ra_date),
            "status": ra_bill.status.value,
            "lines": [self._line_to_doc(line) for line in ra_bill.lines],
            "advance_recovery": float(ra_bill.advance_recovery or 0.0),
            "retention_pct": float(ra_bill.retention_pct or 0.0),
            "retention_amount_claimed": float(ra_bill.retention_amount_claimed or 0.0),
            "retention_amount_certified": float(
                ra_bill.retention_amount_certified or 0.0
            ),
            "tds_amount": float(ra_bill.tds_amount or 0.0),
            "other_deductions": float(ra_bill.other_deductions or 0.0),
            "description": ra_bill.description,
            "work_order_id": ra_bill.work_order_id,
            "invoice_voucher_id": ra_bill.invoice_voucher_id,
            "claimed_by": ra_bill.claimed_by,
            "certified_by": ra_bill.certified_by,
            "certified_at": ra_bill.certified_at,
            "created_at": ra_bill.created_at,
            "updated_at": ra_bill.updated_at,
        }

    def _lines_from_doc(self, doc: dict) -> List[ProjectRABillLine]:
        lines = [self._line_from_doc(line) for line in doc.get("lines", [])]
        if lines:
            return lines
        claim_amount = float(doc.get("claim_amount") or 0.0)
        if claim_amount <= 0:
            return []
        description = doc.get("description", "") or f"RA {doc.get('ra_number', '')}"
        return [
            ProjectRABillLine(
                boq_item_id="",
                description=description,
                current_claimed_qty=1.0,
                cumulative_claimed_qty=1.0,
                current_certified_qty=1.0,
                cumulative_certified_qty=1.0,
                rate=claim_amount,
            )
        ]

    def _from_doc(self, doc: dict) -> ProjectRABill:
        retention_amount = float(doc.get("retention_amount") or 0.0)
        return ProjectRABill(
            id=doc["_id"],
            project_id=doc["project_id"],
            ra_number=doc.get("ra_number", ""),
            ra_date=from_bson_date(doc["ra_date"]),
            status=self._parse_status(doc.get("status", ProjectRABillStatus.DRAFT.value)),
            lines=self._lines_from_doc(doc),
            advance_recovery=float(doc.get("advance_recovery") or 0.0),
            retention_pct=float(doc.get("retention_pct") or 0.0),
            retention_amount_claimed=float(
                doc.get("retention_amount_claimed", retention_amount) or 0.0
            ),
            retention_amount_certified=float(
                doc.get("retention_amount_certified", retention_amount) or 0.0
            ),
            tds_amount=float(doc.get("tds_amount") or 0.0),
            other_deductions=float(doc.get("other_deductions") or 0.0),
            description=doc.get("description", ""),
            work_order_id=doc.get("work_order_id", ""),
            invoice_voucher_id=doc.get("invoice_voucher_id", ""),
            claimed_by=doc.get("claimed_by", ""),
            certified_by=doc.get("certified_by", ""),
            certified_at=doc.get("certified_at"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, ra_bill: ProjectRABill) -> ProjectRABill:
        self._collection.replace_one(
            {"_id": ra_bill.id}, self._to_doc(ra_bill), upsert=True
        )
        return ra_bill

    def find_by_id(self, ra_id: str) -> Optional[ProjectRABill]:
        doc = self._collection.find_one({"_id": ra_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectRABill]:
        docs = self._collection.find({"project_id": project_id}).sort("ra_date", -1)
        return [self._from_doc(d) for d in docs]
