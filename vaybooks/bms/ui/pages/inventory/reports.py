"""Inventory Reports — filter bar, pagination, and CSV download."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.components.common.filter_sort_bar import render_filter_sort_bar
from vaybooks.bms.ui.components.common.report_filters import (
    build_report_filter,
    report_filter_token,
)
from vaybooks.bms.ui.pagination import REPORT_PAGE_SIZE, paginate_list, render_page_controls
from vaybooks.bms.ui.report_schemas import INVENTORY_REPORT_TYPES, SCHEMA_BY_REPORT_TYPE

_REPORT_LOADERS = {
    "Stock on Hand": "stock_on_hand_report",
    "Low Stock Alert": "low_stock_report",
    "Stock Movements": "stock_movements_report",
    "Inventory Valuation": "inventory_valuation_report",
    "Category Stock Summary": "category_stock_summary_report",
    "Dead / Slow-Moving Stock": "dead_stock_report",
    "Stock Movement Summary": "stock_movement_summary_report",
    "Cost vs Selling (Stock Margin)": "stock_margin_report",
    "Opening → Closing Stock": "opening_closing_stock_report",
    "HSN Stock Summary": "hsn_stock_summary_report",
    "Fast-Moving Stock": "fast_moving_stock_report",
    "Customer Latest Prices": "customer_latest_prices_report",
    "Inactive Products with Stock": "inactive_products_with_stock_report",
    "Product Rate Card": "product_rate_card_report",
}

_DATE_CAPTIONS = {
    "Stock Movements": "Filtered by movement date.",
    "Dead / Slow-Moving Stock": "Qty out measured within the selected period.",
    "Stock Movement Summary": "Aggregated by movement type within the period.",
    "Opening → Closing Stock": (
        "Opening is reconstructed from ledger movements before the period start. "
        "Create-time opening stock is recorded as a dated Receive."
    ),
    "Fast-Moving Stock": "Ranked by qty out within the selected period.",
    "Customer Latest Prices": (
        "Latest rate per customer×product. Optional effective-date filter "
        "limits which latest pairs are shown."
    ),
}


def _slug(report_type: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", report_type.lower()).strip("_")


def _to_dataframe(rows: list) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _export_buttons(filtered_df: pd.DataFrame, report_type: str) -> None:
    slug = _slug(report_type)
    today = date.today().isoformat()
    st.download_button(
        "Download CSV",
        data=filtered_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{slug}_{today}.csv",
        mime="text/csv",
        key=f"inv_report_dl_{slug}",
        disabled=filtered_df.empty,
        use_container_width=True,
        icon=":material/download:",
    )


def _render_table(data: list, entity_key: str, filter_token: str) -> None:
    if not data:
        st.info("No rows match the selected filters.")
        return
    page_rows, page, total_pages = paginate_list(
        data,
        page_key=f"inv_report_page_{entity_key}",
        page_size=REPORT_PAGE_SIZE,
        filter_key=f"inv_report_filter_{entity_key}",
        filter_value=filter_token,
    )
    st.dataframe(pd.DataFrame(page_rows), use_container_width=True, hide_index=True)
    render_page_controls(
        page,
        total_pages,
        len(data),
        page_key=f"inv_report_page_{entity_key}",
        prev_key=f"inv_report_prev_{entity_key}",
        next_key=f"inv_report_next_{entity_key}",
        label="rows",
    )


def render(services: dict) -> None:
    st.header("Inventory Reports")

    reports_svc = services.get("reports_inventory")
    if reports_svc is None:
        st.error("Inventory reports service is unavailable.")
        return

    report_type = st.selectbox(
        "Report",
        options=INVENTORY_REPORT_TYPES,
        key="inventory_reports_type",
    )

    schema = SCHEMA_BY_REPORT_TYPE[report_type]
    bar = render_filter_sort_bar(schema, services=services, title=report_type)
    committed = bar["filters"]
    sort = bar["sort"]
    token = report_filter_token(report_type, committed, sort)

    caption = _DATE_CAPTIONS.get(report_type)
    if caption:
        st.caption(caption)

    try:
        service_filters = build_report_filter(report_type, committed)
        method = getattr(reports_svc, _REPORT_LOADERS[report_type])
        rows = method(service_filters)
        ordered = F.sort_records(rows, schema, sort)
    except Exception as exc:
        st.error(f"Could not load report: {exc}")
        return

    filtered_df = _to_dataframe(ordered)
    st.caption(f"{len(ordered)} rows")
    _export_buttons(filtered_df, report_type)
    _render_table(ordered, schema.entity_key, token)
