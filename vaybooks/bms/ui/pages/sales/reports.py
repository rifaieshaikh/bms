"""Sales Reports — Filters dialog (incl. date presets) and CSV download."""

from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd
import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.components.common.filter_sort_bar import (
    _mtd_range,
    _normalize_date_range,
    render_filter_sort_bar,
)
from vaybooks.bms.ui.components.common.report_filters import report_filter_token
from vaybooks.bms.ui.pagination import REPORT_PAGE_SIZE, paginate_list, render_page_controls
from vaybooks.bms.ui.report_schemas import SCHEMA_BY_REPORT_TYPE

SALES_REPORT_TYPES = [
    "Sales Orders Pipeline",
    "Delivery Pending",
    "Sales by Customer",
    "Sales Returns Summary",
]

_DATE_FIELD_BY_REPORT = {
    "Sales Orders Pipeline": "order_date",
    "Delivery Pending": "order_date",
    "Sales Returns Summary": "return_date",
}

_DATE_CAPTION = {
    "Sales Orders Pipeline": "Filtered by sales order date.",
    "Delivery Pending": "Filtered by linked SO order date.",
    "Sales by Customer": "Filtered by sales invoice date.",
    "Sales Returns Summary": "Filtered by return date.",
}


def _slug(report_type: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", report_type.lower()).strip("_")


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _in_range(value, start: date, end: date) -> bool:
    d = _as_date(value)
    if d is None:
        return False
    return start <= d <= end


def _filter_by_date(rows: list[dict], report_type: str, start: date, end: date) -> list:
    field = _DATE_FIELD_BY_REPORT.get(report_type)
    if not field:
        return list(rows)
    return [row for row in rows if _in_range(row.get(field), start, end)]


def _resolved_range(committed: dict) -> tuple[date, date]:
    return _normalize_date_range(committed.get("date_range")) or _mtd_range()


def _non_date_filters(committed: dict) -> dict:
    return {k: v for k, v in committed.items() if k != "date_range"}


def _load_all(reports_svc, report_type: str) -> list:
    if report_type == "Sales Orders Pipeline":
        return reports_svc.sales_orders_pipeline()
    if report_type == "Delivery Pending":
        return reports_svc.delivery_pending()
    if report_type == "Sales by Customer":
        return reports_svc.sales_by_customer()
    if report_type == "Sales Returns Summary":
        return reports_svc.sales_returns_summary()
    return []


def _load_dated(reports_svc, report_type: str, start: date, end: date) -> list:
    if report_type == "Sales by Customer":
        return reports_svc.sales_by_customer(start, end)
    if report_type == "Sales Returns Summary":
        return reports_svc.sales_returns_summary(start, end)
    return _filter_by_date(_load_all(reports_svc, report_type), report_type, start, end)


def _export_buttons(
    filtered_df: pd.DataFrame,
    all_df: pd.DataFrame,
    report_type: str,
) -> None:
    slug = _slug(report_type)
    today = date.today().isoformat()
    cols = st.columns(2)
    with cols[0]:
        st.download_button(
            "Download filtered CSV",
            data=filtered_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{slug}_filtered_{today}.csv",
            mime="text/csv",
            key=f"sales_report_dl_filtered_{slug}",
            disabled=filtered_df.empty,
            use_container_width=True,
            icon=":material/download:",
            help="Rows matching the Filters dialog (including period).",
        )
    with cols[1]:
        st.download_button(
            "Download all CSV",
            data=all_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{slug}_all_{today}.csv",
            mime="text/csv",
            key=f"sales_report_dl_all_{slug}",
            disabled=all_df.empty,
            use_container_width=True,
            icon=":material/download:",
            help="All rows with no date or other filters.",
        )


def _to_dataframe(rows: list) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _render_table(
    data: list,
    entity_key: str,
    filter_token: str,
) -> None:
    if not data:
        st.info("No rows match the selected filters.")
        return
    page_rows, page, total_pages = paginate_list(
        data,
        page_key=f"sales_report_page_{entity_key}",
        page_size=REPORT_PAGE_SIZE,
        filter_key=f"sales_report_filter_{entity_key}",
        filter_value=filter_token,
    )
    st.dataframe(pd.DataFrame(page_rows), use_container_width=True, hide_index=True)
    render_page_controls(
        page,
        total_pages,
        len(data),
        page_key=f"sales_report_page_{entity_key}",
        prev_key=f"sales_report_prev_{entity_key}",
        next_key=f"sales_report_next_{entity_key}",
        label="rows",
    )


def render(services: dict) -> None:
    st.header("Sales Reports")

    reports_svc = services.get("reports_sales_module")
    if reports_svc is None:
        st.error("Sales reports service is unavailable.")
        return

    report_type = st.selectbox(
        "Report",
        options=SALES_REPORT_TYPES,
        key="sales_reports_type",
    )

    schema = SCHEMA_BY_REPORT_TYPE[report_type]
    bar = render_filter_sort_bar(schema, services=services, title=report_type)
    committed = bar["filters"]
    sort = bar["sort"]
    start, end = _resolved_range(committed)
    token = report_filter_token(report_type, committed, sort)

    st.caption(
        f"{_DATE_CAPTION[report_type]} "
        f"**{start:%d %b %Y}** → **{end:%d %b %Y}**"
    )

    try:
        all_rows = _load_all(reports_svc, report_type)
        dated_rows = _load_dated(reports_svc, report_type, start, end)
        filtered_rows = F.apply_filters(
            dated_rows, schema, _non_date_filters(committed)
        )
        ordered_filtered = F.sort_records(filtered_rows, schema, sort)
        ordered_all = F.sort_records(all_rows, schema, sort)
    except Exception as exc:
        st.error(f"Could not load report: {exc}")
        return

    filtered_df = _to_dataframe(ordered_filtered)
    all_df = _to_dataframe(ordered_all)

    st.caption(
        f"{len(ordered_filtered)} filtered rows · {len(ordered_all)} total (no filters)"
    )
    _export_buttons(filtered_df, all_df, report_type)
    _render_table(ordered_filtered, schema.entity_key, token)
