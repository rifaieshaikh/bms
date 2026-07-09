from datetime import date, datetime, timedelta
from typing import List, Optional

from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.dtos import ActivityCompletionResult, CreateOrderRequest
from vaybooks.bms.domain.accounting.repository import AccountRepository, CounterRepository, VoucherRepository
from vaybooks.bms.domain.accounting.services import AccountingDomainService
from vaybooks.bms.domain.activities.repository import ActivityRepository
from vaybooks.bms.domain.activities.services import ActivityDomainService
from vaybooks.bms.domain.customers.repository import CustomerRepository
from vaybooks.bms.domain.customers.services import CustomerDomainService
from vaybooks.bms.domain.deliveries.repository import DeliveryRepository
from vaybooks.bms.domain.expenses.repository import ExpenseRepository
from vaybooks.bms.domain.expenses.services import ExpenseDomainService
from vaybooks.bms.domain.invoices.repository import InvoiceRepository
from vaybooks.bms.domain.orders.entities import CustomizationItem, CustomizationOrder
from vaybooks.bms.domain.orders.repository import BillRegistryRepository, OrderRepository
from vaybooks.bms.domain.orders.services import OrderDomainService
from vaybooks.bms.domain.orders.order_refs import compact_order_ref
from vaybooks.bms.domain.shared.date_utils import today, utc_now
from vaybooks.bms.domain.time_tracking.repository import TimeTrackingRepository


