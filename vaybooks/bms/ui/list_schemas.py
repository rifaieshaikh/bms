"""Per-entity list schemas: filters + sort options.

Most string filters are strict equality (``EXACT``). Customers and vendors
use case-insensitive ``REGEX`` on text fields. Cross-field combination is
AND; within a single multiselect it is OR (value ``in`` list).
"""

from __future__ import annotations

from vaybooks.bms.domain.shared.enums import (
    AccountType,
    ActivityCategory,
    ActivityType,
    CustomizationItemStatus,
    OrderStatus,
    PartyRegistrationType,
    PersonType,
    VoucherType,
)
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui.pagination import (
    CARD_PAGE_SIZE,
    TRIAL_BALANCE_PAGE_SIZE,
    VOUCHER_PAGE_SIZE,
)
from vaybooks.bms.ui.inventory_list_schemas import (
    INVENTORY_CATEGORIES,
    INVENTORY_PRODUCTS,
    INVENTORY_STOCK,
    INVENTORY_STOCK_LEDGER,
)


def _enum_opts(enum_cls) -> list[tuple]:
    return [(e.value, e.value) for e in enum_cls]


# --- option loaders (id/value, label) ---------------------------------------
def _customers(services):
    return [(c.id, c.customer_name) for c in services["customers"].list_all_customers()]


def _vendors(services):
    return [(v.id, v.vendor_name) for v in services["vendors"].list_all_vendors()]


def _accounts(services):
    return [(a.id, a.account_name)
            for a in services["accounting"].list_accounts(active_only=False)]


def _store_accounts(services):
    return [(a.id, a.account_name) for a in services["accounting"].get_store_accounts()]


def _customer_accounts(services):
    return [(a.id, a.account_name)
            for a in services["accounting"].list_accounts(active_only=False)
            if a.linked_customer_id]


def _vendor_accounts(services):
    return [(a.id, a.account_name)
            for a in services["accounting"].list_accounts(active_only=False)
            if a.linked_vendor_id]


def _expense_accounts(services):
    return [(a.id, a.account_name)
            for a in services["accounting"].list_accounts(active_only=False)
            if a.account_type == AccountType.EXPENSE]


def _activity_names(services):
    return [(a.activity_name, a.activity_name)
            for a in services["activities"].list_activities(active_only=False)]


def _services_by_id(services):
    return [(s.id, s.service_name)
            for s in services["vendor_services"].list_services(active_only=False)]


def _inventory_categories(services):
    inventory = services.get("inventory")
    if inventory is None:
        return []
    return [
        (c.id, c.name)
        for c in inventory.list_categories(active_only=False)
    ]


def _inventory_products(services):
    inventory = services.get("inventory")
    if inventory is None:
        return []
    return [
        (p.id, f"{p.sku} — {p.name}")
        for p in inventory.list_products(active_only=False)
    ]


OPTION_LOADERS = {
    "customers": _customers,
    "vendors": _vendors,
    "accounts": _accounts,
    "store_accounts": _store_accounts,
    "customer_accounts": _customer_accounts,
    "vendor_accounts": _vendor_accounts,
    "expense_accounts": _expense_accounts,
    "activity_names": _activity_names,
    "services_by_id": _services_by_id,
    "inventory_categories": _inventory_categories,
    "inventory_products": _inventory_products,
}


# --- custom match predicates -------------------------------------------------
def _match_order_bill(order, value) -> bool:
    target = str(value).strip()
    return any((getattr(i, "bill_number", "") or "") == target
               for i in getattr(order, "customization_items", []))


def _match_has_advance(order, _value) -> bool:
    return (getattr(order, "advance_amount", 0) or 0) > 0


def _match_mph_state(row, value) -> bool:
    snap = row.get("mph_snapshot_at") if isinstance(row, dict) \
        else getattr(row, "mph_snapshot_at", None)
    return (snap is not None) if value == "set" else (snap is None)


def _match_customer_has_orders(customer, value) -> bool:
    count = getattr(customer, "order_count", 0) or 0
    return count > 0 if value == "with" else count == 0


