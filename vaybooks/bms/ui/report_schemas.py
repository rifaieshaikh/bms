"""Filter + sort schemas for the Reports page (popover bar, same as list routes)."""

from __future__ import annotations

from datetime import date, timedelta

from vaybooks.bms.domain.shared.enums import (
    ExpenseSource,
    OrderStatus,
    PurchaseOrderStatus,
    SalesOrderStatus,
    StockMovementType,
)
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui.pagination import REPORT_PAGE_SIZE


def _today() -> date:
    return date.today()


def _mtd() -> tuple[date, date]:
    today = date.today()
    return today.replace(day=1), today


def _last_30_days() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=29), today


def _etd_default() -> tuple[date, date]:
    today = date.today()
    return today, today + timedelta(days=30)


def _enum_opts(enum_cls) -> list[tuple]:
    return [(e.value, e.value) for e in enum_cls]


ITEM_PROFITABILITY = ListSchema(
    entity_key="report_item_profitability",
    title="Item Profitability (MPH)",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            help="Delivered / snapshotted items in this range.",
        ),
        FilterField(
            "customer_query",
            "Customer",
            F.EXACT,
            placeholder="Name contains…",
        ),
        FilterField(
            "bill_query",
            "Bill / order",
            F.EXACT,
            placeholder="Bill or order contains…",
        ),
        FilterField("min_mph", "Min MPH (₹/h)", F.NUMBER_MIN),
        FilterField("min_margin", "Min margin (₹)", F.NUMBER_MIN),
    ],
    sort_options=[
        SortOption("margin_per_hour", "MPH"),
        SortOption("margin_amount", "Margin"),
        SortOption("delivered_on", "Delivered date"),
        SortOption("bill_number", "Measurement bill number"),
        SortOption("customer_name", "Customer"),
    ],
    default_sort="margin_per_hour",
    page_size=REPORT_PAGE_SIZE,
)

ORDER_MPH = ListSchema(
    entity_key="report_order_mph",
    title="Margin Per Hour (MPH)",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            help="Items delivered in this range; order MPH is aggregated across bills.",
        ),
        FilterField(
            "customer_query",
            "Customer",
            F.EXACT,
            placeholder="Name contains…",
        ),
        FilterField("min_mph", "Min order MPH (₹/h)", F.NUMBER_MIN),
    ],
    sort_options=[
        SortOption("margin_per_hour", "Order MPH"),
        SortOption("total_margin", "Total margin"),
        SortOption("total_hours", "Total hours"),
        SortOption("delivered_through", "Latest delivery"),
        SortOption("order_number", "Order number"),
        SortOption("customer_name", "Customer"),
    ],
    default_sort="margin_per_hour",
    page_size=REPORT_PAGE_SIZE,
)

ACTIVITY_PENDING = ListSchema(
    entity_key="report_activity_pending",
    title="Activity Pending",
    filter_fields=[
        FilterField(
            "etd_range",
            "ETD range",
            F.DATE_RANGE,
            default=_etd_default,
            record_attr="expected_delivery_date",
        ),
        FilterField(
            "overdue_only",
            "Overdue only (ETD before today)",
            F.CHECKBOX,
        ),
        FilterField(
            "statuses",
            "Activity status",
            F.MULTISELECT,
            options=[("Pending", "Pending"), ("In Progress", "In Progress")],
            default=lambda: ["Pending", "In Progress"],
        ),
        FilterField(
            "activity_names",
            "Activity",
            F.MULTISELECT,
            options_loader="activity_names",
        ),
        FilterField(
            "customer_query",
            "Customer / order",
            F.EXACT,
            placeholder="Search contains…",
        ),
    ],
    sort_options=[
        SortOption("expected_delivery_date", "ETD"),
        SortOption("order_number", "Order number"),
        SortOption("customer_name", "Customer"),
        SortOption("activity_name", "Activity"),
        SortOption("activity_status", "Status"),
    ],
    default_sort="expected_delivery_date",
    default_desc=False,
    page_size=REPORT_PAGE_SIZE,
)

