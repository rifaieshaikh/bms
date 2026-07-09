from typing import List, Optional

from vaybooks.bms.domain.deliveries.entities import Delivery
from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.orders.bill_status import (
    delivered_bill_ids,
    invoiced_bill_ids,
)
from vaybooks.bms.domain.orders.entities import CustomizationOrder
from vaybooks.bms.domain.shared.enums import OrderStatus


def resolve_order_status(
    order: CustomizationOrder,
    invoices: Optional[List[Invoice]] = None,
    deliveries: Optional[List[Delivery]] = None,
) -> OrderStatus:
    """Derive the order lifecycle status from invoices, deliveries, and activity progress."""
    if order.order_status in (OrderStatus.CANCELLED, OrderStatus.COMPLETED):
        return order.order_status

    if invoices is not None and deliveries is not None:
        all_item_ids = {item.item_id for item in order.customization_items}
        delivered = delivered_bill_ids(deliveries)
        invoiced = invoiced_bill_ids(invoices)

        if (
            all_item_ids
            and all_item_ids <= delivered
            and all_item_ids <= invoiced
        ):
            return OrderStatus.DELIVERED

        if invoices and all_item_ids and all_item_ids <= invoiced:
            if delivered:
                return OrderStatus.DELIVERED
            return OrderStatus.INVOICE_GENERATED

        if order.all_required_done():
            return OrderStatus.READY_FOR_DELIVERY
        return OrderStatus.IN_PROGRESS

    if order.all_required_done():
        if order.order_status == OrderStatus.IN_PROGRESS:
            return OrderStatus.READY_FOR_DELIVERY
    elif order.order_status == OrderStatus.READY_FOR_DELIVERY:
        return OrderStatus.IN_PROGRESS

    return order.order_status
