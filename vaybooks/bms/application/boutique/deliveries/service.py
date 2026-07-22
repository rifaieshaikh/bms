from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.boutique.deliveries.entities import Delivery
from vaybooks.bms.domain.boutique.deliveries.repository import DeliveryRepository
from vaybooks.bms.domain.boutique.deliveries.services import DeliveryDomainService
from vaybooks.bms.domain.boutique.invoices.services import InvoiceDomainService
from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder
from vaybooks.bms.domain.boutique.orders.repository import OrderRepository
from vaybooks.bms.domain.boutique.orders.services import OrderDomainService
from vaybooks.bms.domain.boutique.orders.order_refs import order_ref_search_variants
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError


class DeliveryAppService:
    def __init__(
        self,
        delivery_repo: DeliveryRepository,
        order_repo: OrderRepository,
        invoice_repo,
        expense_repo=None,
    ):
        self._delivery_repo = delivery_repo
        self._order_repo = order_repo
        self._invoice_repo = invoice_repo
        self._expense_repo = expense_repo
        self._domain = DeliveryDomainService(delivery_repo)
        self._order_domain = OrderDomainService(order_repo, None)

    def _resolve_order(self, order_ref: str) -> CustomizationOrder:
        for candidate in order_ref_search_variants(order_ref) or [order_ref]:
            order = self._order_repo.find_by_id(candidate)
            if order is None:
                order = self._order_repo.find_by_order_number(candidate)
            if order is not None:
                return order
        raise ValidationError(f"Order not found: {order_ref}")

    def _snapshot_item_mph(self, order, invoices, deliveries) -> None:
        """Freeze per-item MPH for items now delivered + invoiced."""
        if self._expense_repo is None:
            return
        expenses = self._expense_repo.find_by_order(order.id)
        InvoiceDomainService.snapshot_order_items(
            order, invoices, deliveries, expenses
        )

    def record_delivery(
        self,
        order_id: str,
        bill_ids: List[str],
        delivery_date: date,
        delivery_notes: str = "",
        allow_already_delivered: bool = False,
    ) -> Delivery:
        order = self._resolve_order(order_id)
        existing = self._delivery_repo.list_by_order(order.id)
        delivery = self._domain.record_delivery(
            order=order,
            bill_ids=bill_ids,
            delivery_date=delivery_date,
            delivery_notes=delivery_notes,
            existing_deliveries=existing,
            allow_already_delivered=allow_already_delivered,
        )
        invoices = self._invoice_repo.list_by_order(order.id)
        deliveries = self._delivery_repo.list_by_order(order.id) + [delivery]
        self._order_domain.recalculate_status(order, invoices, deliveries)
        self._snapshot_item_mph(order, invoices, deliveries)
        order.updated_at = utc_now()
        self._order_repo.save(order)
        return delivery

    def get_delivery(self, delivery_id: str) -> Optional[Delivery]:
        return self._delivery_repo.find_by_id(delivery_id)

    def update_delivery(
        self,
        delivery_id: str,
        bill_ids: List[str],
        delivery_date: date,
        delivery_notes: str = "",
    ) -> Delivery:
        delivery = self._delivery_repo.find_by_id(delivery_id)
        if not delivery:
            raise ValueError("Delivery not found")
        if not bill_ids:
            raise ValueError("Select at least one item for the delivery")
        if not delivery_date:
            raise ValueError("Delivery date is required")

        delivery.bill_ids = list(bill_ids)
        delivery.delivery_date = delivery_date
        delivery.delivery_notes = delivery_notes
        delivery.updated_at = utc_now()
        saved = self._delivery_repo.save(delivery)

        order = self._order_repo.find_by_id(delivery.order_id)
        invoices = self._invoice_repo.list_by_order(delivery.order_id)
        deliveries = self._delivery_repo.list_by_order(delivery.order_id)
        self._order_domain.recalculate_status(order, invoices, deliveries)
        self._snapshot_item_mph(order, invoices, deliveries)
        order.updated_at = utc_now()
        self._order_repo.save(order)
        return saved

    def list_by_order(self, order_id: str) -> List[Delivery]:
        return self._delivery_repo.list_by_order(order_id)

    def get_order_with_status(
        self, order_id: str
    ) -> tuple[CustomizationOrder, List[Delivery], list]:
        try:
            order = self._resolve_order(order_id)
        except ValidationError:
            return None, [], []
        deliveries = self._delivery_repo.list_by_order(order.id)
        invoices = self._invoice_repo.list_by_order(order.id)
        return order, deliveries, invoices
