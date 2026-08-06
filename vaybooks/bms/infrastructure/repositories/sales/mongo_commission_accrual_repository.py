"""Commission accrual ledger repository."""

from __future__ import annotations

from typing import List, Optional, Protocol

from pymongo.database import Database

from vaybooks.bms.domain.sales.commission_accrual import (
    STATUS_ACCRUED,
    CommissionAccrualEntry,
    accrual_from_dict,
    accrual_to_dict,
)


class CommissionAccrualRepository(Protocol):
    def save(self, entry: CommissionAccrualEntry) -> CommissionAccrualEntry: ...

    def save_many(
        self, entries: List[CommissionAccrualEntry]
    ) -> List[CommissionAccrualEntry]: ...

    def find_by_id(self, entry_id: str) -> Optional[CommissionAccrualEntry]: ...

    def list_by_invoice(
        self, invoice_id: str, *, status: Optional[str] = None
    ) -> List[CommissionAccrualEntry]: ...

    def list_by_receipt(self, receipt_id: str) -> List[CommissionAccrualEntry]: ...

    def list_by_party(
        self,
        party_type: str,
        party_id: str,
        *,
        period_key: Optional[str] = None,
        basis: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[CommissionAccrualEntry]: ...

    def list_unpaid(
        self,
        party_type: str,
        party_id: str,
        *,
        period_key: Optional[str] = None,
    ) -> List[CommissionAccrualEntry]: ...

    def mark_paid(
        self, entry_ids: List[str], paid_voucher_id: str
    ) -> int: ...


class MongoCommissionAccrualRepository:
    def __init__(self, db: Database):
        self._collection = db.commission_accruals

    def save(self, entry: CommissionAccrualEntry) -> CommissionAccrualEntry:
        self._collection.replace_one(
            {"_id": entry.id}, accrual_to_dict(entry), upsert=True
        )
        return entry

    def save_many(
        self, entries: List[CommissionAccrualEntry]
    ) -> List[CommissionAccrualEntry]:
        for entry in entries:
            self.save(entry)
        return entries

    def find_by_id(self, entry_id: str) -> Optional[CommissionAccrualEntry]:
        if not entry_id:
            return None
        doc = self._collection.find_one({"_id": str(entry_id)})
        return accrual_from_dict(doc) if doc else None

    def list_by_invoice(
        self, invoice_id: str, *, status: Optional[str] = None
    ) -> List[CommissionAccrualEntry]:
        if not invoice_id:
            return []
        query: dict = {"source_invoice_id": str(invoice_id)}
        if status:
            query["status"] = status
        return [
            accrual_from_dict(d)
            for d in self._collection.find(query).sort("created_at", 1)
        ]

    def list_by_receipt(self, receipt_id: str) -> List[CommissionAccrualEntry]:
        if not receipt_id:
            return []
        return [
            accrual_from_dict(d)
            for d in self._collection.find(
                {"source_receipt_id": str(receipt_id)}
            ).sort("created_at", 1)
        ]

    def list_by_party(
        self,
        party_type: str,
        party_id: str,
        *,
        period_key: Optional[str] = None,
        basis: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[CommissionAccrualEntry]:
        if not party_id:
            return []
        query: dict = {
            "party_type": str(party_type),
            "party_id": str(party_id),
        }
        if period_key:
            query["period_key"] = period_key
        if basis:
            query["basis"] = basis
        if status:
            query["status"] = status
        return [
            accrual_from_dict(d)
            for d in self._collection.find(query).sort("created_at", 1)
        ]

    def list_unpaid(
        self,
        party_type: str,
        party_id: str,
        *,
        period_key: Optional[str] = None,
    ) -> List[CommissionAccrualEntry]:
        return self.list_by_party(
            party_type,
            party_id,
            period_key=period_key,
            status=STATUS_ACCRUED,
        )

    def mark_paid(self, entry_ids: List[str], paid_voucher_id: str) -> int:
        ids = [str(i) for i in entry_ids if str(i).strip()]
        if not ids:
            return 0
        from vaybooks.bms.domain.sales.commission_accrual import STATUS_PAID
        from vaybooks.bms.domain.shared.date_utils import utc_now

        result = self._collection.update_many(
            {"_id": {"$in": ids}, "status": STATUS_ACCRUED},
            {
                "$set": {
                    "status": STATUS_PAID,
                    "paid_voucher_id": str(paid_voucher_id or ""),
                    "updated_at": utc_now(),
                }
            },
        )
        return int(result.modified_count or 0)

    def sum_base_for_party_period(
        self,
        party_type: str,
        party_id: str,
        *,
        period_key: str,
        basis: str,
    ) -> float:
        """Sum base_amount of accrued (non-reversed) entries for threshold checks."""
        pipeline = [
            {
                "$match": {
                    "party_type": party_type,
                    "party_id": party_id,
                    "period_key": period_key,
                    "basis": basis,
                    "status": {"$in": [STATUS_ACCRUED, "paid"]},
                    "reversal_of_id": {"$in": ["", None]},
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$base_amount"}}},
        ]
        rows = list(self._collection.aggregate(pipeline))
        if not rows:
            return 0.0
        return round(float(rows[0].get("total") or 0), 2)
