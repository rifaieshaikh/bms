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
        self._counters = {"order_number": 0, "voucher_number": 0, "invoice_number": 0}
        self._prefixes = {"order_number": "CO", "voucher_number": "VCH", "invoice_number": "INV"}

    def next(self, counter_name: str) -> str:
        self._counters[counter_name] += 1
        prefix = self._prefixes[counter_name]
        return f"{prefix}-{self._counters[counter_name]:04d}"
