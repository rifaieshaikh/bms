from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import StockMovementType, StockReferenceType
from vaybooks.bms.domain.shared.item_tax import (
    ItemTaxProfile,
    ProductGstSlab,
    ProductMrpSlab,
    validate_gst_slabs,
    validate_mrp_entries,
)


@dataclass
class ProductUnit:
    code: str
    label: str
    id: str = field(default_factory=lambda: uuid4().hex)
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


@dataclass
class ProductCategory:
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
    parent_id: Optional[str] = None
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


@dataclass
class InventoryProduct:
    sku: str
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
    category_ids: List[str] = field(default_factory=list)
    category_names: List[str] = field(default_factory=list)
    category_id: str = ""
    category_name: str = ""
    unit_id: str = ""
    unit: str = "pcs"
    selling_rate: float = 0.0
    hsn_sac: str = ""
    gst_rates: List[ProductGstSlab] = field(default_factory=list)
    mrp_entries: List[ProductMrpSlab] = field(default_factory=list)
    tax_profile: ItemTaxProfile = field(default_factory=ItemTaxProfile)
    specifications: Dict[str, str] = field(default_factory=dict)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    weighted_avg_cost: float = 0.0
    last_purchase_rate: float = 0.0
    opening_qty: float = 0.0
    current_qty: float = 0.0
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()

    def sync_legacy_category_fields(self) -> None:
        if self.category_ids:
            self.category_id = self.category_ids[0]
            self.category_name = self.category_names[0] if self.category_names else ""
        else:
            self.category_id = ""
            self.category_name = ""

    def active_gst_slab(self) -> Optional[ProductGstSlab]:
        for slab in self.gst_rates:
            if slab.is_active:
                return slab
        return None

    def active_mrp_slab(self) -> Optional[ProductMrpSlab]:
        for entry in self.mrp_entries:
            if entry.is_active:
                return entry
        return None

    def active_tax_profile(self) -> ItemTaxProfile:
        gst_slab = self.active_gst_slab()
        mrp_slab = self.active_mrp_slab()
        if not gst_slab and not mrp_slab and not self.hsn_sac:
            return self.tax_profile
        profile = ItemTaxProfile(
            hsn_sac=self.hsn_sac or self.tax_profile.hsn_sac,
            gst_rate=float(gst_slab.gst_rate) if gst_slab else self.tax_profile.gst_rate,
            mrp=float(mrp_slab.mrp) if mrp_slab else self.tax_profile.mrp,
        )
        profile.sync_rates_from_gst()
        return profile

    def set_gst_slabs(self, slabs: List[ProductGstSlab]) -> None:
        validate_gst_slabs(slabs)
        self.gst_rates = list(slabs)
        self._sync_tax_profile()

    def set_mrp_entries(self, entries: List[ProductMrpSlab]) -> None:
        validate_mrp_entries(entries)
        self.mrp_entries = list(entries)
        self._sync_tax_profile()

    def apply_tax_data(
        self,
        hsn_sac: str,
        gst_slabs: List[ProductGstSlab],
        mrp_entries: List[ProductMrpSlab],
    ) -> None:
        self.hsn_sac = (hsn_sac or "").strip()
        validate_gst_slabs(gst_slabs)
        validate_mrp_entries(mrp_entries)
        self.gst_rates = list(gst_slabs)
        self.mrp_entries = list(mrp_entries)
        self._sync_tax_profile()

    def _sync_tax_profile(self) -> None:
        self.tax_profile = self.active_tax_profile()

    @classmethod
    def default_gst_slab(cls, gst_rate: float = 0.0, effective_from: date | None = None) -> ProductGstSlab:
        return ProductGstSlab(
            gst_rate=gst_rate,
            effective_from=effective_from or date.today(),
            is_active=True,
        )

    @classmethod
    def default_mrp_entry(cls, mrp: float = 0.0, effective_from: date | None = None) -> ProductMrpSlab:
        return ProductMrpSlab(
            mrp=mrp,
            effective_from=effective_from or date.today(),
            is_active=True,
        )


@dataclass
class StockMovement:
    product_id: str
    movement_type: StockMovementType
    qty: float
    movement_date: date
    id: str = field(default_factory=lambda: uuid4().hex)
    reference_type: StockReferenceType = StockReferenceType.MANUAL
    reference_id: Optional[str] = None
    notes: str = ""
    created_at: datetime = field(default_factory=utc_now)
