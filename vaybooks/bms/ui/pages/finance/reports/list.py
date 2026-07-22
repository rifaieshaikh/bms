from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.components.filter_sort_bar import render_filter_sort_bar
from vaybooks.bms.ui.components.report_filters import (
    build_report_filter,
    report_filter_token,
)
from vaybooks.bms.ui.pagination import REPORT_PAGE_SIZE, paginate_list, render_page_controls
from vaybooks.bms.ui.report_schemas import (
    CUSTOMER_HISTORY,
    REPORT_CATEGORIES,
    SCHEMA_BY_REPORT_TYPE,
    SUMMARY_REPORT_TYPES,
)
from vaybooks.bms.ui.styles import metric_grid

AGGREGATED_PERIOD_LABEL = "Aggregated Totals for period"

# (service_key, method_name)
REPORT_LOADERS: dict[str, tuple[str, str]] = {
    "Period Financial Summary": ("reports_business", "period_financial_summary"),
    "Top Customers by Revenue": ("reports_business", "top_customers_by_revenue"),
    "Top Customers by Margin": ("reports_business", "top_customers_by_margin"),
    "Customer Outstanding": ("reports_business", "customer_outstanding_report"),
    "Vendor Payables": ("reports_business", "vendor_payables_report"),
    "Cash Movement": ("reports_business", "cash_movement_report"),
    "Expense by Source": ("reports_business", "expense_by_source_report"),
    "Customer Segments": ("reports_business", "customer_segments_report"),
    "Expense Detail": ("reports_business", "expense_detail_report"),
    "Item Profitability (MPH)": ("reports_profitability", "item_profitability_report"),
    "Margin Per Hour (MPH)": ("reports_profitability", "mph_report"),
    "Order Pipeline": ("reports_operations", "order_pipeline_report"),
    "Bills Pending Invoice": ("reports_operations", "bills_pending_invoice_report"),
    "Activity Bottleneck": ("reports_operations", "activity_bottleneck_report"),
    "Delivery Performance": ("reports_operations", "delivery_performance_report"),
    "Activity Pending": ("reports_operations", "activity_pending_report"),
    "Overdue Orders": ("reports_operations", "overdue_order_report"),
    "Completed Orders": ("reports_operations", "completed_order_report"),
    "Time Tracking": ("reports_labor", "time_tracking_report"),
    "Employee Productivity": ("reports_labor", "worker_productivity_report"),
    "Labor vs MPH": ("reports_labor", "labor_vs_mph_report"),
    "Customer Order History": ("reports_customers", "customer_order_history"),
    "Stock on Hand": ("reports_inventory", "stock_on_hand_report"),
    "Low Stock Alert": ("reports_inventory", "low_stock_report"),
    "Stock Movements": ("reports_inventory", "stock_movements_report"),
    "Inventory Valuation": ("reports_inventory", "inventory_valuation_report"),
    "Purchase Orders Pipeline": ("reports_purchases", "purchase_orders_pipeline_report"),
    "GRN Pending": ("reports_purchases", "grn_pending_report"),
    "Purchases by Vendor": ("reports_purchases", "purchases_by_vendor_report"),
    "Purchase Returns Summary": ("reports_purchases", "purchase_returns_summary_report"),
}


@st.cache_data(ttl=60, show_spinner=False)
def _period_summary(_report_service, start: date, end: date):
    return _report_service.get_period_summary(start, end)


def _render_aggregated_period_summary(report_service, start: date, end: date) -> None:
    st.subheader(AGGREGATED_PERIOD_LABEL)
    st.caption(f"{start:%d %b %Y} → {end:%d %b %Y}")
    summary = _period_summary(report_service, start, end)
    metric_grid(
        [
            ("Orders", summary.get("order_count", 0)),
            ("Invoiced", f"₹{summary.get('invoiced', 0):,.0f}"),
            ("Expenses", f"₹{summary.get('expenses', 0):,.0f}"),
        ],
        suffix="report_period_agg",
    )
    st.divider()


