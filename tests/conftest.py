"""In-memory fake repositories for unit tests."""

from copy import deepcopy
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.accounting.entities import Account, Voucher
from vaybooks.bms.domain.activities.entities import ActivityConfig
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.deliveries.entities import Delivery
from vaybooks.bms.domain.expenses.entities import Expense
from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.orders.entities import CustomizationOrder
from vaybooks.bms.domain.orders.order_refs import order_ref_search_variants
from vaybooks.bms.domain.orders.value_objects import BillRegistryEntry
from vaybooks.bms.domain.shared.enums import AccountType, ActivityType, OrderStatus
from vaybooks.bms.domain.time_tracking.entities import TimeEntry


class FakeCustomerRepository:
    def __init__(self):
        self._store: Dict[str, Customer] = {}

    def save(self, customer: Customer) -> Customer:
        self._store[customer.id] = customer
        return customer

    def find_by_id(self, customer_id: str) -> Optional[Customer]:
        return self._store.get(customer_id)

    def find_by_phone(self, phone: str) -> Optional[Customer]:
        phone = (phone or "").strip()
        if not phone:
            return None
        for c in self._store.values():
            if c.phone_number == phone:
                return c
        return None

    def find_by_gstin(self, gstin: str) -> Optional[Customer]:
        gstin = (gstin or "").strip().upper()
        if not gstin:
            return None
        for c in self._store.values():
            if (c.gstin or "").strip().upper() == gstin:
                return c
        return None

    def search(self, query: str) -> List[Customer]:
        return list(self._store.values())

    def list_all(self) -> List[Customer]:
        return list(self._store.values())


class FakeAccountRepository:
    def __init__(self):
        self._store: Dict[str, Account] = {}

    def save(self, account: Account) -> Account:
        self._store[account.id] = account
        return account

    def find_by_id(self, account_id: str) -> Optional[Account]:
        return self._store.get(account_id)

    def find_by_name(self, name: str) -> Optional[Account]:
        for a in self._store.values():
            if a.account_name == name:
                return a
        return None

    def find_customer_account(self, customer_id: str) -> Optional[Account]:
        for a in self._store.values():
            if a.linked_customer_id == customer_id:
                return a
        return None

    def find_vendor_account(self, vendor_id: str) -> Optional[Account]:
        for a in self._store.values():
            if a.linked_vendor_id == vendor_id:
                return a
        return None

    def find_worker_account(self, worker_id: str) -> Optional[Account]:
        for a in self._store.values():
            if a.linked_worker_id == worker_id:
                return a
        return None

    def customer_balances_by_customer(self) -> dict:
        return {
            str(a.linked_customer_id): a.current_balance
            for a in self._store.values()
            if a.linked_customer_id
        }

    def list_all(self, active_only: bool = True) -> List[Account]:
        return list(self._store.values())

    def update_balance(self, account_id: str, debit: float, credit: float) -> None:
        acc = self._store[account_id]
        acc.current_balance += debit - credit

    def delete(self, account_id: str) -> None:
        self._store.pop(account_id, None)


class FakeVoucherRepository:
    def __init__(self):
        self._store: Dict[str, Voucher] = {}

    def save(self, voucher: Voucher) -> Voucher:
        self._store[voucher.id] = voucher
        return voucher

    def find_by_id(self, voucher_id: str) -> Optional[Voucher]:
        return self._store.get(voucher_id)

    def find_by_number(self, voucher_number: str) -> Optional[Voucher]:
        for v in self._store.values():
            if v.voucher_number == voucher_number:
                return v
        return None

    def list_by_account(self, account_id: str) -> List[Voucher]:
        return [
            v for v in self._store.values()
            if any(l.account_id == account_id for l in v.lines)
        ]

    def list_by_order(self, order_id: str) -> List[Voucher]:
        return [v for v in self._store.values() if v.reference_order_id == order_id]

    def list_all(self) -> List[Voucher]:
        return list(self._store.values())

    def delete(self, voucher_id: str) -> None:
        self._store.pop(voucher_id, None)


