from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import StockMovementType, StockReferenceType


@dataclass
class ProductCategory:
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
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
    category_id: str
    id: str = field(default_factory=lambda: uuid4().hex)
    category_name: str = ""
    unit: str = "pcs"
    selling_rate: float = 0.0
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
