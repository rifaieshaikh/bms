from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.recognition import (
    ProjectReconcileException,
    ProjectRecognitionEntry,
    ProjectReconciliation,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectRecognitionMethod,
    ProjectRecognitionStatus,
    ProjectReconcileStatus,
)
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectRecognitionRepository:
    def __init__(self, db: Database):
        self._entries = db.project_recognition_entries
        self._reconciliations = db.project_reconciliations

    def _entry_to_doc(self, entry: ProjectRecognitionEntry) -> dict:
        return {
            "_id": entry.id,
            "project_id": entry.project_id,
            "period_end": to_bson_value(entry.period_end),
            "method": entry.method.value,
            "percent_complete": float(entry.percent_complete or 0.0),
            "total_cost": float(entry.total_cost or 0.0),
            "billed_to_date": float(entry.billed_to_date or 0.0),
            "prior_recognised": float(entry.prior_recognised or 0.0),
            "current_recognised": float(entry.current_recognised or 0.0),
            "wip_adjustment": float(entry.wip_adjustment or 0.0),
            "unbilled_revenue": float(entry.unbilled_revenue or 0.0),
            "deferred_revenue": float(entry.deferred_revenue or 0.0),
            "status": entry.status.value,
            "voucher_id": entry.voucher_id,
            "journal_stub": entry.journal_stub,
            "notes": entry.notes,
            "idempotency_key": entry.idempotency_key,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }

    def _entry_from_doc(self, doc: dict) -> ProjectRecognitionEntry:
        return ProjectRecognitionEntry(
            id=doc["_id"],
            project_id=doc["project_id"],
            period_end=from_bson_date(doc["period_end"]),
            method=ProjectRecognitionMethod(
                doc.get("method", ProjectRecognitionMethod.PERCENT_COMPLETE.value)
            ),
            percent_complete=float(doc.get("percent_complete") or 0.0),
            total_cost=float(doc.get("total_cost") or 0.0),
            billed_to_date=float(doc.get("billed_to_date") or 0.0),
            prior_recognised=float(doc.get("prior_recognised") or 0.0),
            current_recognised=float(doc.get("current_recognised") or 0.0),
            wip_adjustment=float(doc.get("wip_adjustment") or 0.0),
            unbilled_revenue=float(doc.get("unbilled_revenue") or 0.0),
            deferred_revenue=float(doc.get("deferred_revenue") or 0.0),
            status=ProjectRecognitionStatus(
                doc.get("status", ProjectRecognitionStatus.DRAFT.value)
            ),
            voucher_id=doc.get("voucher_id", ""),
            journal_stub=doc.get("journal_stub"),
            notes=doc.get("notes", ""),
            idempotency_key=doc.get("idempotency_key", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def _exception_to_doc(self, exc: ProjectReconcileException) -> dict:
        return {
            "id": exc.id,
            "category": exc.category,
            "description": exc.description,
            "amount": float(exc.amount or 0.0),
            "source_ref": exc.source_ref,
        }

    def _exception_from_doc(self, doc: dict) -> ProjectReconcileException:
        return ProjectReconcileException(
            id=doc.get("id", ""),
            category=doc.get("category", ""),
            description=doc.get("description", ""),
            amount=float(doc.get("amount") or 0.0),
            source_ref=doc.get("source_ref", ""),
        )

    def _recon_to_doc(self, recon: ProjectReconciliation) -> dict:
        return {
            "_id": recon.id,
            "project_id": recon.project_id,
            "as_of": to_bson_value(recon.as_of),
            "project_subledger": float(recon.project_subledger or 0.0),
            "gl_balance": float(recon.gl_balance or 0.0),
            "ar_balance": float(recon.ar_balance or 0.0),
            "ap_balance": float(recon.ap_balance or 0.0),
            "exceptions": [self._exception_to_doc(e) for e in recon.exceptions],
            "status": recon.status.value,
            "signed_off_by": recon.signed_off_by,
            "signed_off_at": recon.signed_off_at,
            "notes": recon.notes,
            "created_at": recon.created_at,
            "updated_at": recon.updated_at,
        }

    def _recon_from_doc(self, doc: dict) -> ProjectReconciliation:
        return ProjectReconciliation(
            id=doc["_id"],
            project_id=doc["project_id"],
            as_of=from_bson_date(doc["as_of"]),
            project_subledger=float(doc.get("project_subledger") or 0.0),
            gl_balance=float(doc.get("gl_balance") or 0.0),
            ar_balance=float(doc.get("ar_balance") or 0.0),
            ap_balance=float(doc.get("ap_balance") or 0.0),
            exceptions=[
                self._exception_from_doc(e) for e in doc.get("exceptions", [])
            ],
            status=ProjectReconcileStatus(
                doc.get("status", ProjectReconcileStatus.DRAFT.value)
            ),
            signed_off_by=doc.get("signed_off_by", ""),
            signed_off_at=doc.get("signed_off_at"),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save_entry(self, entry: ProjectRecognitionEntry) -> ProjectRecognitionEntry:
        entry.updated_at = utc_now()
        self._entries.replace_one(
            {"_id": entry.id}, self._entry_to_doc(entry), upsert=True
        )
        return entry

    def find_entry_by_id(self, entry_id: str) -> Optional[ProjectRecognitionEntry]:
        doc = self._entries.find_one({"_id": entry_id})
        return self._entry_from_doc(doc) if doc else None

    def find_entry_by_idempotency_key(
        self, key: str
    ) -> Optional[ProjectRecognitionEntry]:
        if not key:
            return None
        doc = self._entries.find_one({"idempotency_key": key})
        return self._entry_from_doc(doc) if doc else None

    def list_entries_by_project(self, project_id: str) -> List[ProjectRecognitionEntry]:
        docs = self._entries.find({"project_id": project_id}).sort("period_end", -1)
        return [self._entry_from_doc(d) for d in docs]

    def save_reconciliation(
        self, recon: ProjectReconciliation
    ) -> ProjectReconciliation:
        recon.updated_at = utc_now()
        self._reconciliations.replace_one(
            {"_id": recon.id}, self._recon_to_doc(recon), upsert=True
        )
        return recon

    def find_reconciliation_by_id(
        self, recon_id: str
    ) -> Optional[ProjectReconciliation]:
        doc = self._reconciliations.find_one({"_id": recon_id})
        return self._recon_from_doc(doc) if doc else None

    def list_reconciliations_by_project(
        self, project_id: str
    ) -> List[ProjectReconciliation]:
        docs = self._reconciliations.find({"project_id": project_id}).sort("as_of", -1)
        return [self._recon_from_doc(d) for d in docs]