def _match_vendor_balance(vendor, value) -> bool:
    bal = getattr(vendor, "current_balance", 0.0) or 0.0
    if value == "dr":
        return bal > 0
    if value == "cr":
        return bal < 0
    return bal == 0


def _match_account_active(account, _value) -> bool:
    return bool(getattr(account, "is_active", False))


def _match_account_store(account, value) -> bool:
    is_store = bool(getattr(account, "is_store_account", False))
    return is_store if value == "yes" else (not is_store)


def _match_account_linked(account, value) -> bool:
    cust = getattr(account, "linked_customer_id", None)
    vend = getattr(account, "linked_vendor_id", None)
    if value == "customer":
        return bool(cust)
    if value == "vendor":
        return bool(vend)
    return not cust and not vend


def _match_activity_active(activity, _value) -> bool:
    return bool(getattr(activity, "is_active", False))


def _match_activity_time_tracking(activity, value) -> bool:
    flag = bool(getattr(activity, "requires_time_tracking", False))
    return flag if value == "yes" else (not flag)


def _match_service_active(service, _value) -> bool:
    return bool(getattr(service, "is_active", False))


def _match_voucher_debit_account(voucher, value) -> bool:
    return any(line.account_id == value and line.debit_amount > 0
               for line in voucher.lines)


def _match_voucher_credit_account(voucher, value) -> bool:
    return any(line.account_id == value and line.credit_amount > 0
               for line in voucher.lines)


def _match_voucher_any_account(voucher, value) -> bool:
    return any(line.account_id == value for line in voucher.lines)


def _match_voucher_service(voucher, value) -> bool:
    return getattr(voucher, "reference_service_id", None) == value