TIME_TRACKING = ListSchema(
    entity_key="report_time_tracking",
    title="Time Tracking",
    filter_fields=[
        FilterField(
            "date_range",
            "Work date",
            F.DATE_RANGE,
            default=_mtd,
        ),
        FilterField(
            "worker",
            "Employee",
            F.EXACT,
            placeholder="Name contains…",
        ),
        FilterField(
            "activity_name",
            "Activity",
            F.EXACT,
            placeholder="Exact activity name",
        ),
        FilterField(
            "search",
            "Order / bill",
            F.EXACT,
            placeholder="Contains…",
        ),
    ],
    sort_options=[
        SortOption("work_date", "Work date"),
        SortOption("duration_minutes", "Duration"),
        SortOption("worker_name", "Employee"),
        SortOption("activity_name", "Activity"),
        SortOption("order_number", "Order number"),
    ],
    default_sort="work_date",
    page_size=REPORT_PAGE_SIZE,
)

EXPENSE_DETAIL = ListSchema(
    entity_key="report_expense_detail",
    title="Expense Detail",
    filter_fields=[
        FilterField(
            "date_range",
            "Expense date",
            F.DATE_RANGE,
            default=_mtd,
        ),
        FilterField(
            "expense_source",
            "Expense source",
            F.SELECT,
            options=_enum_opts(ExpenseSource),
        ),
        FilterField(
            "search",
            "Order / bill / name",
            F.EXACT,
            placeholder="Contains…",
        ),
        FilterField("min_amount", "Min amount (₹)", F.NUMBER_MIN),
    ],
    sort_options=[
        SortOption("expense_date", "Expense date"),
        SortOption("total_purchase_price", "Amount"),
        SortOption("expense_name", "Expense name"),
        SortOption("order_number", "Order number"),
    ],
    default_sort="expense_date",
    page_size=REPORT_PAGE_SIZE,
)

CUSTOMER_HISTORY = ListSchema(
    entity_key="report_customer_history",
    title="Customer Order History",
    filter_fields=[
        FilterField(
            "date_range",
            "Order date",
            F.DATE_RANGE,
            default=_mtd,
        ),
        FilterField(
            "statuses",
            "Order status",
            F.MULTISELECT,
            options=_enum_opts(OrderStatus),
        ),
    ],
    sort_options=[
        SortOption("order_date", "Order date"),
        SortOption("expected_delivery_date", "ETD"),
        SortOption("order_number", "Order number"),
        SortOption("advance_amount", "Advance"),
        SortOption("order_status", "Status"),
    ],
    default_sort="order_date",
    page_size=REPORT_PAGE_SIZE,
)

OVERDUE = ListSchema(
    entity_key="report_overdue",
    title="Overdue Orders",
    filter_fields=[
        FilterField(
            "as_of_date",
            "As-of date",
            F.DATE,
            default=_today,
        ),
        FilterField("min_days_overdue", "Min days overdue", F.NUMBER_MIN),
        FilterField(
            "statuses",
            "Order status",
            F.MULTISELECT,
            options=[
                (OrderStatus.IN_PROGRESS.value, OrderStatus.IN_PROGRESS.value),
                (
                    OrderStatus.READY_FOR_DELIVERY.value,
                    OrderStatus.READY_FOR_DELIVERY.value,
                ),
                (
                    OrderStatus.INVOICE_GENERATED.value,
                    OrderStatus.INVOICE_GENERATED.value,
                ),
            ],
        ),
        FilterField(
            "customer_query",
            "Customer / phone",
            F.EXACT,
            placeholder="Contains…",
        ),
    ],
    sort_options=[
        SortOption("days_overdue", "Days overdue"),
        SortOption("expected_delivery_date", "ETD"),
        SortOption("order_number", "Order number"),
        SortOption("customer_name", "Customer"),
    ],
    default_sort="days_overdue",
    page_size=REPORT_PAGE_SIZE,
)

COMPLETED = ListSchema(
    entity_key="report_completed",
    title="Completed Orders",
    filter_fields=[
        FilterField(
            "date_range",
            "Delivery date",
            F.DATE_RANGE,
            default=_mtd,
        ),
        FilterField(
            "statuses",
            "Status",
            F.MULTISELECT,
            options=[
                (OrderStatus.COMPLETED.value, OrderStatus.COMPLETED.value),
                (OrderStatus.DELIVERED.value, OrderStatus.DELIVERED.value),
            ],
            default=lambda: [
                OrderStatus.COMPLETED.value,
                OrderStatus.DELIVERED.value,
            ],
        ),
        FilterField(
            "customer_query",
            "Customer",
            F.EXACT,
            placeholder="Name contains…",
        ),
    ],
    sort_options=[
        SortOption("delivery_date", "Delivery date"),
        SortOption("order_date", "Order date"),
        SortOption("order_number", "Order number"),
        SortOption("customer_name", "Customer"),
    ],
    default_sort="delivery_date",
    page_size=REPORT_PAGE_SIZE,
)

