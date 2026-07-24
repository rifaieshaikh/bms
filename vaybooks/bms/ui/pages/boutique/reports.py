"""Boutique Reports - module-facing subset of operations and labor reports."""

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
from vaybooks.bms.ui.pagination import (
    REPORT_PAGE_SIZE,
    paginate_list,
    render_page_controls,
)
from vaybooks.bms.ui.report_schemas import SCHEMA_BY_REPORT_TYPE

# report_type -> method on reports_boutique_module
BOUTIQUE_REPORT_METHODS: dict[str, str] = {
    "Order Pipeline": "order_pipeline_report",
    "Overdue Orders": "overdue_order_report",
    "Bills Pending Invoice": "bills_pending_invoice_report",
    "Activity Pending": "activity_pending_report",
    "Time Tracking": "time_tracking_report",
}

BOUTIQUE_REPORT_TYPES = list(BOUTIQUE_REPORT_METHODS.keys())


def _slug(report_type: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", report_type.lower()).strip("_")


def _download_button(df: pd.DataFrame, report_type: str) -> None:
    slug = _slug(report_type)
    today = date.today().isoformat()
    st.download_button(
        "Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"{slug}_{today}.csv",
        mime="text/csv",
        key=f"boutique_report_dl_{slug}",
        disabled=df.empty,
        use_container_width=True,
        icon=":material/download:",
        help="Rows matching the current filters.",
    )


def _render_table(data: list, entity_key: str, filter_token: str) -> None:
    if not data:
        st.info("No rows match the selected filters.")
        return
    page_rows, page, total_pages = paginate_list(
        data,
        page_key=f"boutique_report_page_{entity_key}",
        page_size=REPORT_PAGE_SIZE,
        filter_key=f"boutique_report_filter_{entity_key}",
        filter_value=filter_token,
    )
    st.dataframe(pd.DataFrame(page_rows), use_container_width=True, hide_index=True)
    render_page_controls(
        page,
        total_pages,
        len(data),
        page_key=f"boutique_report_page_{entity_key}",
        prev_key=f"boutique_report_prev_{entity_key}",
        next_key=f"boutique_report_next_{entity_key}",
        label="rows",
    )


def render(services: dict) -> None:
    st.header("Boutique Reports")

    reports_svc = services.get("reports_boutique_module")
    if reports_svc is None:
        st.error("Boutique reports service is unavailable.")
        return

    report_type = st.selectbox(
        "Report",
        options=BOUTIQUE_REPORT_TYPES,
        key="boutique_reports_type",
    )

    schema = SCHEMA_BY_REPORT_TYPE[report_type]
    bar = render_filter_sort_bar(schema, services=services, title=report_type)
    committed = bar["filters"]
    sort = bar["sort"]

    service_filters = build_report_filter(report_type, committed)
    token = report_filter_token(report_type, committed, sort)

    method_name = BOUTIQUE_REPORT_METHODS[report_type]
    try:
        rows = getattr(reports_svc, method_name)(service_filters)
        ordered = F.sort_records(rows, schema, sort)
    except Exception as exc:
        st.error(f"Could not load report: {exc}")
        return

    st.caption(f"{len(ordered)} rows")
    _download_button(pd.DataFrame(ordered), report_type)
    _render_table(ordered, schema.entity_key, token)
