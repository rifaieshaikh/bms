from datetime import date
from typing import List, Set

from vaybooks.bms.domain.deliveries.entities import Delivery
from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.orders.entities import CustomizationOrder


def invoiced_bill_ids(invoices: List[Invoice]) -> Set[str]:
    ids: Set[str] = set()
    for invoice in invoices:
        ids.update(invoice.bill_ids)
    return ids


def delivered_bill_ids(deliveries: List[Delivery]) -> Set[str]:
    ids: Set[str] = set()
    for delivery in deliveries:
        ids.update(delivery.bill_ids)
    return ids


def bill_is_invoiced(bill_id: str, invoices: List[Invoice]) -> bool:
    return bill_id in invoiced_bill_ids(invoices)


def bill_is_delivered(bill_id: str, deliveries: List[Delivery]) -> bool:
    return bill_id in delivered_bill_ids(deliveries)


def all_bills_invoiced_and_delivered(
    order: CustomizationOrder,
    invoices: List[Invoice],
    deliveries: List[Delivery],
) -> bool:
    if not order.customization_items:
        return False
    all_item_ids = {item.item_id for item in order.customization_items}
    return all_item_ids <= invoiced_bill_ids(invoices) and all_item_ids <= delivered_bill_ids(
        deliveries
    )


def count_bills_pending_invoice(
    order: CustomizationOrder, invoices: List[Invoice]
) -> int:
    invoiced = invoiced_bill_ids(invoices)
    return sum(1 for item in order.customization_items if item.item_id not in invoiced)


def count_bills_pending_delivery(
    order: CustomizationOrder, deliveries: List[Delivery]
) -> int:
    delivered = delivered_bill_ids(deliveries)
    return sum(1 for item in order.customization_items if item.item_id not in delivered)
