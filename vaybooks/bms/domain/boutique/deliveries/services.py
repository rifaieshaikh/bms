from datetime import date
from typing import List, Set

from vaybooks.bms.domain.boutique.deliveries.entities import Delivery
from vaybooks.bms.domain.boutique.deliveries.repository import DeliveryRepository
from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder
from vaybooks.bms.domain.shared.exceptions import ValidationError


class DeliveryDomainService:
    def __init__(self, delivery_repo: DeliveryRepository):
        self._delivery_repo = delivery_repo

    @staticmethod
    def delivered_bill_ids(deliveries: List[Delivery]) -> Set[str]:
        ids: Set[str] = set()
        for delivery in deliveries:
            ids.update(delivery.bill_ids)
        return ids

    def validate_bill_ids(
        self,
        order: CustomizationOrder,
        bill_ids: List[str],
        existing_deliveries: List[Delivery],
        allow_already_delivered: bool = False,
    ) -> None:
        if not bill_ids:
            raise ValidationError("Select at least one bill for delivery")

        order_bill_ids = {item.item_id for item in order.customization_items}
        for bill_id in bill_ids:
            if bill_id not in order_bill_ids:
                raise ValidationError(f"Item {bill_id} does not belong to this order")
            if not order.item_activities_complete(bill_id):
                raise ValidationError(
                    "Only completed customization items can be delivered"
                )

        if not allow_already_delivered:
            already = self.delivered_bill_ids(existing_deliveries)
            overlap = already.intersection(bill_ids)
            if overlap:
                raise ValidationError(
                    "One or more selected bills are already delivered. "
                    "Enable override to deliver again."
                )

    def record_delivery(
        self,
        order: CustomizationOrder,
        bill_ids: List[str],
        delivery_date: date,
        delivery_notes: str = "",
        existing_deliveries: List[Delivery] | None = None,
        allow_already_delivered: bool = False,
    ) -> Delivery:
        existing = existing_deliveries or self._delivery_repo.list_by_order(order.id)
        self.validate_bill_ids(
            order, bill_ids, existing, allow_already_delivered=allow_already_delivered
        )
        if not delivery_date:
            raise ValidationError("Delivery date is required")

        delivery = Delivery(
            order_id=order.id,
            order_number=order.order_number,
            bill_ids=list(bill_ids),
            delivery_date=delivery_date,
            delivery_notes=delivery_notes,
        )
        return self._delivery_repo.save(delivery)