PERIOD_FINANCIAL_SUMMARY = ListSchema(
    entity_key="report_period_financial",
    title="Period Financial Summary",
    filter_fields=[
        FilterField("date_range", "Period", F.DATE_RANGE, default=_mtd),
    ],
    sort_options=[SortOption("metric", "Metric")],
    default_sort="metric",
    default_desc=False,
    page_size=REPORT_PAGE_SIZE,
)

TOP_CUSTOMERS_REVENUE = ListSchema(
    entity_key="report_top_customers_revenue",
    title="Top Customers by Revenue",
    filter_fields=[
        FilterField("date_range", "Period", F.DATE_RANGE, default=_mtd),
        FilterField("min_revenue", "Min revenue (₹)", F.NUMBER_MIN),
    ],
    sort_options=[
        SortOption("total_revenue", "Revenue"),
        SortOption("total_margin", "Margin"),
        SortOption("order_count", "Orders"),
        SortOption("customer_name", "Customer"),
    ],
    default_sort="total_revenue",
    page_size=REPORT_PAGE_SIZE,
)

TOP_CUSTOMERS_MARGIN = ListSchema(
    entity_key="report_top_customers_margin",
    title="Top Customers by Margin",
    filter_fields=[
        FilterField("date_range", "Period", F.DATE_RANGE, default=_mtd),
        FilterField("min_margin", "Min margin (₹)", F.NUMBER_MIN),
    ],
    sort_options=[
        SortOption("total_margin", "Margin"),
        SortOption("avg_mph", "Avg MPH"),
        SortOption("total_revenue", "Revenue"),
        SortOption("customer_name", "Customer"),
    ],
    default_sort="total_margin",
    page_size=REPORT_PAGE_SIZE,
)

CUSTOMER_OUTSTANDING = ListSchema(
    entity_key="report_customer_outstanding",
    title="Customer Outstanding",
    filter_fields=[
        FilterField("min_balance", "Min balance due (₹)", F.NUMBER_MIN),
        FilterField("search", "Customer", F.EXACT, placeholder="Name contains…"),
    ],
    sort_options=[
        SortOption("balance_due", "Balance due"),
        SortOption("customer_name", "Customer"),
    ],
    default_sort="balance_due",
    page_size=REPORT_PAGE_SIZE,
)

VENDOR_PAYABLES = ListSchema(
    entity_key="report_vendor_payables",
    title="Vendor Payables",
    filter_fields=[
        FilterField("min_balance", "Min payable (₹)", F.NUMBER_MIN),
        FilterField("search", "Vendor", F.EXACT, placeholder="Name contains…"),
    ],
    sort_options=[
        SortOption("payable", "Payable"),
        SortOption("vendor_name", "Vendor"),
    ],
    default_sort="payable",
    page_size=REPORT_PAGE_SIZE,
)

CASH_MOVEMENT = ListSchema(
    entity_key="report_cash_movement",
    title="Cash Movement",
    filter_fields=[
        FilterField("date_range", "Period", F.DATE_RANGE, default=_mtd),
    ],
    sort_options=[
        SortOption("amount", "Amount"),
        SortOption("flow_type", "Flow type"),
    ],
    default_sort="amount",
    page_size=REPORT_PAGE_SIZE,
)

EXPENSE_BY_SOURCE = ListSchema(
    entity_key="report_expense_by_source",
    title="Expense by Source",
    filter_fields=[
        FilterField("date_range", "Period", F.DATE_RANGE, default=_mtd),
    ],
    sort_options=[
        SortOption("total_amount", "Total amount"),
        SortOption("line_count", "Line count"),
        SortOption("expense_source", "Source"),
    ],
    default_sort="total_amount",
    page_size=REPORT_PAGE_SIZE,
)

