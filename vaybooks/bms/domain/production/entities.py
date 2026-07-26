from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProductionBatchStatus,
    ProductionCostAllocationMethod,
    ProductionOutputRole,
)


@dataclass
class RecipeInput:
    product_id: str
    qty: float
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    unit: str = ""
    scrap_pct: float = 0.0


@dataclass
class RecipeOutput:
    product_id: str
    expected_qty: float
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    unit: str = ""
    role: ProductionOutputRole = ProductionOutputRole.MAIN
    allocation_pct: float = 0.0
    nrv_rate: float = 0.0


@dataclass
class RecipeStage:
    name: str
    sequence: int
    id: str = field(default_factory=lambda: uuid4().hex)
    notes: str = ""


@dataclass
class Recipe:
    name: str
    inputs: List[RecipeInput]
    outputs: List[RecipeOutput]
    id: str = field(default_factory=lambda: uuid4().hex)
    code: str = ""
    description: str = ""
    base_quantity: float = 1.0
    stages: List[RecipeStage] = field(default_factory=list)
    allocation_method: ProductionCostAllocationMethod = (
        ProductionCostAllocationMethod.NRV
    )
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


@dataclass
class BatchStage:
    recipe_stage_id: str
    name: str
    sequence: int
    id: str = field(default_factory=lambda: uuid4().hex)
    completed: bool = False
    completed_at: Optional[datetime] = None
    notes: str = ""


@dataclass
class BatchIssue:
    product_id: str
    qty: float
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    unit: str = ""
    unit_cost: float = 0.0
    total_cost: float = 0.0
    location_id: str = ""


@dataclass
class BatchOutput:
    product_id: str
    qty: float
    id: str = field(default_factory=lambda: uuid4().hex)
    product_name: str = ""
    unit: str = ""
    role: ProductionOutputRole = ProductionOutputRole.MAIN
    allocation_pct: float = 0.0
    nrv_rate: float = 0.0
    allocated_cost: float = 0.0
    unit_cost: float = 0.0
    location_id: str = ""


@dataclass
class BatchCost:
    cost_type: str
    amount: float
    id: str = field(default_factory=lambda: uuid4().hex)
    activity_id: str = ""
    account_id: str = ""
    description: str = ""


@dataclass
class ProductionPosting:
    movement_ids: List[str] = field(default_factory=list)
    voucher_ids: List[str] = field(default_factory=list)
    posted_at: Optional[datetime] = None
    posted_by: str = ""


@dataclass
class ProductionBatch:
    batch_number: str
    recipe_id: str
    batch_date: date
    location_id: str
    id: str = field(default_factory=lambda: uuid4().hex)
    recipe_name: str = ""
    planned_quantity: float = 1.0
    status: ProductionBatchStatus = ProductionBatchStatus.DRAFT
    stages: List[BatchStage] = field(default_factory=list)
    issues: List[BatchIssue] = field(default_factory=list)
    outputs: List[BatchOutput] = field(default_factory=list)
    costs: List[BatchCost] = field(default_factory=list)
    allocation_method: ProductionCostAllocationMethod = (
        ProductionCostAllocationMethod.NRV
    )
    material_cost: float = 0.0
    expense_cost: float = 0.0
    total_cost: float = 0.0
    expected_sales_value: float = 0.0
    batch_margin: float = 0.0
    notes: str = ""
    posting: ProductionPosting = field(default_factory=ProductionPosting)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()

    @property
    def is_editable(self) -> bool:
        return self.status in {
            ProductionBatchStatus.DRAFT,
            ProductionBatchStatus.IN_PROGRESS,
        }


@dataclass
class ProductionSettings:
    id: str = "default"
    wip_account_id: str = ""
    raw_material_account_id: str = ""
    finished_goods_account_id: str = ""
    manufacturing_overhead_account_id: str = ""
    expense_clearing_account_id: str = ""
    scrap_account_id: str = ""
    default_allocation_method: ProductionCostAllocationMethod = (
        ProductionCostAllocationMethod.NRV
    )
    updated_at: datetime = field(default_factory=utc_now)
