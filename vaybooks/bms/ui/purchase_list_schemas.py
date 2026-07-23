"""List schemas for Purchases module pages."""

from vaybooks.bms.ui.list_schemas import (
    F,
    FilterField,
    ListSchema,
    SortOption,
    VOUCHER_PAGE_SIZE,
)
from datetime import date


def _mtd() -> tuple[date, date]:
    today = date.today()
    return today.replace(day=1), today


def _match_vendor(record, selected):
  if not selected:
    return True
  return record.get("vendor_id") == selected or record.get("vendor_account_id") == selected


PURCHASES_OVERVIEW = ListSchema(
    entity_key="purchases_overview",
    title="Purchases Overview",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            help="Applies to spend KPIs and date-scoped charts.",
        ),
    ],
    sort_options=[
        SortOption("date_range", "Period"),
    ],
    default_sort="date_range",
    page_size=12,
)


PURCHASE_ORDERS = ListSchema(
    entity_key="purchase_orders",
    title="Purchase Orders",
    filter_fields=[
        FilterField("po_number", "PO number", F.EXACT),
        FilterField("vendor_name", "Vendor", F.EXACT),
        FilterField("order_date", "Order date", F.DATE_RANGE),
        FilterField("status", "Status", F.EXACT),
        FilterField("vendor_id", "Vendor", F.ENTITY_SELECT,
                    options_loader="vendors", match=_match_vendor),
    ],
    sort_options=[
        SortOption("order_date", "Date"),
        SortOption("po_number", "PO number"),
        SortOption("status", "Status"),
    ],
    default_sort="order_date",
    page_size=VOUCHER_PAGE_SIZE,
)

GOODS_RECEIPTS = ListSchema(
    entity_key="goods_receipts",
    title="Goods Receipt",
    filter_fields=[
        FilterField("grn_number", "GRN number", F.EXACT),
        FilterField("po_number", "PO number", F.EXACT),
        FilterField("vendor_name", "Vendor", F.EXACT),
        FilterField("receipt_date", "Receipt date", F.DATE_RANGE),
        FilterField("status", "Status", F.EXACT),
        FilterField("vendor_id", "Vendor", F.ENTITY_SELECT,
                    options_loader="vendors", match=_match_vendor),
    ],
    sort_options=[
        SortOption("receipt_date", "Date"),
        SortOption("grn_number", "GRN number"),
    ],
    default_sort="receipt_date",
    page_size=VOUCHER_PAGE_SIZE,
)

STORE_PURCHASES = ListSchema(
    entity_key="store_purchases",
    title="Purchase Bills",
    filter_fields=[
        FilterField("vendor_bill_number", "Bill number", F.EXACT),
        FilterField("vendor_name", "Vendor", F.EXACT),
        FilterField("bill_date", "Bill date", F.DATE_RANGE),
        FilterField("vendor_id", "Vendor", F.ENTITY_SELECT,
                    options_loader="vendors", match=_match_vendor),
        FilterField("vendor_account_id", "Vendor account", F.ENTITY_SELECT,
                    options_loader="vendor_accounts", match=_match_vendor),
        FilterField("min_total", "Min total (₹)", F.NUMBER_MIN, record_attr="total"),
    ],
    sort_options=[
        SortOption("bill_date", "Date"),
        SortOption("total", "Total amount"),
        SortOption("vendor_bill_number", "Bill number"),
    ],
    default_sort="bill_date",
    page_size=VOUCHER_PAGE_SIZE,
)

PURCHASE_RETURNS = ListSchema(
    entity_key="purchase_returns",
    title="Purchase Returns",
    filter_fields=[
        FilterField("return_number", "Return number", F.EXACT),
        FilterField("vendor_name", "Vendor", F.EXACT),
        FilterField("return_date", "Return date", F.DATE_RANGE),
        FilterField("vendor_id", "Vendor", F.ENTITY_SELECT,
                    options_loader="vendors", match=_match_vendor),
    ],
    sort_options=[
        SortOption("return_date", "Date"),
        SortOption("return_number", "Return number"),
    ],
    default_sort="return_date",
    page_size=VOUCHER_PAGE_SIZE,
)
