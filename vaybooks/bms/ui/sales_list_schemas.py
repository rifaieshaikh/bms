"""List schemas for Sales module pages."""

from vaybooks.bms.domain.shared.enums import SalesReturnStatus
from vaybooks.bms.ui.list_schemas import (
    F,
    FilterField,
    ListSchema,
    SortOption,
    VOUCHER_PAGE_SIZE,
)


def _match_customer(record, selected):
    if not selected:
        return True
    return record.get("customer_id") == selected


def _match_sales_customer(row, value):
    if isinstance(row, dict):
        return row.get("customer_account_id") == value
    return False


ESTIMATES = ListSchema(
    entity_key="estimates",
    title="Estimates",
    filter_fields=[
        FilterField("estimate_number", "Estimate number", F.EXACT),
        FilterField("customer_name", "Customer", F.EXACT),
        FilterField("estimate_date", "Estimate date", F.DATE_RANGE),
        FilterField("status", "Status", F.EXACT),
        FilterField(
            "customer_id",
            "Customer",
            F.ENTITY_SELECT,
            options_loader="customers",
            match=_match_customer,
        ),
    ],
    sort_options=[
        SortOption("estimate_date", "Date (newest)"),
        SortOption("estimate_number", "Estimate number"),
        SortOption("status", "Status"),
    ],
    default_sort="estimate_date",
    page_size=VOUCHER_PAGE_SIZE,
)

QUOTATIONS = ListSchema(
    entity_key="quotations",
    title="Quotations",
    filter_fields=[
        FilterField("quotation_number", "Quotation number", F.EXACT),
        FilterField("customer_name", "Customer", F.EXACT),
        FilterField("quotation_date", "Quotation date", F.DATE_RANGE),
        FilterField("status", "Status", F.EXACT),
        FilterField(
            "customer_id",
            "Customer",
            F.ENTITY_SELECT,
            options_loader="customers",
            match=_match_customer,
        ),
    ],
    sort_options=[
        SortOption("quotation_date", "Date (newest)"),
        SortOption("quotation_number", "Quotation number"),
        SortOption("status", "Status"),
    ],
    default_sort="quotation_date",
    page_size=VOUCHER_PAGE_SIZE,
)

SALES_ORDERS = ListSchema(
    entity_key="sales_orders",
    title="Sales Orders",
    filter_fields=[
        FilterField("so_number", "SO number", F.EXACT),
        FilterField("customer_name", "Customer", F.EXACT),
        FilterField("order_date", "Order date", F.DATE_RANGE),
        FilterField("status", "Status", F.EXACT),
        FilterField("customer_id", "Customer", F.ENTITY_SELECT,
                    options_loader="customers", match=_match_customer),
    ],
    sort_options=[
        SortOption("order_date", "Date (newest)"),
        SortOption("so_number", "SO number"),
        SortOption("status", "Status"),
    ],
    default_sort="order_date",
    page_size=VOUCHER_PAGE_SIZE,
)

DELIVERY_NOTES = ListSchema(
    entity_key="delivery_notes",
    title="Delivery Notes",
    filter_fields=[
        FilterField("dn_number", "DN number", F.EXACT),
        FilterField("so_number", "SO number", F.EXACT),
        FilterField("customer_name", "Customer", F.EXACT),
        FilterField("delivery_date", "Delivery date", F.DATE_RANGE),
        FilterField("status", "Status", F.EXACT),
    ],
    sort_options=[
        SortOption("delivery_date", "Date (newest)"),
        SortOption("dn_number", "DN number"),
    ],
    default_sort="delivery_date",
    page_size=VOUCHER_PAGE_SIZE,
)

STORE_SALES = ListSchema(
    entity_key="store_sales",
    title="Sales Invoices",
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

SALES_RETURNS = ListSchema(
    entity_key="sales_returns",
    title="Sales Returns",
    filter_fields=[
        FilterField("return_number", "Return number", F.EXACT),
        FilterField("customer_name", "Customer", F.EXACT),
        FilterField("return_date", "Return date", F.DATE_RANGE),
        FilterField(
            "statuses",
            "Status",
            F.MULTISELECT,
            record_attr="status",
            options=[
                (status.value, status.value)
                for status in SalesReturnStatus
            ],
        ),
    ],
    sort_options=[
        SortOption("return_date", "Date (newest)"),
        SortOption("return_number", "Return number"),
        SortOption("status", "Status"),
    ],
    default_sort="return_date",
    page_size=VOUCHER_PAGE_SIZE,
)
