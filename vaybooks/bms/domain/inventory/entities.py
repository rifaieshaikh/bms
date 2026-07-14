from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import StockMovementType, StockReferenceType
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile


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
    hsn_sac: str = ""
    active_selling_rate: float = 0.0
    active_mrp: float = 0.0
    active_gst_rate: float = 0.0
    specifications: Dict[str, str] = field(default_factory=dict)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    weighted_avg_cost: float = 0.0
    last_purchase_rate: float = 0.0
    opening_qty: float = 0.0
    current_qty: float = 0.0
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def selling_rate(self) -> float:
        return float(self.active_selling_rate or 0)

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

    def apply_active_rates(
        self,
        *,
        selling_rate: Optional[float] = None,
        mrp: Optional[float] = None,
        gst_rate: Optional[float] = None,
    ) -> None:
        if selling_rate is not None:
            self.active_selling_rate = round(float(selling_rate), 2)
        if mrp is not None:
            self.active_mrp = round(float(mrp), 2)
        if gst_rate is not None:
            self.active_gst_rate = round(float(gst_rate), 2)

    def active_tax_profile(self) -> ItemTaxProfile:
        profile = ItemTaxProfile(
            hsn_sac=self.hsn_sac or "",
            gst_rate=float(self.active_gst_rate or 0),
            mrp=float(self.active_mrp or 0),
        )
        profile.sync_rates_from_gst()
        return profile


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