CUSTOMER_SEGMENTS = ListSchema(
    entity_key="report_customer_segments",
    title="Customer Segments",
    filter_fields=[
        FilterField("date_range", "Period", F.DATE_RANGE, default=_mtd),
    ],
    sort_options=[
        SortOption("customer_count", "Customer count"),
        SortOption("segment", "Segment"),
    ],
    default_sort="customer_count",
    page_size=REPORT_PAGE_SIZE,
)

ORDER_PIPELINE = ListSchema(
    entity_key="report_order_pipeline",
    title="Order Pipeline",
    filter_fields=[
        FilterField(
            "statuses",
            "Order status",
            F.MULTISELECT,
            options=_enum_opts(OrderStatus),
        ),
    ],
    sort_options=[
        SortOption("order_count", "Order count"),
        SortOption("order_status", "Status"),
    ],
    default_sort="order_count",
    page_size=REPORT_PAGE_SIZE,
)

BILLS_PENDING = ListSchema(
    entity_key="report_bills_pending",
    title="Bills Pending Invoice",
    filter_fields=[
        FilterField(
            "customer_query",
            "Customer / order",
            F.EXACT,
            placeholder="Contains…",
        ),
    ],
    sort_options=[
        SortOption("order_number", "Order number"),
        SortOption("customer_name", "Customer"),
        SortOption("bill_number", "Measurement bill number"),
    ],
    default_sort="order_number",
    page_size=REPORT_PAGE_SIZE,
)

ACTIVITY_BOTTLENECK = ListSchema(
    entity_key="report_activity_bottleneck",
    title="Activity Bottleneck",
    filter_fields=ACTIVITY_PENDING.filter_fields,
    sort_options=[
        SortOption("pending_count", "Pending count"),
        SortOption("overdue_count", "Overdue count"),
        SortOption("activity_name", "Activity"),
    ],
    default_sort="pending_count",
    page_size=REPORT_PAGE_SIZE,
)

DELIVERY_PERFORMANCE = ListSchema(
    entity_key="report_delivery_performance",
    title="Delivery Performance",
    filter_fields=[
        FilterField("date_range", "Delivery date", F.DATE_RANGE, default=_mtd),
        FilterField(
            "customer_query",
            "Customer",
            F.EXACT,
            placeholder="Name contains…",
        ),
        FilterField("on_time_only", "On-time only", F.CHECKBOX),
        FilterField("late_only", "Late only", F.CHECKBOX),
    ],
    sort_options=[
        SortOption("days_variance", "Days variance"),
        SortOption("delivery_date", "Delivery date"),
        SortOption("order_number", "Order number"),
    ],
    default_sort="days_variance",
    page_size=REPORT_PAGE_SIZE,
)

WORKER_PRODUCTIVITY = ListSchema(
    entity_key="report_worker_productivity",
    title="Employee Productivity",
    filter_fields=[
        FilterField("date_range", "Work date", F.DATE_RANGE, default=_mtd),
        FilterField("worker", "Employee", F.EXACT, placeholder="Name contains…"),
        FilterField("min_hours", "Min hours", F.NUMBER_MIN),
    ],
    sort_options=[
        SortOption("total_hours", "Total hours"),
        SortOption("entry_count", "Entries"),
        SortOption("order_count", "Orders"),
        SortOption("worker_name", "Employee"),
    ],
    default_sort="total_hours",
    page_size=REPORT_PAGE_SIZE,
)

LABOR_VS_MPH = ListSchema(
    entity_key="report_labor_vs_mph",
    title="Labor vs MPH",
    filter_fields=[
        FilterField("date_range", "Period", F.DATE_RANGE, default=_mtd),
        FilterField("min_hours", "Min logged hours", F.NUMBER_MIN),
    ],
    sort_options=[
        SortOption("mph", "MPH"),
        SortOption("logged_hours", "Logged hours"),
        SortOption("margin", "Margin"),
        SortOption("order_number", "Order number"),
    ],
    default_sort="mph",
    page_size=REPORT_PAGE_SIZE,
)