def _render_report_table(
    data: list,
    entity_key: str,
    filter_token: str,
    *,
    count_label: str = "rows",
):
    if not data:
        st.info("No rows match the selected filters.")
        return
    page_rows, page, total_pages = paginate_list(
        data,
        page_key=f"report_page_{entity_key}",
        page_size=REPORT_PAGE_SIZE,
        filter_key=f"report_filter_{entity_key}",
        filter_value=filter_token,
    )
    st.dataframe(pd.DataFrame(page_rows), use_container_width=True)
    render_page_controls(
        page,
        total_pages,
        len(data),
        page_key=f"report_page_{entity_key}",
        prev_key=f"report_prev_{entity_key}",
        next_key=f"report_next_{entity_key}",
        label=count_label,
    )


def _load_report_data(services: dict, report_type: str, service_filters):
    service_key, method_name = REPORT_LOADERS[report_type]
    service = services[service_key]
    method = getattr(service, method_name)
    return method(service_filters)


def _render_period_financial_summary(services: dict) -> None:
    schema = SCHEMA_BY_REPORT_TYPE["Period Financial Summary"]
    bar = render_filter_sort_bar(
        schema, services=services, title="Period Financial Summary"
    )
    committed = bar["filters"]
    sort = bar["sort"]
    service_filters = build_report_filter("Period Financial Summary", committed)
    data = _load_report_data(services, "Period Financial Summary", service_filters)
    ordered = F.sort_records(data, schema, sort)
    st.caption(f"{len(ordered)} metrics")
    if not ordered:
        st.info("No data for the selected period.")
        return
    metric_grid(
        [(row.get("metric", ""), row.get("value", "")) for row in ordered],
        suffix="report_period_financial",
        card_min_width=200,
    )


def _render_standard_report(services: dict, report_type: str) -> None:
    schema = SCHEMA_BY_REPORT_TYPE[report_type]
    bar = render_filter_sort_bar(schema, services=services, title=report_type)
    committed = bar["filters"]
    sort = bar["sort"]
    service_filters = build_report_filter(report_type, committed)
    token = report_filter_token(report_type, committed, sort)

    if report_type in SUMMARY_REPORT_TYPES:
        _render_aggregated_period_summary(
            services["reports"],
            service_filters.date_range.start,
            service_filters.date_range.end,
        )

    data = _load_report_data(services, report_type, service_filters)
    ordered = F.sort_records(data, schema, sort)
    st.caption(f"{len(ordered)} rows")
    _render_report_table(ordered, schema.entity_key, token)


def _render_customer_history(services: dict) -> None:
    customer_service = services["customers"]
    report_service = services["reports_customers"]
    query = st.text_input(
        "Search customer by name or phone", key="report_cust_search"
    )
    if not query:
        st.caption("Search and select a customer to view order history.")
        return
    customers = customer_service.search_customers(query)
    if not customers:
        st.info("No customers found")
        return
    options = {f"{c.customer_name} — {c.phone_number}": c.id for c in customers}
    choice = st.selectbox(
        "Select customer", list(options.keys()), key="report_cust_pick"
    )
    customer_id = options[choice]

    bar = render_filter_sort_bar(
        CUSTOMER_HISTORY,
        services=services,
        title="Customer Order History",
    )
    committed = bar["filters"]
    sort = bar["sort"]
    service_filters = build_report_filter(
        "Customer Order History",
        committed,
        customer_id=customer_id,
    )
    token = report_filter_token(
        "Customer Order History",
        committed,
        sort,
        customer_id=customer_id,
    )
    data = report_service.customer_order_history(service_filters)
    ordered = F.sort_records(data, CUSTOMER_HISTORY, sort)
    st.caption(f"{len(ordered)} rows")
    _render_report_table(
        ordered,
        f"{CUSTOMER_HISTORY.entity_key}_{customer_id}",
        token,
    )


def _render_category_tab(services: dict, category: str, reports: list[str]) -> None:
    report_type = st.selectbox(
        "Report",
        reports,
        key=f"report_pick_{category.replace(' ', '_').lower()}",
    )
    st.divider()
    if report_type == "Customer Order History":
        _render_customer_history(services)
    elif report_type == "Period Financial Summary":
        _render_period_financial_summary(services)
    else:
        _render_standard_report(services, report_type)


def render(services: dict):
    st.title("Reports")
    st.caption("Browse reports by category — each tab has its own report list.")
    tabs = st.tabs(list(REPORT_CATEGORIES.keys()))
    for tab, (category, reports) in zip(tabs, REPORT_CATEGORIES.items()):
        with tab:
            _render_category_tab(services, category, reports)
