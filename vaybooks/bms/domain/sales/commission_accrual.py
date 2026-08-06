"""Commission accrual ledger entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.sales.commission_rules import (
    BASIS_COLLECTION,
    BASIS_SALES,
    PARTY_AGENT,
    PARTY_SALES_REP,
)
from vaybooks.bms.domain.shared.date_utils import utc_now

STATUS_ACCRUED = "accrued"
STATUS_REVERSED = "reversed"
STATUS_PAID = "paid"
_STATUSES = {STATUS_ACCRUED, STATUS_REVERSED, STATUS_PAID}


@dataclass
class CommissionAccrualEntry:
    party_type: str  # agent | sales_rep
    party_id: str
    basis: str  # sales | collection
    rule_id: str
    source_invoice_id: str
    base_amount: float
    rate: float
    amount: float
    period_key: str
    id: str = field(default_factory=lambda: uuid4().hex)
    source_receipt_id: str = ""
    line_product_id: str = ""
    customer_id: str = ""
    aging_days: Optional[int] = None
    status: str = STATUS_ACCRUED
    reversal_of_id: str = ""
    paid_voucher_id: str = ""
    gl_voucher_id: str = ""
    event_date: Optional[date] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def mark_paid(self, voucher_id: str) -> None:
        self.status = STATUS_PAID
        self.paid_voucher_id = str(voucher_id or "").strip()
        self.updated_at = utc_now()

    def mark_reversed(self) -> None:
        self.status = STATUS_REVERSED
        self.updated_at = utc_now()


@dataclass
class CommissionAccrualCandidate:
    """Computed accrual before persistence / GL posting."""

    party_type: str
    party_id: str
    basis: str
    rule_id: str
    source_invoice_id: str
    base_amount: float
    rate: float
    amount: float
    period_key: str
    source_receipt_id: str = ""
    line_product_id: str = ""
    customer_id: str = ""
    aging_days: Optional[int] = None
    event_date: Optional[date] = None


def accrual_to_dict(entry: CommissionAccrualEntry) -> dict:
    return {
        "_id": entry.id,
        "party_type": entry.party_type,
        "party_id": entry.party_id,
        "basis": entry.basis,
        "rule_id": entry.rule_id,
        "source_invoice_id": entry.source_invoice_id,
        "source_receipt_id": entry.source_receipt_id,
        "line_product_id": entry.line_product_id,
        "customer_id": entry.customer_id,
        "base_amount": float(entry.base_amount),
        "rate": float(entry.rate),
        "amount": float(entry.amount),
        "aging_days": entry.aging_days,
        "period_key": entry.period_key,
        "status": entry.status,
        "reversal_of_id": entry.reversal_of_id,
        "paid_voucher_id": entry.paid_voucher_id,
        "gl_voucher_id": entry.gl_voucher_id,
        "event_date": entry.event_date.isoformat() if entry.event_date else None,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def accrual_from_dict(doc: dict) -> CommissionAccrualEntry:
    event_date = doc.get("event_date")
    if isinstance(event_date, str) and event_date:
        event_date = date.fromisoformat(event_date[:10])
    elif hasattr(event_date, "date"):
        event_date = event_date.date()
    elif not isinstance(event_date, date):
        event_date = None
    return CommissionAccrualEntry(
        id=str(doc.get("_id") or doc.get("id") or uuid4().hex),
        party_type=str(doc.get("party_type") or PARTY_AGENT),
        party_id=str(doc.get("party_id") or ""),
        basis=str(doc.get("basis") or BASIS_SALES),
        rule_id=str(doc.get("rule_id") or ""),
        source_invoice_id=str(doc.get("source_invoice_id") or ""),
        source_receipt_id=str(doc.get("source_receipt_id") or ""),
        line_product_id=str(doc.get("line_product_id") or ""),
        customer_id=str(doc.get("customer_id") or ""),
        base_amount=float(doc.get("base_amount") or 0),
        rate=float(doc.get("rate") or 0),
        amount=float(doc.get("amount") or 0),
        aging_days=(
            None if doc.get("aging_days") is None else int(doc.get("aging_days"))
        ),
        period_key=str(doc.get("period_key") or ""),
        status=str(doc.get("status") or STATUS_ACCRUED),
        reversal_of_id=str(doc.get("reversal_of_id") or ""),
        paid_voucher_id=str(doc.get("paid_voucher_id") or ""),
        gl_voucher_id=str(doc.get("gl_voucher_id") or ""),
        event_date=event_date,
        created_at=doc.get("created_at") or utc_now(),
        updated_at=doc.get("updated_at") or utc_now(),
    )


def candidate_to_entry(candidate: CommissionAccrualCandidate) -> CommissionAccrualEntry:
    return CommissionAccrualEntry(
        party_type=candidate.party_type,
        party_id=candidate.party_id,
        basis=candidate.basis,
        rule_id=candidate.rule_id,
        source_invoice_id=candidate.source_invoice_id,
        source_receipt_id=candidate.source_receipt_id,
        line_product_id=candidate.line_product_id,
        customer_id=candidate.customer_id,
        base_amount=round(float(candidate.base_amount), 2),
        rate=float(candidate.rate),
        amount=round(float(candidate.amount), 2),
        aging_days=candidate.aging_days,
        period_key=candidate.period_key,
        event_date=candidate.event_date,
        status=STATUS_ACCRUED,
    )


def sum_accrued_amounts(entries: List[CommissionAccrualEntry]) -> float:
    return round(
        sum(
            float(e.amount)
            for e in entries
            if e.status == STATUS_ACCRUED and float(e.amount) > 0
        ),
        2,
    )
