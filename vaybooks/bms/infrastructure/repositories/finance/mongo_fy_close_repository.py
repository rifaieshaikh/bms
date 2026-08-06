"""Mongo persistence for financial-year close records."""

from __future__ import annotations

from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.finance.fy_close import FyCloseRecord


class MongoFyCloseRepository:
    def __init__(self, db: Database):
        self._collection = db.fy_closes
        try:
            self._collection.create_index(
                [("from_fy", 1), ("to_fy", 1)], unique=True, name="fy_close_pair"
            )
        except Exception:
            pass

    def _to_doc(self, record: FyCloseRecord) -> dict:
        return {
            "_id": record.id,
            "from_fy": record.from_fy,
            "to_fy": record.to_fy,
            "mode": record.mode,
            "status": record.status,
            "closed_at": record.closed_at,
            "totals": record.totals or {},
            "backup_path": record.backup_path or "",
            "error": record.error or "",
            "account_snapshots": record.account_snapshots or [],
            "pending_receivables": record.pending_receivables or [],
            "pending_payables": record.pending_payables or [],
        }

    def _from_doc(self, doc: dict) -> FyCloseRecord:
        return FyCloseRecord(
            id=str(doc.get("_id") or ""),
            from_fy=str(doc.get("from_fy") or ""),
            to_fy=str(doc.get("to_fy") or ""),
            mode=str(doc.get("mode") or ""),
            status=str(doc.get("status") or ""),
            closed_at=doc.get("closed_at"),
            totals=dict(doc.get("totals") or {}),
            backup_path=str(doc.get("backup_path") or ""),
            error=str(doc.get("error") or ""),
            account_snapshots=list(doc.get("account_snapshots") or []),
            pending_receivables=list(doc.get("pending_receivables") or []),
            pending_payables=list(doc.get("pending_payables") or []),
        )

    def save(self, record: FyCloseRecord) -> FyCloseRecord:
        """Upsert by (from_fy, to_fy) so failed closes can be retried."""
        existing = self.find_by_pair(record.from_fy, record.to_fy)
        if existing:
            record.id = existing.id
        doc = self._to_doc(record)
        self._collection.replace_one(
            {"from_fy": record.from_fy, "to_fy": record.to_fy},
            doc,
            upsert=True,
        )
        return record

    def find_by_pair(self, from_fy: str, to_fy: str) -> Optional[FyCloseRecord]:
        doc = self._collection.find_one({"from_fy": from_fy, "to_fy": to_fy})
        return self._from_doc(doc) if doc else None

    def find_success_by_pair(
        self, from_fy: str, to_fy: str
    ) -> Optional[FyCloseRecord]:
        doc = self._collection.find_one(
            {"from_fy": from_fy, "to_fy": to_fy, "status": "success"}
        )
        return self._from_doc(doc) if doc else None

    def list_closed_fys(self) -> List[str]:
        """FY labels that have been successfully closed (from_fy)."""
        rows = self._collection.find(
            {"status": "success"}, {"from_fy": 1}
        )
        return sorted({str(r.get("from_fy") or "") for r in rows if r.get("from_fy")})

    def last_success(self) -> Optional[FyCloseRecord]:
        doc = self._collection.find_one(
            {"status": "success"}, sort=[("closed_at", -1)]
        )
        return self._from_doc(doc) if doc else None

    def is_fy_closed(self, fy: str) -> bool:
        fy = (fy or "").strip()
        if not fy:
            return False
        return (
            self._collection.find_one({"from_fy": fy, "status": "success"}) is not None
        )
