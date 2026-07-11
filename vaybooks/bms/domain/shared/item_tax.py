"""Tax profile for catalog products and services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from vaybooks.bms.domain.shared.exceptions import ValidationError


@dataclass
class ItemTaxProfile:
    hsn_sac: str = ""
    gst_rate: float = 0.0
    cgst_rate: float = 0.0
    sgst_rate: float = 0.0
    igst_rate: float = 0.0
    utgst_rate: float = 0.0
    mrp: float = 0.0

    def sync_rates_from_gst(self) -> None:
        half = round(self.gst_rate / 2.0, 4) if self.gst_rate else 0.0
        if not self.cgst_rate and not self.sgst_rate and not self.igst_rate:
            self.cgst_rate = half
            self.sgst_rate = half
            self.utgst_rate = half

    def to_dict(self) -> dict:
        return {
            "hsn_sac": self.hsn_sac,
            "gst_rate": self.gst_rate,
            "cgst_rate": self.cgst_rate,
            "sgst_rate": self.sgst_rate,
            "igst_rate": self.igst_rate,
            "utgst_rate": self.utgst_rate,
            "mrp": self.mrp,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> ItemTaxProfile:
        if not data:
            return cls()
        profile = cls(
            hsn_sac=str(data.get("hsn_sac") or ""),
            gst_rate=float(data.get("gst_rate") or 0),
            cgst_rate=float(data.get("cgst_rate") or 0),
            sgst_rate=float(data.get("sgst_rate") or 0),
            igst_rate=float(data.get("igst_rate") or 0),
            utgst_rate=float(data.get("utgst_rate") or 0),
            mrp=float(data.get("mrp") or 0),
        )
        if profile.gst_rate and not any(
            [profile.cgst_rate, profile.sgst_rate, profile.igst_rate]
        ):
            profile.sync_rates_from_gst()
        return profile


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value[:10])
    return date.today()


@dataclass
class ProductGstSlab:
    gst_rate: float
    effective_from: date
    is_active: bool = False
    id: str = field(default_factory=lambda: uuid4().hex)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "gst_rate": self.gst_rate,
            "effective_from": self.effective_from.isoformat(),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProductGstSlab:
        return cls(
            id=str(data.get("id") or uuid4().hex),
            gst_rate=float(data.get("gst_rate") or 0),
            effective_from=_parse_date(data.get("effective_from")),
            is_active=bool(data.get("is_active")),
        )


@dataclass
class ProductMrpSlab:
    mrp: float
    effective_from: date
    is_active: bool = False
    id: str = field(default_factory=lambda: uuid4().hex)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mrp": self.mrp,
            "effective_from": self.effective_from.isoformat(),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProductMrpSlab:
        return cls(
            id=str(data.get("id") or uuid4().hex),
            mrp=float(data.get("mrp") or 0),
            effective_from=_parse_date(data.get("effective_from")),
            is_active=bool(data.get("is_active")),
        )


def validate_gst_slabs(slabs: list[ProductGstSlab]) -> None:
    if not slabs:
        raise ValidationError("At least one GST rate is required")
    active = [s for s in slabs if s.is_active]
    if len(active) != 1:
        raise ValidationError("Exactly one GST rate must be active")
    dates = [s.effective_from for s in slabs]
    if len(dates) != len(set(dates)):
        raise ValidationError("Duplicate effective-from dates in GST rates")
    for slab in slabs:
        if slab.gst_rate < 0 or slab.gst_rate > 100:
            raise ValidationError("GST rate must be between 0 and 100")


def validate_mrp_entries(entries: list[ProductMrpSlab]) -> None:
    if not entries:
        raise ValidationError("At least one MRP entry is required")
    active = [e for e in entries if e.is_active]
    if len(active) != 1:
        raise ValidationError("Exactly one MRP must be active")
    dates = [e.effective_from for e in entries]
    if len(dates) != len(set(dates)):
        raise ValidationError("Duplicate effective-from dates in MRP entries")
    for entry in entries:
        if entry.mrp < 0:
            raise ValidationError("MRP cannot be negative")


@dataclass
class GstBreakdown:
    taxable_amount: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    utgst_amount: float = 0.0

    @property
    def total_tax(self) -> float:
        return round(
            self.cgst_amount + self.sgst_amount + self.igst_amount + self.utgst_amount,
            2,
        )

    @property
    def line_total(self) -> float:
        return round(self.taxable_amount + self.total_tax, 2)

    def to_dict(self) -> dict:
        return {
            "taxable_amount": self.taxable_amount,
            "cgst_amount": self.cgst_amount,
            "sgst_amount": self.sgst_amount,
            "igst_amount": self.igst_amount,
            "utgst_amount": self.utgst_amount,
            "line_total": self.line_total,
        }
