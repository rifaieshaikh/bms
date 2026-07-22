from dataclasses import dataclass
from typing import List, Optional

from vaybooks.bms.domain.boutique.activities.entities import ActivityConfig
from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder, OrderActivity
from vaybooks.bms.domain.shared.date_utils import is_time_entry_complete, minutes_to_hours
from vaybooks.bms.domain.shared.exceptions import IncompleteTimeEntriesError, ValidationError
from vaybooks.bms.domain.boutique.time_tracking.entities import TimeEntry


@dataclass
class ActivityCompletionPreview:
    order_activity_id: str
    activity_id: str
    activity_name: str
    order_id: str
    order_number: str
    needs_expense: bool
    total_duration_minutes: int = 0
    total_hours: float = 0.0
    purchase_price: float = 0.0
    selling_price: float = 0.0
    total_purchase_price: float = 0.0
    total_selling_price: float = 0.0
    expense_source: str = "In House"
    bill_id: Optional[str] = None
    bill_number: Optional[str] = None
    incomplete_time_warning: bool = False


class ActivityDomainService:
    def prepare_completion(
        self,
        order: CustomizationOrder,
        order_activity: OrderActivity,
        activity_config: ActivityConfig,
        time_entries: List[TimeEntry],
    ) -> ActivityCompletionPreview:
        preview = ActivityCompletionPreview(
            order_activity_id=order_activity.order_activity_id,
            activity_id=order_activity.activity_id,
            activity_name=order_activity.activity_name,
            order_id=order.id,
            order_number=order.order_number,
            needs_expense=activity_config.is_in_house
            or activity_config.default_hourly_expense > 0,
            expense_source=activity_config.activity_type.value,
            bill_id=order_activity.bill_id,
        )

        if order_activity.bill_id:
            bill = order.get_bill_by_id(order_activity.bill_id)
            if bill:
                preview.bill_number = bill.bill_number
            time_entries = [t for t in time_entries if t.bill_id == order_activity.bill_id]

        if activity_config.requires_time_tracking:
            if not time_entries:
                raise IncompleteTimeEntriesError(
                    "No time entries found for this activity"
                )
            incomplete = [
                t
                for t in time_entries
                if not is_time_entry_complete(t.start_time, t.end_time)
            ]
            if incomplete:
                preview.incomplete_time_warning = True
                raise IncompleteTimeEntriesError(
                    "Time is recorded but not fully completed. "
                    "Please complete the time entry before marking this activity as completed."
                )

            total_minutes = sum(t.duration_minutes for t in time_entries)
            total_hours = minutes_to_hours(total_minutes)
            preview.total_duration_minutes = total_minutes
            preview.total_hours = total_hours
            hourly_expense = activity_config.default_hourly_expense
            preview.purchase_price = hourly_expense
            preview.selling_price = hourly_expense
            preview.total_purchase_price = round(total_hours * hourly_expense, 2)
            preview.total_selling_price = round(total_hours * hourly_expense, 2)
            preview.needs_expense = True

        return preview

    def validate_activity_config(self, activity: ActivityConfig) -> None:
        if not activity.activity_name.strip():
            raise ValidationError("Activity name is required")
        if activity.default_hourly_expense < 0:
            raise ValidationError("Default hourly expense cannot be negative")
        if activity.requires_pricing and activity.default_hourly_expense <= 0:
            raise ValidationError(
                "In House Service requires a default hourly expense"
            )
