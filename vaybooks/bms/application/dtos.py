from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class ActivityCompletionResult:
    order_id: str
    order_activity_id: str
    activity_name: str
    needs_expense: bool
    total_hours: float = 0.0
    total_duration_minutes: int = 0
    purchase_price: float = 0.0
    selling_price: float = 0.0
    total_purchase_price: float = 0.0
    total_selling_price: float = 0.0
    expense_source: str = "In House"
    bill_id: Optional[str] = None
    bill_number: Optional[str] = None
    activity_id: Optional[str] = None
    order_number: str = ""


@dataclass
class DashboardSummary:
    active_orders: int = 0
    pending_activity_orders: int = 0
    ready_for_delivery: int = 0
    invoice_generated: int = 0
    completed_orders: int = 0
    delivered_this_month: int = 0
    total_advance_this_month: float = 0.0
    total_invoice_this_month: float = 0.0
    total_pending_activities: int = 0
    bills_pending_invoice: int = 0
    items_pending: int = 0
    items_awaiting_delivery: int = 0
    etd_today: List[dict] = field(default_factory=list)
    overdue_orders: List[dict] = field(default_factory=list)
    ready_orders: List[dict] = field(default_factory=list)
    in_progress_orders: List[dict] = field(default_factory=list)
    recently_completed: List[dict] = field(default_factory=list)
    recently_delivered: List[dict] = field(default_factory=list)


@dataclass
class CreateOrderRequest:
    customer_name: str
    phone_number: str
    customization_items: List[dict] = field(default_factory=list)
    expected_delivery_date: Optional[date] = None
    bill_numbers: List[dict] = field(default_factory=list)
    required_activities: dict = field(default_factory=dict)
    measurements: List[dict] = field(default_factory=list)
    advance_amount: float = 0.0
    receiving_account_id: Optional[str] = None
    notes: str = ""
    alternate_phone_number: Optional[str] = None
    address: str = ""