STOCK_ON_HAND = ListSchema(
    entity_key="report_stock_on_hand",
    title="Stock on Hand",
    filter_fields=[
        FilterField(
            "category_id",
            "Category",
            F.ENTITY_SELECT,
            options_loader="inventory_categories",
        ),
        FilterField("search", "Product / SKU", F.EXACT, placeholder="Contains…"),
        FilterField("min_qty", "Min qty", F.NUMBER_MIN, record_attr="qty"),
        FilterField(
            "active_only",
            "Active only",
            F.CHECKBOX,
            default_active=True,
        ),
    ],
    sort_options=[
        SortOption("qty", "Stock qty"),
        SortOption("stock_value", "Stock value"),
        SortOption("product_name", "Product name"),
        SortOption("sku", "SKU"),
        SortOption("category", "Category"),
    ],
    default_sort="qty",
    page_size=REPORT_PAGE_SIZE,
)

LOW_STOCK = ListSchema(
    entity_key="report_low_stock",
    title="Low Stock Alert",
    filter_fields=[
        FilterField(
            "category_id",
            "Category",
            F.ENTITY_SELECT,
            options_loader="inventory_categories",
        ),
        FilterField("threshold", "Low-stock threshold", F.NUMBER_MIN),
        FilterField(
            "include_out_of_stock",
            "Include out of stock",
            F.CHECKBOX,
            default_active=True,
        ),
    ],
    sort_options=[
        SortOption("qty", "Stock qty"),
        SortOption("product_name", "Product name"),
        SortOption("sku", "SKU"),
        SortOption("category", "Category"),
    ],
    default_sort="qty",
    page_size=REPORT_PAGE_SIZE,
)

STOCK_MOVEMENTS = ListSchema(
    entity_key="report_stock_movements",
    title="Stock Movements",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
        ),
        FilterField(
            "product_id",
            "Product",
            F.ENTITY_SELECT,
            options_loader="inventory_products",
        ),
        FilterField(
            "category_id",
            "Category",
            F.ENTITY_SELECT,
            options_loader="inventory_categories",
        ),
        FilterField(
            "movement_type",
            "Movement type",
            F.SELECT,
            options=_enum_opts(StockMovementType),
        ),
    ],
    sort_options=[
        SortOption("movement_date", "Date"),
        SortOption("product_name", "Product name"),
        SortOption("movement_type", "Movement type"),
        SortOption("qty_out", "Qty out"),
        SortOption("qty_in", "Qty in"),
    ],
    default_sort="movement_date",
    page_size=REPORT_PAGE_SIZE,
)

PO_PIPELINE = ListSchema(
    entity_key="report_po_pipeline",
    title="Purchase Orders Pipeline",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            record_attr="order_date",
            help="Filter by purchase order date.",
        ),
        FilterField(
            "status",
            "Status",
            F.SELECT,
            options=_enum_opts(PurchaseOrderStatus),
        ),
        FilterField(
            "vendor_name",
            "Vendor",
            F.REGEX,
            placeholder="Name contains…",
        ),
        FilterField("overdue", "Overdue only", F.CHECKBOX),
    ],
    sort_options=[
        SortOption("order_date", "Order date"),
        SortOption("po_number", "PO number"),
        SortOption("status", "Status"),
        SortOption("total_amount", "Amount"),
        SortOption("vendor_name", "Vendor"),
    ],
    default_sort="order_date",
    page_size=REPORT_PAGE_SIZE,
)

GRN_PENDING = ListSchema(
    entity_key="report_grn_pending",
    title="GRN Pending",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            record_attr="order_date",
            help="Filter by linked PO order date.",
        ),
        FilterField(
            "vendor_name",
            "Vendor",
            F.REGEX,
            placeholder="Name contains…",
        ),
        FilterField(
            "product_name",
            "Product",
            F.REGEX,
            placeholder="Name contains…",
        ),
        FilterField("qty_pending", "Min pending qty", F.NUMBER_MIN),
    ],
    sort_options=[
        SortOption("po_number", "PO number"),
        SortOption("qty_pending", "Qty pending"),
        SortOption("vendor_name", "Vendor"),
        SortOption("product_name", "Product"),
        SortOption("order_date", "PO order date"),
    ],
    default_sort="qty_pending",
    page_size=REPORT_PAGE_SIZE,
)

PURCHASES_BY_VENDOR = ListSchema(
    entity_key="report_purchases_by_vendor",
    title="Purchases by Vendor",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            help="Filter by purchase bill date.",
        ),
        FilterField(
            "vendor_name",
            "Vendor",
            F.REGEX,
            placeholder="Name contains…",
        ),
    ],
    sort_options=[
        SortOption("total", "Total amount"),
        SortOption("vendor_name", "Vendor"),
        SortOption("bill_count", "Bill count"),
    ],
    default_sort="total",
    page_size=REPORT_PAGE_SIZE,
)