class FakeOrderRepository:
    def __init__(self):
        self._store: Dict[str, CustomizationOrder] = {}

    def save(self, order: CustomizationOrder) -> CustomizationOrder:
        self._store[order.id] = deepcopy(order)
        return order

    def find_by_id(self, order_id: str) -> Optional[CustomizationOrder]:
        for candidate in order_ref_search_variants(order_id) or [order_id]:
            o = self._store.get(candidate)
            if o is not None:
                return deepcopy(o)
        return None

    def find_by_order_number(self, order_number: str) -> Optional[CustomizationOrder]:
        for candidate in order_ref_search_variants(order_number) or [order_number]:
            for o in self._store.values():
                if o.order_number == candidate:
                    return deepcopy(o)
        return None

    def find_by_order_activity_id(self, order_activity_id: str) -> Optional[CustomizationOrder]:
        for o in self._store.values():
            for a in o.order_activities:
                if a.order_activity_id == order_activity_id:
                    return deepcopy(o)
        return None

    def search(self, query: str) -> List[CustomizationOrder]:
        return [deepcopy(o) for o in self._store.values()]

    def list_all(self) -> List[CustomizationOrder]:
        return [deepcopy(o) for o in self._store.values()]

    def list_by_status(self, status: str) -> List[CustomizationOrder]:
        return [deepcopy(o) for o in self._store.values() if o.order_status.value == status]

    def list_by_customer(self, customer_id: str) -> List[CustomizationOrder]:
        return [deepcopy(o) for o in self._store.values() if o.customer_id == customer_id]

    def list_recent_by_customer(self, customer_id: str, limit: int = 5) -> List[CustomizationOrder]:
        orders = [o for o in self._store.values() if o.customer_id == customer_id]
        orders.sort(key=lambda o: o.created_at, reverse=True)
        return [deepcopy(o) for o in orders[:limit]]

    def get_customer_summary(self, customer_id: str) -> dict:
        inactive = {"Delivered", "Completed", "Cancelled"}
        orders = [o for o in self._store.values() if o.customer_id == customer_id]
        return {
            "order_count": len(orders),
            "active_count": sum(
                1 for o in orders if o.order_status.value not in inactive
            ),
            "total_invoiced": 0.0,
        }

    def update_order_activity(self, order_id, order_activity_id, updates):
        return self.find_by_id(order_id)


class FakeBillRegistryRepository:
    def __init__(self):
        self._bills: Dict[str, BillRegistryEntry] = {}

    def register(self, entry: BillRegistryEntry) -> BillRegistryEntry:
        if entry.bill_number in self._bills:
            from vaybooks.bms.domain.shared.exceptions import BillNumberExistsError
            raise BillNumberExistsError(f"Bill {entry.bill_number} exists")
        entry.id = entry.id or uuid4().hex
        self._bills[entry.bill_number] = entry
        return entry

    def find_by_bill_number(self, bill_number: str) -> Optional[BillRegistryEntry]:
        return self._bills.get(bill_number.upper())

    def exists(self, bill_number: str) -> bool:
        return bill_number.upper() in self._bills

    def unregister(self, bill_number: str) -> None:
        self._bills.pop(bill_number.upper(), None)


class FakeActivityRepository:
    def __init__(self):
        self._store: Dict[str, ActivityConfig] = {}

    def save(self, activity: ActivityConfig) -> ActivityConfig:
        self._store[activity.id] = activity
        return activity

    def find_by_id(self, activity_id: str) -> Optional[ActivityConfig]:
        return self._store.get(activity_id)

    def find_by_name(self, name: str) -> Optional[ActivityConfig]:
        for a in self._store.values():
            if a.activity_name == name:
                return a
        return None

    def list_all(self, active_only: bool = True) -> List[ActivityConfig]:
        return list(self._store.values())