# --- schemas -----------------------------------------------------------------
ORDERS = ListSchema(
    entity_key="orders",
    title="Customization Orders",
    filter_fields=[
        FilterField("order_number", "Order number", F.EXACT),
        FilterField("bill_number", "Bill number", F.EXACT, match=_match_order_bill),
        FilterField("customer_id", "Customer", F.ENTITY_SELECT,
                    options_loader="customers"),
        FilterField("customer_name", "Customer name", F.EXACT),
        FilterField("phone_number", "Phone", F.EXACT),
        FilterField("statuses", "Order status", F.MULTISELECT,
                    record_attr="order_status", options=_enum_opts(OrderStatus)),
        FilterField("order_date", "Order date", F.DATE_RANGE),
        FilterField("etd", "Expected delivery", F.DATE_RANGE,
                    record_attr="expected_delivery_date"),
        FilterField("has_advance", "Has advance", F.CHECKBOX,
                    match=_match_has_advance),
    ],
    sort_options=[
        SortOption("created_at", "Created (newest)"),
        SortOption("order_date", "Order date"),
        SortOption("expected_delivery_date", "Expected delivery"),
        SortOption("order_number", "Order number"),
        SortOption("customer_name", "Customer name"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

ITEMS = ListSchema(
    entity_key="items",
    title="Customization Items",
    filter_fields=[
        FilterField("bill_number", "Bill number", F.EXACT),
        FilterField("description", "Description", F.EXACT),
        FilterField("order_number", "Order number", F.EXACT),
        FilterField("customer_name", "Customer name", F.EXACT),
        FilterField("phone_number", "Phone", F.EXACT),
        FilterField("item_statuses", "Item status", F.MULTISELECT,
                    record_attr="item_status",
                    options=_enum_opts(CustomizationItemStatus)),
        FilterField("order_statuses", "Order status", F.MULTISELECT,
                    record_attr="order_status", options=_enum_opts(OrderStatus)),
        FilterField("mph_state", "MPH snapshotted", F.SELECT,
                    options=[("set", "Snapshotted"), ("null", "Not snapshotted")],
                    match=_match_mph_state),
        FilterField("min_mph", "Min MPH (₹/h)", F.NUMBER_MIN,
                    record_attr="margin_per_hour"),
    ],
    sort_options=[
        SortOption("bill_number", "Bill number"),
        SortOption("customer_name", "Customer name"),
        SortOption("item_status", "Item status"),
        SortOption("margin_per_hour", "MPH"),
    ],
    default_sort="bill_number",
    page_size=CARD_PAGE_SIZE,
)

MEASUREMENTS = ListSchema(
    entity_key="measurements",
    title="Measurements",
    filter_fields=[
        FilterField("measurement_number", "Measurement number", F.EXACT),
        FilterField(
            "customer_id",
            "Customer",
            F.ENTITY_SELECT,
            options_loader="customers",
        ),
        FilterField("customer_name", "Customer name", F.REGEX),
        FilterField("wearer_name", "Wearer name", F.REGEX),
        FilterField(
            "person_types",
            "Person type",
            F.MULTISELECT,
            record_attr="person_type",
            options=_enum_opts(PersonType),
        ),
        FilterField("measured_at", "Measured on", F.DATE_RANGE),
    ],
    sort_options=[
        SortOption("measured_at", "Measured (newest)"),
        SortOption("created_at", "Created (newest)"),
        SortOption("measurement_number", "Measurement number"),
        SortOption("customer_name", "Customer name"),
        SortOption("wearer_name", "Wearer name"),
    ],
    default_sort="measured_at",
    page_size=CARD_PAGE_SIZE,
)

CUSTOMERS = ListSchema(
    entity_key="customers",
    title="Customers",
    filter_fields=[
        FilterField("customer_name", "Customer name", F.REGEX),
        FilterField("phone_number", "Phone", F.REGEX),
        FilterField("alternate_phone_number", "Alternate phone", F.REGEX),
        FilterField("gstin", "GSTIN", F.REGEX),
        FilterField("registration_type", "Registration type", F.SELECT,
                    options=_enum_opts(PartyRegistrationType)),
        FilterField("has_orders", "Has orders", F.SELECT,
                    options=[("with", "With orders"), ("without", "Without orders")],
                    match=_match_customer_has_orders),
    ],
    sort_options=[
        SortOption("created_at", "Created (newest)"),
        SortOption("customer_name", "Customer name"),
        SortOption("order_count", "Order count"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

VENDORS = ListSchema(
    entity_key="vendors",
    title="Vendors",
    filter_fields=[
        FilterField("vendor_name", "Vendor name", F.REGEX),
        FilterField("phone_number", "Phone", F.REGEX),
        FilterField("alternate_phone_number", "Alternate phone", F.REGEX),
        FilterField("balance_state", "Payable balance", F.SELECT,
                    options=[("dr", "Dr"), ("cr", "Cr"), ("zero", "Zero")],
                    match=_match_vendor_balance),
    ],
    sort_options=[
        SortOption("created_at", "Created (newest)"),
        SortOption("vendor_name", "Vendor name"),
        SortOption("current_balance", "Payable balance"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

TIME = ListSchema(
    entity_key="time",
    title="Time Log",
    filter_fields=[
        FilterField("work_date", "Work date", F.DATE_RANGE),
        FilterField("bill_number", "Bill number", F.EXACT),
        FilterField("order_number", "Order number", F.EXACT),
        FilterField("worker_name", "Employee", F.EXACT),
        FilterField("activity_name", "Activity", F.SELECT,
                    options_loader="activity_names"),
    ],
    sort_options=[
        SortOption("work_date", "Work date (newest)"),
        SortOption("created_at", "Created (newest)"),
        SortOption("duration_minutes", "Duration"),
        SortOption("bill_number", "Bill number"),
    ],
    default_sort="work_date",
    page_size=CARD_PAGE_SIZE,
)

ACCOUNTS = ListSchema(
    entity_key="accounts",
    title="Chart of Accounts",
    filter_fields=[
        FilterField("account_name", "Account name", F.EXACT),
        FilterField("types", "Account type", F.MULTISELECT,
                    record_attr="account_type", options=_enum_opts(AccountType)),
        FilterField("active_only", "Active only", F.CHECKBOX,
                    match=_match_account_active),
        FilterField("store_filter", "Store account", F.SELECT,
                    options=[("yes", "Store"), ("no", "Non-store")],
                    match=_match_account_store),
        FilterField("linked", "Linked entity", F.SELECT,
                    options=[("customer", "Customer"), ("vendor", "Vendor"),
                             ("standalone", "Standalone")],
                    match=_match_account_linked),
    ],
    sort_options=[
        SortOption("created_at", "Created (newest)"),
        SortOption("account_name", "Account name"),
        SortOption("account_type", "Account type"),
        SortOption("current_balance", "Balance"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

VOUCHERS = ListSchema(
    entity_key="vouchers",
    title="All Vouchers",
    filter_fields=[
        FilterField("voucher_number", "Voucher number", F.EXACT),
        FilterField("description", "Description", F.EXACT),
        FilterField("types", "Voucher type", F.MULTISELECT,
                    record_attr="voucher_type", options=_enum_opts(VoucherType)),
        FilterField("voucher_date", "Voucher date", F.DATE_RANGE),
        FilterField("min_amount", "Min amount (₹)", F.NUMBER_MIN,
                    record_attr="total_debit"),
    ],
    sort_options=[
        SortOption("voucher_date", "Voucher date (newest)"),
        SortOption("voucher_number", "Voucher number"),
        SortOption("total_debit", "Amount"),
    ],
    default_sort="voucher_date",
    page_size=VOUCHER_PAGE_SIZE,
)

RECEIPTS = ListSchema(
    entity_key="receipts",
    title="Receipts",
    filter_fields=[
        FilterField("voucher_number", "Voucher number", F.EXACT),
        FilterField("description", "Description", F.EXACT),
        FilterField("voucher_date", "Receipt date", F.DATE_RANGE),
        FilterField("store_account_id", "Store account", F.ENTITY_SELECT,
                    options_loader="store_accounts",
                    match=_match_voucher_debit_account),
        FilterField("customer_account_id", "Customer account", F.ENTITY_SELECT,
                    options_loader="customer_accounts",
                    match=_match_voucher_credit_account),
        FilterField("min_amount", "Min amount (₹)", F.NUMBER_MIN,
                    record_attr="total_debit"),
    ],
    sort_options=[
        SortOption("voucher_date", "Date (newest)"),
        SortOption("total_debit", "Amount"),
    ],
    default_sort="voucher_date",
    page_size=VOUCHER_PAGE_SIZE,
)

PAYMENTS = ListSchema(
    entity_key="payments",
    title="Vendor Payments",
    filter_fields=[
        FilterField("voucher_number", "Voucher number", F.EXACT),
        FilterField("description", "Description", F.EXACT),
        FilterField("voucher_date", "Payment date", F.DATE_RANGE),
        FilterField("vendor_id", "Vendor", F.ENTITY_SELECT,
                    options_loader="vendor_accounts",
                    match=_match_voucher_any_account),
        FilterField("service_name", "Service", F.ENTITY_SELECT,
                    options_loader="services_by_id",
                    match=_match_voucher_service),
        FilterField("min_amount", "Min amount (₹)", F.NUMBER_MIN,
                    record_attr="total_debit"),
    ],
    sort_options=[
        SortOption("voucher_date", "Date (newest)"),
        SortOption("total_debit", "Amount"),
    ],
    default_sort="voucher_date",
    page_size=VOUCHER_PAGE_SIZE,
)

ACCOUNTING_INVOICES = ListSchema(
    entity_key="accounting_invoices",
    title="Accounting Invoices",
    filter_fields=[
        FilterField("voucher_number", "Voucher number", F.EXACT),
        FilterField("description", "Description", F.EXACT),
        FilterField("voucher_date", "Invoice date", F.DATE_RANGE),
        FilterField("customer_account_id", "Customer account", F.ENTITY_SELECT,
                    options_loader="customer_accounts",
                    match=_match_voucher_debit_account),
        FilterField("min_amount", "Min amount (₹)", F.NUMBER_MIN,
                    record_attr="total_debit"),
    ],
    sort_options=[
        SortOption("voucher_date", "Date (newest)"),
        SortOption("total_debit", "Amount"),
    ],
    default_sort="voucher_date",
    page_size=VOUCHER_PAGE_SIZE,
)

def _match_sales_customer(row, value) -> bool:
    if isinstance(row, dict):
        return row.get("customer_account_id") == value
    return _match_voucher_debit_account(row, value)


STORE_SALES = ListSchema(
    entity_key="store_sales",
    title="Sales",
    filter_fields=[
        FilterField("store_invoice_number", "Store invoice number", F.EXACT),
        FilterField("party_name", "Customer", F.EXACT),
        FilterField("sale_date", "Sale date", F.DATE_RANGE),
        FilterField("customer_account_id", "Customer account", F.ENTITY_SELECT,
                    options_loader="customer_accounts",
                    match=_match_sales_customer),
        FilterField("min_gross", "Min gross (₹)", F.NUMBER_MIN,
                    record_attr="gross"),
    ],
    sort_options=[
        SortOption("sale_date", "Date (newest)"),
        SortOption("gross", "Gross amount"),
        SortOption("collected", "Collected"),
        SortOption("store_invoice_number", "Store invoice #"),
    ],
    default_sort="sale_date",
    page_size=VOUCHER_PAGE_SIZE,
)

JOURNAL = ListSchema(
    entity_key="journal",
    title="Journal Entries",
    filter_fields=[
        FilterField("voucher_number", "Voucher number", F.EXACT),
        FilterField("description", "Description", F.EXACT),
        FilterField("voucher_date", "Journal date", F.DATE_RANGE),
        FilterField("account_id", "Account", F.ENTITY_SELECT,
                    options_loader="accounts", match=_match_voucher_any_account),
        FilterField("min_amount", "Min amount (₹)", F.NUMBER_MIN,
                    record_attr="total_debit"),
    ],
    sort_options=[
        SortOption("voucher_date", "Date (newest)"),
        SortOption("voucher_number", "Voucher number"),
    ],
    default_sort="voucher_date",
    page_size=VOUCHER_PAGE_SIZE,
)

TRIAL_BALANCE = ListSchema(
    entity_key="trial_balance",
    title="Trial Balance",
    filter_fields=[
        FilterField("account_name", "Account name", F.EXACT),
        FilterField("types", "Account type", F.MULTISELECT,
                    record_attr="account_type", options=_enum_opts(AccountType)),
    ],
    sort_options=[
        SortOption("account_name", "Account name"),
        SortOption("balance", "Balance"),
    ],
    default_sort="account_name",
    default_desc=False,
    page_size=TRIAL_BALANCE_PAGE_SIZE,
)

ACTIVITIES = ListSchema(
    entity_key="activities",
    title="Activity Configuration",
    filter_fields=[
        FilterField("activity_name", "Activity name", F.EXACT),
        FilterField("categories", "Category", F.MULTISELECT,
                    record_attr="activity_category",
                    options=_enum_opts(ActivityCategory)),
        FilterField("types", "Type", F.MULTISELECT,
                    record_attr="activity_type", options=_enum_opts(ActivityType)),
        FilterField("active_only", "Active only", F.CHECKBOX,
                    match=_match_activity_active),
        FilterField("time_tracking", "Requires time tracking", F.SELECT,
                    options=[("yes", "Yes"), ("no", "No")],
                    match=_match_activity_time_tracking),
    ],
    sort_options=[
        SortOption("created_at", "Created (newest)"),
        SortOption("activity_name", "Activity name"),
        SortOption("activity_category", "Category"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

SERVICES = ListSchema(
    entity_key="services",
    title="Service Configuration",
    filter_fields=[
        FilterField("service_name", "Service name", F.EXACT),
        FilterField("expense_account_id", "Expense account", F.ENTITY_SELECT,
                    options_loader="expense_accounts"),
        FilterField("active_only", "Active only", F.CHECKBOX,
                    match=_match_service_active),
    ],
    sort_options=[
        SortOption("created_at", "Created (newest)"),
        SortOption("service_name", "Service name"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)


SCHEMAS = {
    s.entity_key: s
    for s in [
        ORDERS, ITEMS, MEASUREMENTS, CUSTOMERS, VENDORS, TIME, ACCOUNTS, VOUCHERS, RECEIPTS,
        PAYMENTS, ACCOUNTING_INVOICES, STORE_SALES, JOURNAL, TRIAL_BALANCE, ACTIVITIES,
        SERVICES, INVENTORY_CATEGORIES, INVENTORY_PRODUCTS, INVENTORY_STOCK,
        INVENTORY_STOCK_LEDGER,
    ]
}