PURCHASE_RETURNS_SUMMARY = ListSchema(
    entity_key="report_purchase_returns",
    title="Purchase Returns Summary",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            record_attr="return_date",
            help="Filter by return date.",
        ),
        FilterField(
            "vendor_name",
            "Vendor",
            F.REGEX,
            placeholder="Name contains…",
        ),
    ],
    sort_options=[
        SortOption("return_date", "Return date"),
        SortOption("total_amount", "Amount"),
        SortOption("vendor_name", "Vendor"),
    ],
    default_sort="return_date",
    page_size=REPORT_PAGE_SIZE,
)

SO_PIPELINE = ListSchema(
    entity_key="report_so_pipeline",
    title="Sales Orders Pipeline",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            record_attr="order_date",
            help="Filter by sales order date.",
        ),
        FilterField(
            "status",
            "Status",
            F.SELECT,
            options=_enum_opts(SalesOrderStatus),
        ),
        FilterField(
            "customer_name",
            "Customer",
            F.REGEX,
            placeholder="Name contains…",
        ),
        FilterField("overdue", "Overdue only", F.CHECKBOX),
    ],
    sort_options=[
        SortOption("order_date", "Order date"),
        SortOption("so_number", "SO number"),
        SortOption("status", "Status"),
        SortOption("total_amount", "Amount"),
        SortOption("customer_name", "Customer"),
    ],
    default_sort="order_date",
    page_size=REPORT_PAGE_SIZE,
)

DN_PENDING = ListSchema(
    entity_key="report_dn_pending",
    title="Delivery Pending",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            record_attr="order_date",
            help="Filter by linked SO order date.",
        ),
        FilterField(
            "customer_name",
            "Customer",
            F.REGEX,
            placeholder="Name contains…",
        ),
        FilterField(
            "product_name",
            "Product",
            F.REGEX,
            placeholder="Name contains…",
        ),
        FilterField("qty_pending", "Min pending qty", F.NUMBER_MIN),
    ],
    sort_options=[
        SortOption("so_number", "SO number"),
        SortOption("qty_pending", "Qty pending"),
        SortOption("customer_name", "Customer"),
        SortOption("product_name", "Product"),
        SortOption("order_date", "SO order date"),
    ],
    default_sort="qty_pending",
    page_size=REPORT_PAGE_SIZE,
)

SALES_BY_CUSTOMER = ListSchema(
    entity_key="report_sales_by_customer",
    title="Sales by Customer",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            help="Filter by sales invoice date.",
        ),
        FilterField(
            "customer_name",
            "Customer",
            F.REGEX,
            placeholder="Name contains…",
        ),
    ],
    sort_options=[
        SortOption("total", "Total amount"),
        SortOption("customer_name", "Customer"),
        SortOption("invoice_count", "Invoice count"),
    ],
    default_sort="total",
    page_size=REPORT_PAGE_SIZE,
)

SALES_RETURNS_SUMMARY = ListSchema(
    entity_key="report_sales_returns",
    title="Sales Returns Summary",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            record_attr="return_date",
            help="Filter by return date.",
        ),
        FilterField(
            "customer_name",
            "Customer",
            F.REGEX,
            placeholder="Name contains…",
        ),
    ],
    sort_options=[
        SortOption("return_date", "Return date"),
        SortOption("total_amount", "Amount"),
        SortOption("customer_name", "Customer"),
    ],
    default_sort="return_date",
    page_size=REPORT_PAGE_SIZE,
)

INVENTORY_VALUATION = ListSchema(
    entity_key="report_inventory_valuation",
    title="Inventory Valuation",
    filter_fields=[
        FilterField(
            "category_id",
            "Category",
            F.ENTITY_SELECT,
            options_loader="inventory_categories",
        ),
    ],
    sort_options=[
        SortOption("valuation", "Valuation"),
        SortOption("product_name", "Product"),
    ],
    default_sort="valuation",
    page_size=REPORT_PAGE_SIZE,
)