class FakeTimeTrackingRepository:
    def __init__(self):
        self._store: Dict[str, TimeEntry] = {}

    def save(self, entry: TimeEntry) -> TimeEntry:
        self._store[entry.id] = entry
        return entry

    def find_by_id(self, entry_id: str) -> Optional[TimeEntry]:
        return self._store.get(entry_id)

    def find_by_order(self, order_id: str) -> List[TimeEntry]:
        return [e for e in self._store.values() if e.order_id == order_id]

    def find_by_order_and_activity(self, order_id: str, activity_id: str) -> List[TimeEntry]:
        return [
            e for e in self._store.values()
            if e.order_id == order_id and e.activity_id == activity_id
        ]

    def find_by_bill_number(self, bill_number: str) -> List[TimeEntry]:
        return [e for e in self._store.values() if e.bill_number == bill_number]

    def search(
        self,
        bill_number: Optional[str] = None,
        order_number: Optional[str] = None,
        worker_name: Optional[str] = None,
        activity_name: Optional[str] = None,
        work_date_from: Optional[date] = None,
        work_date_to: Optional[date] = None,
    ) -> List[TimeEntry]:
        entries = list(self._store.values())
        if bill_number:
            needle = bill_number.upper()
            entries = [e for e in entries if needle in e.bill_number.upper()]
        if order_number:
            needle = order_number.lower()
            entries = [e for e in entries if needle in e.order_number.lower()]
        if worker_name:
            needle = worker_name.lower()
            entries = [
                e for e in entries if needle in (e.worker_name or "").lower()
            ]
        if activity_name:
            entries = [e for e in entries if e.activity_name == activity_name]
        if work_date_from is not None:
            entries = [e for e in entries if e.work_date >= work_date_from]
        if work_date_to is not None:
            entries = [e for e in entries if e.work_date <= work_date_to]
        return sorted(entries, key=lambda e: e.work_date, reverse=True)

    def list_all(self) -> List[TimeEntry]:
        return list(self._store.values())

    def delete(self, entry_id: str) -> None:
        self._store.pop(entry_id, None)


class FakeExpenseRepository:
    def __init__(self):
        self._store: Dict[str, Expense] = {}

    def save(self, expense: Expense) -> Expense:
        self._store[expense.id] = expense
        return expense

    def find_by_id(self, expense_id: str) -> Optional[Expense]:
        return self._store.get(expense_id)

    def find_by_order(self, order_id: str) -> List[Expense]:
        return [e for e in self._store.values() if e.order_id == order_id]

    def find_by_bill(self, bill_id: str) -> List[Expense]:
        return [e for e in self._store.values() if e.bill_id == bill_id]

    def list_all(self) -> List[Expense]:
        return list(self._store.values())

    def delete(self, expense_id: str) -> None:
        self._store.pop(expense_id, None)


class FakeDeliveryRepository:
    def __init__(self):
        self._store: Dict[str, Delivery] = {}

    def save(self, delivery: Delivery) -> Delivery:
        self._store[delivery.id] = delivery
        return delivery

    def find_by_id(self, delivery_id: str) -> Optional[Delivery]:
        return self._store.get(delivery_id)

    def list_by_order(self, order_id: str) -> List[Delivery]:
        return [d for d in self._store.values() if d.order_id == order_id]

    def list_all(self) -> List[Delivery]:
        return list(self._store.values())


class FakeInvoiceRepository:
    def __init__(self):
        self._store: Dict[str, Invoice] = {}

    def save(self, invoice: Invoice) -> Invoice:
        self._store[invoice.id] = invoice
        return invoice

    def find_by_id(self, invoice_id: str) -> Optional[Invoice]:
        return self._store.get(invoice_id)

    def find_by_order(self, order_id: str) -> Optional[Invoice]:
        for inv in self._store.values():
            if inv.order_id == order_id:
                return inv
        return None

    def list_by_order(self, order_id: str) -> List[Invoice]:
        return [inv for inv in self._store.values() if inv.order_id == order_id]

    def find_by_bill(self, bill_id: str) -> List[Invoice]:
        return [inv for inv in self._store.values() if bill_id in inv.bill_ids]

    def list_all(self) -> List[Invoice]:
        return list(self._store.values())


