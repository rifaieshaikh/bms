from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ActivityStatus, CustomizationItemStatus, OrderStatus


@dataclass
class CustomizationItem:
    bill_number: str
    description: str = ""
    item_id: str = field(default_factory=lambda: uuid4().hex)
    item_status: CustomizationItemStatus = CustomizationItemStatus.PENDING
    # Per-item ETD. Defaults to the order ETD when not explicitly set; older
    # items without one fall back to the order ETD at display time.
    expected_delivery_date: Optional[date] = None
    # Per-item profitability snapshot, frozen once the item is both invoiced
    # and delivered. `mph_snapshot_at` being set marks the numbers as final.
    sell_amount: float = 0.0

    @property
    def sale_price(self) -> float:
        """Per-item sale price used when computing invoice totals."""
        return self.sell_amount
    expense_selling_total: float = 0.0
    expense_purchase_total: float = 0.0
    in_house_hours: float = 0.0
    margin_amount: Optional[float] = None
    margin_per_hour: Optional[float] = None
    mph_snapshot_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class BillNumber:
    """Backward-compatible view of a customization item."""

    bill_number: str
    item_description: str = ""
    bill_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class Measurement:
    measurement_name: str
    measurement_value: str
    bill_id: Optional[str] = None
    unit: str = "inch"
    notes: str = ""
    measurement_id: str = field(default_factory=lambda: uuid4().hex)


CREATED_ACTIVITY_STATUS = "Created"
COMPLETED_ACTIVITY_STATUS = "Completed"


@dataclass
class OrderActivity:
    activity_id: str
    activity_name: str
    is_required: bool = True
    activity_status: ActivityStatus = ActivityStatus.PENDING
    current_status: str = CREATED_ACTIVITY_STATUS
    bill_id: Optional[str] = None
    order_activity_id: str = field(default_factory=lambda: uuid4().hex)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None


@dataclass
class CustomizationOrder:
    order_number: str
    customer_id: str
    customer_name: str
    phone_number: str
    order_date: date
    expected_delivery_date: date
    id: str = field(default_factory=lambda: uuid4().hex)
    advance_amount: float = 0.0
    order_status: OrderStatus = OrderStatus.IN_PROGRESS
    notes: str = ""
    customization_items: List[CustomizationItem] = field(default_factory=list)
    measurements: List[Measurement] = field(default_factory=list)
    order_activities: List[OrderActivity] = field(default_factory=list)
    delivery_date: Optional[date] = None
    delivery_notes: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def bill_numbers(self) -> List[BillNumber]:
        return [
            BillNumber(
                bill_id=item.item_id,
                bill_number=item.bill_number,
                item_description=item.description,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in self.customization_items
        ]

    def get_item_by_id(self, item_id: str) -> Optional[CustomizationItem]:
        for item in self.customization_items:
            if item.item_id == item_id:
                return item
        return None

    def get_bill_by_id(self, bill_id: str) -> Optional[BillNumber]:
        item = self.get_item_by_id(bill_id)
        if not item:
            return None
        return BillNumber(
            bill_id=item.item_id,
            bill_number=item.bill_number,
            item_description=item.description,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def get_items_by_bill_number(self, bill_number: str) -> List[CustomizationItem]:
        normalized = bill_number.strip().upper()
        return [i for i in self.customization_items if i.bill_number == normalized]

    def get_bill_by_number(self, bill_number: str) -> Optional[BillNumber]:
        items = self.get_items_by_bill_number(bill_number)
        if not items:
            return None
        item = items[0]
        return BillNumber(
            bill_id=item.item_id,
            bill_number=item.bill_number,
            item_description=item.description,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def get_activity_by_id(self, order_activity_id: str) -> Optional[OrderActivity]:
        for activity in self.order_activities:
            if activity.order_activity_id == order_activity_id:
                return activity
        return None

    def required_activities(self) -> List[OrderActivity]:
        return [a for a in self.order_activities if a.is_required]

    def activities_for_item(self, item_id: str) -> List[OrderActivity]:
        return [a for a in self.order_activities if a.bill_id == item_id]

    def activities_for_bill(self, bill_id: str) -> List[OrderActivity]:
        return self.activities_for_item(bill_id)

    def item_activities_complete(self, item_id: str) -> bool:
        required = [a for a in self.activities_for_item(item_id) if a.is_required]
        if not required:
            return True
        complete = all(
            a.activity_status in (ActivityStatus.COMPLETED, ActivityStatus.SKIPPED)
            for a in required
        )
        if complete:
            item = self.get_item_by_id(item_id)
            if item and item.item_status != CustomizationItemStatus.COMPLETED:
                item.item_status = CustomizationItemStatus.COMPLETED
                item.updated_at = utc_now()
        return complete

    def bill_activities_complete(self, bill_id: str) -> bool:
        return self.item_activities_complete(bill_id)

    def refresh_item_statuses(self) -> None:
        for item in self.customization_items:
            if self.item_activities_complete(item.item_id):
                item.item_status = CustomizationItemStatus.COMPLETED
            elif any(
                a.activity_status == ActivityStatus.IN_PROGRESS
                for a in self.activities_for_item(item.item_id)
            ):
                item.item_status = CustomizationItemStatus.IN_PROGRESS
            else:
                item.item_status = CustomizationItemStatus.PENDING
            item.updated_at = utc_now()

    def all_required_done(self) -> bool:
        required = self.required_activities()
        if not required:
            return False
        return all(
            a.activity_status in (ActivityStatus.COMPLETED, ActivityStatus.SKIPPED)
            for a in required
        )