REPORT_CATEGORIES: dict[str, list[str]] = {
    "Business Insights": [
        "Period Financial Summary",
        "Top Customers by Revenue",
        "Top Customers by Margin",
        "Customer Outstanding",
        "Vendor Payables",
        "Cash Movement",
        "Expense by Source",
        "Customer Segments",
        "Expense Detail",
    ],
    "Profitability": [
        "Item Profitability (MPH)",
        "Margin Per Hour (MPH)",
    ],
    "Operations": [
        "Order Pipeline",
        "Bills Pending Invoice",
        "Activity Bottleneck",
        "Delivery Performance",
        "Activity Pending",
        "Overdue Orders",
        "Completed Orders",
    ],
    "Labor": [
        "Time Tracking",
        "Employee Productivity",
        "Labor vs MPH",
    ],
    "Customers": [
        "Customer Order History",
    ],
    "Inventory": [
        "Stock on Hand",
        "Low Stock Alert",
        "Stock Movements",
        "Inventory Valuation",
    ],
    "Purchases": [
        "Purchase Orders Pipeline",
        "GRN Pending",
        "Purchases by Vendor",
        "Purchase Returns Summary",
    ],
    "Sales Documents": [
        "Sales Orders Pipeline",
        "Delivery Pending",
        "Sales by Customer",
        "Sales Returns Summary",
    ],
}

SCHEMA_BY_REPORT_TYPE = {
    "Period Financial Summary": PERIOD_FINANCIAL_SUMMARY,
    "Top Customers by Revenue": TOP_CUSTOMERS_REVENUE,
    "Top Customers by Margin": TOP_CUSTOMERS_MARGIN,
    "Customer Outstanding": CUSTOMER_OUTSTANDING,
    "Vendor Payables": VENDOR_PAYABLES,
    "Cash Movement": CASH_MOVEMENT,
    "Expense by Source": EXPENSE_BY_SOURCE,
    "Customer Segments": CUSTOMER_SEGMENTS,
    "Expense Detail": EXPENSE_DETAIL,
    "Item Profitability (MPH)": ITEM_PROFITABILITY,
    "Margin Per Hour (MPH)": ORDER_MPH,
    "Order Pipeline": ORDER_PIPELINE,
    "Bills Pending Invoice": BILLS_PENDING,
    "Activity Bottleneck": ACTIVITY_BOTTLENECK,
    "Delivery Performance": DELIVERY_PERFORMANCE,
    "Activity Pending": ACTIVITY_PENDING,
    "Overdue Orders": OVERDUE,
    "Completed Orders": COMPLETED,
    "Time Tracking": TIME_TRACKING,
    "Employee Productivity": WORKER_PRODUCTIVITY,
    "Labor vs MPH": LABOR_VS_MPH,
    "Customer Order History": CUSTOMER_HISTORY,
    "Stock on Hand": STOCK_ON_HAND,
    "Low Stock Alert": LOW_STOCK,
    "Stock Movements": STOCK_MOVEMENTS,
    "Inventory Valuation": INVENTORY_VALUATION,
    "Purchase Orders Pipeline": PO_PIPELINE,
    "GRN Pending": GRN_PENDING,
    "Purchases by Vendor": PURCHASES_BY_VENDOR,
    "Purchase Returns Summary": PURCHASE_RETURNS_SUMMARY,
    "Sales Orders Pipeline": SO_PIPELINE,
    "Delivery Pending": DN_PENDING,
    "Sales by Customer": SALES_BY_CUSTOMER,
    "Sales Returns Summary": SALES_RETURNS_SUMMARY,
}

CATEGORY_BY_REPORT_TYPE = {
    report: category
    for category, reports in REPORT_CATEGORIES.items()
    for report in reports
}

CATEGORY_SERVICE_KEYS = {
    "Business Insights": "reports_business",
    "Profitability": "reports_profitability",
    "Operations": "reports_operations",
    "Labor": "reports_labor",
    "Customers": "reports_customers",
    "Inventory": "reports_inventory",
    "Purchases": "reports_purchases",
    "Sales Documents": "reports_sales_module",
}

REPORT_TYPES = [
    report
    for reports in REPORT_CATEGORIES.values()
    for report in reports
]

SUMMARY_REPORT_TYPES = frozenset(
    {
        "Item Profitability (MPH)",
        "Margin Per Hour (MPH)",
    }
)

SPECIAL_REPORT_TYPES = frozenset(
    {"Customer Order History", "Period Financial Summary"}
)