class FakeCounterRepository:
    def __init__(self):
        self._counters = {
            "order_number": 0,
            "voucher_number": 0,
            "invoice_number": 0,
            "po_number": 0,
            "grn_number": 0,
            "purchase_return_number": 0,
            "so_number": 0,
            "dn_number": 0,
            "sales_return_number": 0,
            "estimate_number": 0,
            "quotation_number": 0,
            "project_number": 0,
            "project_quotation_number": 0,
            "project_work_order_number": 0,
            "project_ra_number": 0,
            "project_proforma_number": 0,
            "project_variation_number": 0,
            "enquiry_number": 0,
            "project_mr_number": 0,
            "project_rfq_number": 0,
            "project_subcon_number": 0,
            "project_petty_cash_number": 0,
        }
        self._prefixes = {
            "order_number": "CO",
            "voucher_number": "VCH",
            "invoice_number": "INV",
            "po_number": "PO",
            "grn_number": "GRN",
            "purchase_return_number": "PR",
            "so_number": "SO",
            "dn_number": "DN",
            "sales_return_number": "SR",
            "estimate_number": "EST",
            "quotation_number": "QT",
            "project_number": "PRJ",
            "project_quotation_number": "PQ",
            "project_work_order_number": "PWO",
            "project_ra_number": "PRA",
            "project_proforma_number": "PPF",
            "project_variation_number": "PV",
            "enquiry_number": "ENQ",
            "project_mr_number": "PMR",
            "project_rfq_number": "PRFQ",
            "project_subcon_number": "PSC",
            "project_petty_cash_number": "PPC",
        }

    def next(self, counter_name: str) -> str:
        if counter_name not in self._counters:
            self._counters[counter_name] = 0
            self._prefixes.setdefault(counter_name, counter_name[:3].upper())
        self._counters[counter_name] += 1
        prefix = self._prefixes[counter_name]
        return f"{prefix}-{self._counters[counter_name]:04d}"

    def peek(self, counter_name: str) -> str:
        prefix = self._prefixes[counter_name]
        return f"{prefix}-{self._counters[counter_name] + 1:04d}"


class FakeProductCategoryRepository:
    def __init__(self):
        self._store: Dict[str, "ProductCategory"] = {}

    def save(self, category):
        self._store[category.id] = category
        return category

    def find_by_id(self, category_id: str):
        return self._store.get(category_id)

    def find_by_ids(self, category_ids):
        return [self._store[cid] for cid in category_ids if cid in self._store]

    def find_by_name(self, name: str):
        name = (name or "").strip()
        for category in self._store.values():
            if category.name == name:
                return category
        return None

    def find_by_parent_and_name(self, parent_id: str | None, name: str):
        name = (name or "").strip()
        parent_id = parent_id or None
        for category in self._store.values():
            if category.name == name and (category.parent_id or None) == parent_id:
                return category
        return None

    def list_children(self, parent_id: str | None):
        parent_id = parent_id or None
        return [c for c in self._store.values() if (c.parent_id or None) == parent_id]

    def list_all(self, active_only: bool = True):
        if active_only:
            return [c for c in self._store.values() if c.is_active]
        return list(self._store.values())

    def search(self, query: str, *, active_only: bool = True, limit: int = 25):
        text = (query or "").strip().lower()
        items = self.list_all(active_only=active_only)
        if text:
            items = [c for c in items if text in c.name.lower()]
        items = sorted(items, key=lambda c: c.name.lower())
        return items[: max(1, min(int(limit or 25), 50))]

    def delete(self, category_id: str) -> None:
        self._store.pop(category_id, None)


class FakeProductUnitRepository:
    def __init__(self):
        self._store: Dict[str, "ProductUnit"] = {}

    def save(self, unit):
        self._store[unit.id] = unit
        return unit

    def find_by_id(self, unit_id: str):
        return self._store.get(unit_id)

    def find_by_code(self, code: str):
        code = (code or "").strip().lower()
        for unit in self._store.values():
            if unit.code == code:
                return unit
        return None

    def list_all(self, active_only: bool = True):
        if active_only:
            return [u for u in self._store.values() if u.is_active]
        return list(self._store.values())

    def search(self, query: str, *, active_only: bool = True, limit: int = 25):
        text = (query or "").strip().lower()
        items = self.list_all(active_only=active_only)
        if text:
            items = [
                u
                for u in items
                if text in u.code.lower() or text in (u.label or "").lower()
            ]
        items = sorted(items, key=lambda u: u.code.lower())
        return items[: max(1, min(int(limit or 25), 50))]

    def count_products_using(self, unit_id: str) -> int:
        return 0


