from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.activities.entities import ActivityConfig
from vaybooks.bms.domain.deliveries.entities import Delivery
from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.order_status import resolve_order_status
from vaybooks.bms.domain.orders.entities import (
    COMPLETED_ACTIVITY_STATUS,
    CREATED_ACTIVITY_STATUS,
    CustomizationItem,
    CustomizationOrder,
    Measurement,
    OrderActivity,
)
from vaybooks.bms.domain.orders.repository import BillRegistryRepository, OrderRepository
from vaybooks.bms.domain.orders.value_objects import BillRegistryEntry
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ActivityStatus, CustomizationItemStatus, OrderStatus
from vaybooks.bms.domain.shared.exceptions import (
    BillNumberExistsError,
    OrderNotReadyError,
    ValidationError,
)


class OrderDomainService:
    def __init__(
        self,
        order_repo: OrderRepository,
        bill_registry_repo: BillRegistryRepository,
    ):
        self._order_repo = order_repo
        self._bill_registry_repo = bill_registry_repo

    def validate_order(self, order: CustomizationOrder) -> None:
        if order.order_status == OrderStatus.DRAFT:
            return
        if not order.customization_items:
            raise ValidationError(
                "Customization order must have at least one customization item"
            )
        required = [a for a in order.order_activities if a.is_required]
        if not required:
            raise ValidationError(
                "Customization order must have at least one required activity"
            )

    def next_measurement_bill_number(self, measurement_number: str) -> str:
        """Allocate MS-####-01, MS-####-02, ... for a measurement."""
        base = measurement_number.strip().upper()
        if not base:
            raise ValidationError("Measurement number is required")
        suffix = 1
        while True:
            candidate = f"{base}-{suffix:02d}"
            if not self._bill_registry_repo.exists(candidate):
                return candidate
            suffix += 1
            if suffix > 99:
                raise ValidationError(
                    f"No free bill-number suffix left for {base}"
                )

    def add_customization_item(
        self,
        order: CustomizationOrder,
        bill_number: str,
        description: str,
        activity_configs: List[ActivityConfig],
        required_map: dict,
        expected_delivery_date=None,
        customer_specification: str = "",
        measurement_id: Optional[str] = None,
        measurement_number: Optional[str] = None,
    ) -> CustomizationItem:
        bill_number = bill_number.strip().upper()
        if not bill_number:
            raise ValidationError("Bill number is required")

        if order.get_items_by_bill_number(bill_number):
            raise BillNumberExistsError(
                f"Bill number {bill_number} is already used in this order"
            )

        existing = self._bill_registry_repo.find_by_bill_number(bill_number)
        if existing and existing.order_id != order.id:
            raise BillNumberExistsError(
                f"Bill number {bill_number} already belongs to another order"
            )

        item = CustomizationItem(
            bill_number=bill_number,
            description=description.strip(),
            expected_delivery_date=expected_delivery_date or order.expected_delivery_date,
            customer_specification=(customer_specification or "").strip(),
            measurement_id=measurement_id,
            measurement_number=(measurement_number or "").strip().upper() or None,
        )
        if not existing:
            entry = BillRegistryEntry(
                bill_number=bill_number,
                order_id=order.id,
                bill_id=item.item_id,
            )
            self._bill_registry_repo.register(entry)

        order.customization_items.append(item)
        for config in activity_configs:
            if required_map.get(config.activity_name, False):
                order.order_activities.append(
                    OrderActivity(
                        activity_id=config.id,
                        activity_name=config.activity_name,
                        is_required=True,
                        bill_id=item.item_id,
                    )
                )
        item.item_status = CustomizationItemStatus.IN_PROGRESS
        order.updated_at = utc_now()
        return item

    def register_bill_number(
        self,
        order: CustomizationOrder,
        bill_number: str,
        item_description: str = "",
        activity_configs: Optional[List[ActivityConfig]] = None,
        required_map: Optional[dict] = None,
    ) -> CustomizationItem:
        configs = activity_configs or []
        required = required_map or {}
        return self.add_customization_item(
            order,
            bill_number,
            item_description,
            configs,
            required,
        )

    def add_measurement(
        self,
        order: CustomizationOrder,
        measurement_name: str,
        measurement_value: str,
        bill_id: Optional[str] = None,
        unit: str = "inch",
        notes: str = "",
    ) -> Measurement:
        measurement = Measurement(
            measurement_name=measurement_name,
            measurement_value=measurement_value,
            bill_id=bill_id,
            unit=unit,
            notes=notes,
        )
        order.measurements.append(measurement)
        order.updated_at = utc_now()
        return measurement

    def build_order_activities(
        self,
        activity_configs: List[ActivityConfig],
        required_map: dict,
        bill_ids: List[str],
    ) -> List[OrderActivity]:
        activities = []
        for bill_id in bill_ids:
            for config in activity_configs:
                if required_map.get(config.activity_name, False):
                    activities.append(
                        OrderActivity(
                            activity_id=config.id,
                            activity_name=config.activity_name,
                            is_required=True,
                            bill_id=bill_id,
                        )
                    )
        return activities

    def recalculate_status(
        self,
        order: CustomizationOrder,
        invoices: Optional[List[Invoice]] = None,
        deliveries: Optional[List[Delivery]] = None,
    ) -> OrderStatus:
        order.refresh_item_statuses()
        order.order_status = resolve_order_status(order, invoices, deliveries)
        order.updated_at = utc_now()
        return order.order_status

    def mark_activity_completed(
        self,
        order: CustomizationOrder,
        order_activity_id: str,
        completed_by: str,
    ) -> OrderActivity:
        activity = order.get_activity_by_id(order_activity_id)
        if not activity:
            raise ValidationError(f"Activity {order_activity_id} not found")
        if activity.activity_status == ActivityStatus.COMPLETED:
            raise ValidationError("Activity is already completed")

        activity.activity_status = ActivityStatus.COMPLETED
        activity.current_status = COMPLETED_ACTIVITY_STATUS
        activity.completed_at = utc_now()
        activity.completed_by = completed_by
        if activity.bill_id:
            order.item_activities_complete(activity.bill_id)
        order.updated_at = utc_now()
        return activity

    def set_activity_status(
        self,
        order: CustomizationOrder,
        order_activity_id: str,
        status: str,
        allowed_statuses: Optional[List[str]] = None,
    ) -> OrderActivity:
        activity = order.get_activity_by_id(order_activity_id)
        if not activity:
            raise ValidationError(f"Activity {order_activity_id} not found")

        status = (status or "").strip()
        if not status:
            raise ValidationError("Status is required")
        if status == COMPLETED_ACTIVITY_STATUS:
            raise ValidationError(
                "Use the Complete action to finish an activity"
            )
        if allowed_statuses is not None and status not in allowed_statuses:
            raise ValidationError(f"'{status}' is not a valid status for this activity")

        activity.current_status = status
        if status == CREATED_ACTIVITY_STATUS:
            activity.activity_status = ActivityStatus.PENDING
            activity.started_at = None
        else:
            activity.activity_status = ActivityStatus.IN_PROGRESS
            activity.started_at = activity.started_at or utc_now()
        # Moving to any non-completed status re-opens a previously completed activity.
        activity.completed_at = None
        activity.completed_by = None
        order.updated_at = utc_now()
        return activity

    def skip_activity(
        self,
        order: CustomizationOrder,
        order_activity_id: str,
        completed_by: str,
    ) -> OrderActivity:
        activity = order.get_activity_by_id(order_activity_id)
        if not activity:
            raise ValidationError(f"Activity {order_activity_id} not found")
        if not activity.is_required:
            raise ValidationError("Only required activities can be skipped")

        activity.activity_status = ActivityStatus.SKIPPED
        activity.completed_at = utc_now()
        activity.completed_by = completed_by
        if activity.bill_id:
            order.item_activities_complete(activity.bill_id)
        order.updated_at = utc_now()
        return activity

    def mark_delivered(
        self,
        order: CustomizationOrder,
        delivery_date: date,
        delivery_notes: str = "",
        override: bool = False,
    ) -> CustomizationOrder:
        if order.order_status != OrderStatus.INVOICE_GENERATED and not override:
            raise OrderNotReadyError(
                "Cannot mark delivered before invoice generation"
            )
        if not delivery_date:
            raise ValidationError("Delivery date is required")

        order.delivery_date = delivery_date
        order.delivery_notes = delivery_notes
        order.order_status = OrderStatus.DELIVERED
        order.updated_at = utc_now()
        return order

    def cancel_order(self, order: CustomizationOrder) -> CustomizationOrder:
        order.order_status = OrderStatus.CANCELLED
        order.updated_at = utc_now()
        return order

    def complete_order(self, order: CustomizationOrder) -> CustomizationOrder:
        if order.order_status == OrderStatus.CANCELLED:
            raise ValidationError("Cancelled orders cannot be completed")
        if order.order_status == OrderStatus.COMPLETED:
            raise ValidationError("Order is already completed")
        if order.order_status != OrderStatus.DELIVERED:
            raise ValidationError(
                "Only delivered orders can be marked complete"
            )
        order.order_status = OrderStatus.COMPLETED
        order.updated_at = utc_now()
        return order

    def update_customization_item(
        self,
        order: CustomizationOrder,
        item_id: str,
        bill_number: str,
        description: str,
        expected_delivery_date=None,
    ) -> CustomizationItem:
        item = order.get_item_by_id(item_id)
        if not item:
            raise ValidationError("Customization item not found")

        bill_number = bill_number.strip().upper()
        if not bill_number:
            raise ValidationError("Bill number is required")

        if bill_number != item.bill_number:
            if any(
                i.item_id != item_id
                for i in order.get_items_by_bill_number(bill_number)
            ):
                raise BillNumberExistsError(
                    f"Bill number {bill_number} is already used in this order"
                )
            existing = self._bill_registry_repo.find_by_bill_number(bill_number)
            if existing and existing.order_id != order.id:
                raise BillNumberExistsError(
                    f"Bill number {bill_number} already belongs to another order"
                )
            if not existing:
                entry = BillRegistryEntry(
                    bill_number=bill_number,
                    order_id=order.id,
                    bill_id=item.item_id,
                )
                self._bill_registry_repo.register(entry)

        item.bill_number = bill_number
        item.description = description.strip()
        if expected_delivery_date is not None:
            item.expected_delivery_date = expected_delivery_date
        item.updated_at = utc_now()
        order.updated_at = utc_now()
        return item

    def add_activity_to_item(
        self,
        order: CustomizationOrder,
        item_id: str,
        activity_id: str,
        activity_name: str,
        is_required: bool = True,
    ) -> OrderActivity:
        if not order.get_item_by_id(item_id):
            raise ValidationError("Customization item not found")
        for activity in order.activities_for_item(item_id):
            if activity.activity_id == activity_id:
                raise ValidationError("Activity is already assigned to this item")

        activity = OrderActivity(
            activity_id=activity_id,
            activity_name=activity_name,
            is_required=is_required,
            bill_id=item_id,
        )
        order.order_activities.append(activity)
        order.updated_at = utc_now()
        return activity

    def remove_activity_from_item(
        self,
        order: CustomizationOrder,
        order_activity_id: str,
    ) -> None:
        activity = order.get_activity_by_id(order_activity_id)
        if not activity:
            raise ValidationError("Activity not found")
        if activity.activity_status == ActivityStatus.COMPLETED:
            raise ValidationError("Completed activities cannot be removed")

        order.order_activities = [
            act
            for act in order.order_activities
            if act.order_activity_id != order_activity_id
        ]
        order.updated_at = utc_now()