class OrderAppService:
    def __init__(
        self,
        order_repo: OrderRepository,
        bill_registry_repo: BillRegistryRepository,
        customer_repo: CustomerRepository,
        account_repo: AccountRepository,
        activity_repo: ActivityRepository,
        time_repo: TimeTrackingRepository,
        expense_repo: ExpenseRepository,
        voucher_repo: VoucherRepository,
        counter_repo: CounterRepository,
        invoice_repo: Optional[InvoiceRepository] = None,
        delivery_repo: Optional[DeliveryRepository] = None,
        accounting_service: Optional[AccountingAppService] = None,
    ):
        self._order_repo = order_repo
        self._order_domain = OrderDomainService(order_repo, bill_registry_repo)
        self._customer_domain = CustomerDomainService(customer_repo)
        self._activity_domain = ActivityDomainService()
        self._expense_domain = ExpenseDomainService(expense_repo)
        self._accounting_domain = AccountingDomainService(account_repo, voucher_repo)
        self._activity_repo = activity_repo
        self._time_repo = time_repo
        self._counter_repo = counter_repo
        self._invoice_repo = invoice_repo
        self._delivery_repo = delivery_repo
        self._accounting_service = accounting_service

    def _release_order_advance(self, order: CustomizationOrder) -> None:
        if not self._accounting_service:
            return
        customer_account = self._accounting_service.get_customer_account(order.customer_id)
        if not customer_account:
            return
        self._accounting_service.release_order_advance(
            order.id,
            customer_account.id,
            order.order_number,
        )

    def _recalculate_order(self, order: CustomizationOrder) -> None:
        invoices = (
            self._invoice_repo.list_by_order(order.id) if self._invoice_repo else []
        )
        deliveries = (
            self._delivery_repo.list_by_order(order.id) if self._delivery_repo else []
        )
        self._order_domain.recalculate_status(order, invoices, deliveries)

    def create_customization_order(self, request: CreateOrderRequest) -> CustomizationOrder:
        customer = self._customer_domain.find_or_create(
            customer_name=request.customer_name,
            phone_number=request.phone_number,
            alternate_phone_number=request.alternate_phone_number,
            address=request.address,
        )
        account_name = CustomerDomainService.build_account_name(customer)
        customer_account = self._accounting_domain.ensure_customer_account(
            customer.id, account_name
        )

        order_number = self._counter_repo.next("order_number")
        activity_configs = self._activity_repo.list_all()

        order = CustomizationOrder(
            order_number=order_number,
            customer_id=customer.id,
            customer_name=customer.customer_name,
            phone_number=customer.phone_number,
            order_date=today(),
            expected_delivery_date=request.expected_delivery_date
            or (today() + timedelta(days=7)),
            advance_amount=request.advance_amount,
            notes=request.notes,
        )

        item_rows = request.customization_items or []
        if not item_rows and request.bill_numbers:
            item_rows = [
                {
                    "bill_number": row["bill_number"],
                    "item_description": row.get("item_description", ""),
                    "required_activities": request.required_activities,
                }
                for row in request.bill_numbers
            ]

        for item_data in item_rows:
            self._order_domain.add_customization_item(
                order,
                item_data["bill_number"],
                item_data.get("item_description", ""),
                activity_configs,
                item_data.get("required_activities", request.required_activities),
                expected_delivery_date=item_data.get("expected_delivery_date"),
            )

        self._order_domain.validate_order(order)

        saved = self._order_repo.save(order)

        if request.advance_amount > 0 and request.receiving_account_id:
            receiving = self._accounting_domain._account_repo.find_by_id(
                request.receiving_account_id
            )
            if receiving:
                advance = self._accounting_domain.get_advance_from_customers_account()
                voucher_number = self._counter_repo.next("voucher_number")
                voucher = self._accounting_domain.build_advance_receipt_voucher(
                    voucher_number=voucher_number,
                    voucher_date=datetime.combine(today(), datetime.min.time()),
                    description=f"Advance for {order_number}",
                    receiving_account_id=receiving.id,
                    receiving_account_name=receiving.account_name,
                    customer_account_id=customer_account.id,
                    customer_account_name=customer_account.account_name,
                    advance_account_id=advance.id,
                    advance_account_name=advance.account_name,
                    amount=request.advance_amount,
                    reference_order_id=saved.id,
                )
                self._accounting_domain.save_voucher(voucher)

        return saved

    def search_customization_orders(self, query: str) -> List[CustomizationOrder]:
        if not query.strip():
            return self._order_repo.list_all()
        return self._order_repo.search(query)

    def get_order_detail(self, order_id: str) -> Optional[CustomizationOrder]:
        return self._order_repo.find_by_id(order_id)

    def add_bill_number(
        self,
        order_id: str,
        bill_number: str,
        item_description: str = "",
        required_activities: Optional[dict] = None,
    ) -> CustomizationOrder:
        order = self._order_repo.find_by_id(order_id)
        activity_configs = self._activity_repo.list_all()
        required_map = required_activities or {}
        if not required_map and order.order_activities:
            template_item_id = order.order_activities[0].bill_id
            for act in order.order_activities:
                if act.bill_id == template_item_id and act.is_required:
                    required_map[act.activity_name] = True

        self._order_domain.add_customization_item(
            order,
            bill_number,
            item_description,
            activity_configs,
            required_map,
        )

        self._recalculate_order(order)
        return self._order_repo.save(order)

    def list_all_customization_items(self) -> List[dict]:
        rows = []
        for order in self._order_repo.list_all():
            for item in order.customization_items:
                rows.append(
                    {
                        "order_id": order.id,
                        "order_number": order.order_number,
                        "customer_name": order.customer_name,
                        "phone_number": order.phone_number,
                        "item_id": item.item_id,
                        "bill_number": item.bill_number,
                        "description": item.description,
                        "item_status": item.item_status.value,
                        "order_status": order.order_status.value,
                        "sell_amount": item.sell_amount,
                        "margin_amount": item.margin_amount,
                        "margin_per_hour": item.margin_per_hour,
                        "mph_snapshot_at": item.mph_snapshot_at,
                    }
                )
        return rows

    def search_customization_items(self, query: str) -> List[dict]:
        if not query.strip():
            return self.list_all_customization_items()
        needle = query.strip().lower()
        compact_needle = compact_order_ref(needle)
        return [
            row
            for row in self.list_all_customization_items()
            if needle in row["bill_number"].lower()
            or needle in row["description"].lower()
            or needle in row["order_number"].lower()
            or compact_needle in compact_order_ref(row["order_number"]).lower()
            or needle in row["customer_name"].lower()
        ]

    def prepare_complete_activity(
        self, order_activity_id: str
    ) -> ActivityCompletionResult:
        order = self._order_repo.find_by_order_activity_id(order_activity_id)
        if not order:
            raise ValueError("Order not found for activity")

        order_activity = order.get_activity_by_id(order_activity_id)
        activity_config = self._activity_repo.find_by_id(order_activity.activity_id)
        time_entries = self._time_repo.find_by_order_and_activity(
            order.id, order_activity.activity_id
        )

        preview = self._activity_domain.prepare_completion(
            order, order_activity, activity_config, time_entries
        )

        return ActivityCompletionResult(
            order_id=preview.order_id,
            order_activity_id=preview.order_activity_id,
            activity_name=preview.activity_name,
            needs_expense=preview.needs_expense,
            total_hours=preview.total_hours,
            total_duration_minutes=preview.total_duration_minutes,
            purchase_price=preview.purchase_price,
            selling_price=preview.selling_price,
            total_purchase_price=preview.total_purchase_price,
            total_selling_price=preview.total_selling_price,
            expense_source=preview.expense_source,
            bill_id=preview.bill_id,
            bill_number=preview.bill_number,
            activity_id=preview.activity_id,
            order_number=preview.order_number,
        )

    def finalize_complete_activity(
        self,
        order_activity_id: str,
        completed_by: str,
        add_expense: bool = True,
        purchase_price: float = 0,
        selling_price: float = 0,
        vendor_or_worker_name: str = "",
        notes: str = "",
    ) -> CustomizationOrder:
        order = self._order_repo.find_by_order_activity_id(order_activity_id)
        order_activity = order.get_activity_by_id(order_activity_id)
        activity_config = self._activity_repo.find_by_id(order_activity.activity_id)

        if add_expense:
            preview = self.prepare_complete_activity(order_activity_id)
            from vaybooks.bms.domain.activities.services import ActivityCompletionPreview

            activity_preview = ActivityCompletionPreview(
                order_activity_id=preview.order_activity_id,
                activity_id=preview.activity_id,
                activity_name=preview.activity_name,
                order_id=preview.order_id,
                order_number=preview.order_number,
                needs_expense=True,
                total_duration_minutes=preview.total_duration_minutes,
                total_hours=preview.total_hours,
                purchase_price=purchase_price or preview.purchase_price,
                selling_price=selling_price or preview.selling_price,
                expense_source=preview.expense_source,
                bill_id=preview.bill_id,
                bill_number=preview.bill_number,
            )
            self._expense_domain.create_from_activity_completion(
                activity_preview,
                expense_date=today(),
                purchase_price=purchase_price or preview.purchase_price,
                selling_price=selling_price or preview.selling_price,
                vendor_or_worker_name=vendor_or_worker_name,
                notes=notes,
            )

        self._order_domain.mark_activity_completed(
            order, order_activity_id, completed_by
        )
        self._recalculate_order(order)
        return self._order_repo.save(order)

    def complete_activity(
        self,
        order_activity_id: str,
        completed_by: str,
        purchase_price: float = 0,
        selling_price: float = 0,
        vendor_or_worker_name: str = "",
        notes: str = "",
        add_expense: bool = True,
    ) -> CustomizationOrder:
        return self.finalize_complete_activity(
            order_activity_id,
            completed_by,
            add_expense=add_expense,
            purchase_price=purchase_price,
            selling_price=selling_price,
            vendor_or_worker_name=vendor_or_worker_name,
            notes=notes,
        )

    def skip_activity(
        self, order_activity_id: str, completed_by: str
    ) -> CustomizationOrder:
        order = self._order_repo.find_by_order_activity_id(order_activity_id)
        self._order_domain.skip_activity(order, order_activity_id, completed_by)
        self._recalculate_order(order)
        return self._order_repo.save(order)

    def cancel_order(self, order_id: str) -> CustomizationOrder:
        order = self._order_repo.find_by_id(order_id)
        self._order_domain.cancel_order(order)
        saved = self._order_repo.save(order)
        self._release_order_advance(saved)
        return saved

    def complete_order(self, order_id: str) -> CustomizationOrder:
        order = self._order_repo.find_by_id(order_id)
        self._order_domain.complete_order(order)
        saved = self._order_repo.save(order)
        self._release_order_advance(saved)
        return saved

    def list_by_status(self, status: str) -> List[CustomizationOrder]:
        return self._order_repo.list_by_status(status)

    def list_by_customer(self, customer_id: str) -> List[CustomizationOrder]:
        return self._order_repo.list_by_customer(customer_id)

    def list_recent_by_customer(
        self, customer_id: str, limit: int = 5
    ) -> List[CustomizationOrder]:
        """Latest N orders for a customer (newest first)."""
        return self._order_repo.list_recent_by_customer(customer_id, limit)

    def get_customer_summary(self, customer_id: str) -> dict:
        """Order counts and total invoiced for one customer (aggregated)."""
        return self._order_repo.get_customer_summary(customer_id)

    def order_counts_by_customer(self) -> dict:
        """Map of customer_id -> order count for all customers (one query)."""
        return self._order_repo.counts_by_customer()

    def update_order_delivery_date(
        self,
        order_id: str,
        expected_delivery_date,
        propagate_to_items: bool = True,
    ) -> CustomizationOrder:
        order = self._order_repo.find_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        if not expected_delivery_date:
            raise ValueError("Expected delivery date is required")
        old_etd = order.expected_delivery_date
        order.expected_delivery_date = expected_delivery_date
        if propagate_to_items:
            # Only items still following the order date (never individually
            # overridden) move with it; per-item overrides are preserved.
            for item in order.customization_items:
                if item.expected_delivery_date in (None, old_etd):
                    item.expected_delivery_date = expected_delivery_date
                    item.updated_at = utc_now()
        order.updated_at = utc_now()
        self._recalculate_order(order)
        return self._order_repo.save(order)

    def update_customization_item(
        self,
        order_id: str,
        item_id: str,
        bill_number: str,
        description: str,
        expected_delivery_date=None,
    ) -> CustomizationOrder:
        order = self._order_repo.find_by_id(order_id)
        self._order_domain.update_customization_item(
            order, item_id, bill_number, description,
            expected_delivery_date=expected_delivery_date,
        )
        self._recalculate_order(order)
        return self._order_repo.save(order)

    def add_activity_to_item(
        self,
        order_id: str,
        item_id: str,
        activity_id: str,
    ) -> CustomizationOrder:
        order = self._order_repo.find_by_id(order_id)
        config = self._activity_repo.find_by_id(activity_id)
        if not config:
            raise ValueError("Activity not found")
        self._order_domain.add_activity_to_item(
            order,
            item_id,
            config.id,
            config.activity_name,
        )
        self._recalculate_order(order)
        return self._order_repo.save(order)

    def get_activity_statuses(self, activity_id: str) -> List[str]:
        config = self._activity_repo.find_by_id(activity_id)
        if config and getattr(config, "statuses", None):
            return list(config.statuses)
        return ["Created", "Completed"]

    def update_activity_status(
        self,
        order_id: str,
        order_activity_id: str,
        status: str,
    ) -> CustomizationOrder:
        order = self._order_repo.find_by_id(order_id)
        activity = order.get_activity_by_id(order_activity_id)
        if not activity:
            raise ValueError("Activity not found")
        allowed = self.get_activity_statuses(activity.activity_id)
        self._order_domain.set_activity_status(
            order, order_activity_id, status, allowed_statuses=allowed
        )
        self._recalculate_order(order)
        return self._order_repo.save(order)

    def remove_activity_from_item(
        self,
        order_id: str,
        order_activity_id: str,
    ) -> CustomizationOrder:
        order = self._order_repo.find_by_id(order_id)
        self._order_domain.remove_activity_from_item(order, order_activity_id)
        self._recalculate_order(order)
        return self._order_repo.save(order)

    def get_customization_item_detail(
        self, order_id: str, item_id: str
    ) -> Optional[tuple[CustomizationOrder, CustomizationItem]]:
        order = self._order_repo.find_by_id(order_id)
        if not order:
            return None
        item = order.get_item_by_id(item_id)
        if not item:
            return None
        return order, item