class FakeInventoryProductRepository:
    def __init__(self):
        self._store: Dict[str, "InventoryProduct"] = {}

    def save(self, product):
        self._store[product.id] = product
        return product

    def find_by_id(self, product_id: str):
        return self._store.get(product_id)

    def find_by_sku(self, sku: str):
        sku = (sku or "").strip()
        for product in self._store.values():
            if product.sku == sku:
                return product
        return None

    def list_all(self, active_only: bool = True):
        if active_only:
            return [p for p in self._store.values() if p.is_active]
        return list(self._store.values())

    def list_by_category(self, category_id: str):
        return [
            p for p in self._store.values()
            if category_id in (p.category_ids or [])
            or p.category_id == category_id
        ]

    def count_by_category(self, category_id: str) -> int:
        return len(self.list_by_category(category_id))

    def count_by_unit(self, unit_id: str) -> int:
        return sum(1 for p in self._store.values() if p.unit_id == unit_id)

    def search(self, query: str):
        q = (query or "").strip().lower()
        if not q:
            return self.list_all()
        return [
            p for p in self._store.values()
            if q in p.name.lower() or q in p.sku.lower()
        ]


class FakeProductRateHistoryRepository:
    def __init__(self):
        self._store: Dict[str, "ProductRatePeriod"] = {}

    def save(self, period):
        self._store[period.id] = period
        return period

    def find_by_id(self, period_id: str):
        return self._store.get(period_id)

    def list_for_product(self, product_id: str):
        return [p for p in self._store.values() if p.product_id == product_id]

    def delete(self, period_id: str) -> None:
        self._store.pop(period_id, None)


class FakeStockMovementRepository:
    def __init__(self):
        self._store: Dict[str, "StockMovement"] = {}

    def save(self, movement):
        self._store[movement.id] = movement
        return movement

    def list_by_product(self, product_id: str):
        return [m for m in self._store.values() if m.product_id == product_id]

    def list_all(self):
        return list(self._store.values())

    def list_by_reference(self, reference_id: str):
        return [
            m for m in self._store.values() if m.reference_id == reference_id
        ]

    def delete(self, movement_id: str) -> None:
        self._store.pop(movement_id, None)


def make_inventory_app_service():
    from vaybooks.bms.application.inventory_app_service import InventoryAppService
    from vaybooks.bms.domain.inventory.rate_history_service import ProductRateHistoryService

    selling = FakeProductRateHistoryRepository()
    mrp = FakeProductRateHistoryRepository()
    gst = FakeProductRateHistoryRepository()
    rate_history = ProductRateHistoryService(selling, mrp, gst)

    service = InventoryAppService(
        FakeProductCategoryRepository(),
        FakeInventoryProductRepository(),
        FakeStockMovementRepository(),
        FakeProductUnitRepository(),
        rate_history=rate_history,
    )
    service.find_or_create_unit("pcs", "Pieces")
    return _ensure_test_product_defaults(service)


def create_test_product(service, sku: str, name: str, category_ids, **kwargs):
    """Create a product with default unit and valid pricing for tests."""
    unit = service.find_or_create_unit(kwargs.pop("unit_code", "pcs"))
    return service.create_product(
        sku,
        name,
        category_ids,
        unit_id=unit.id,
        selling_rate=kwargs.pop("selling_rate", 100.0),
        mrp=kwargs.pop("mrp", 200.0),
        gst_rate=kwargs.pop("gst_rate", 5.0),
        **kwargs,
    )


def _ensure_test_product_defaults(service):
    """Back-compat for tests that omit unit/pricing on create_product."""
    original_create = service.create_product

    def create_product_with_defaults(*args, **kwargs):
        if not kwargs.get("unit_id") and not kwargs.get("pending_unit_code"):
            kwargs["unit_id"] = service.find_or_create_unit("pcs").id
        if float(kwargs.get("selling_rate") or 0) <= 0:
            kwargs.setdefault("selling_rate", 100.0)
        if float(kwargs.get("mrp") or 0) <= 0:
            kwargs.setdefault("mrp", 200.0)
        if "gst_rate" not in kwargs:
            kwargs["gst_rate"] = 5.0
        return original_create(*args, **kwargs)

    service.create_product = create_product_with_defaults
    return service
