"""CRM reports: all 34 named reports with shared filters, export, drill-down."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

import pandas as pd
import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.filter_sort_bar import (
    _normalize_date_range,
    render_filter_sort_bar,
)
from vaybooks.bms.ui.components.crm.common import CRM_UNAVAILABLE_TEXT, page_adapter
from vaybooks.bms.ui.components.crm.whatsapp import (
    arm_reminder_dialog,
    open_reminder_dialog_if_armed,
)
from vaybooks.bms.ui.crm_adapters import field, text
from vaybooks.bms.ui.crm_list_schemas import CRM_REPORT_FILTERS
from vaybooks.bms.ui.pages.crm.export import export_filename, rows_to_csv
from vaybooks.bms.ui.pagination import (
    REPORT_PAGE_SIZE,
    paginate_list,
    render_page_controls,
)

PAGE_KEY = "crm_reports"

CATEGORY_LABELS = {
    "engagement": "Customer Engagement",
    "conversion": "Conversion & Pipeline",
    "collection": "Payment & Collection",
    "rep": "Sales Representative",
    "management": "Management & Exceptions",
}

# Row keys that can be opened as a record, in priority order.
DRILL_TARGETS: tuple[tuple[str, str], ...] = (
    ("lead_id", "crm_lead_detail"),
    ("enquiry_id", "crm_enquiry_detail"),
    ("activity_id", "crm_activity_detail"),
    ("customer_id", "customer_detail"),
)


def _category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.title() or "Other")


def _grouped(reports: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for report in reports:
        groups.setdefault(_category_label(report.get("category", "")), []).append(report)
    return groups


def _build_filters(committed: dict):
    """Map the committed UI filters onto ``CrmReportFilters``."""
    date_range = _normalize_date_range(committed.get("date_range"))
    date_from = date_to = None
    if date_range:
        start, end = date_range
        date_from = datetime.combine(start, time.min)
        date_to = datetime.combine(end, time.max)

    values = {
        "date_from": date_from,
        "date_to": date_to,
        "assigned_user_id": committed.get("assigned_user_id") or "",
        "customer_id": committed.get("customer_id") or "",
        "activity_type": committed.get("activity_type") or "",
        "area": committed.get("area") or "",
        "branch": committed.get("branch") or "",
    }
    if committed.get("inactivity_days"):
        values["inactivity_days"] = int(committed["inactivity_days"])
    if committed.get("high_value_threshold"):
        values["high_value_threshold"] = float(committed["high_value_threshold"])

    try:
        from vaybooks.bms.application.crm.reports import CrmReportFilters
    except Exception:
        return values
    return CrmReportFilters(**values)


def _drill_row(row: dict) -> tuple[str, str]:
    """Return ``(record_id, route)`` for the first drillable key in ``row``."""
    for key, route in DRILL_TARGETS:
        value = text(row.get(key))
        if value:
            return value, route
    return "", ""


def _render_rows(
    report_id: str,
    columns: list[str],
    rows: list[dict],
    services: dict,
    adapter,
) -> None:
    page_rows, page, total_pages = paginate_list(
        rows,
        page_key=f"crm_report_page_{report_id}",
        page_size=REPORT_PAGE_SIZE,
        filter_key=f"crm_report_token_{report_id}",
        filter_value=str(len(rows)),
    )
    frame = pd.DataFrame(page_rows)
    if columns:
        ordered = [column for column in columns if column in frame.columns]
        extra = [column for column in frame.columns if column not in ordered]
        frame = frame[ordered + extra]
    st.dataframe(frame, width="stretch", hide_index=True)
    render_page_controls(
        page,
        total_pages,
        len(rows),
        page_key=f"crm_report_page_{report_id}",
        prev_key=f"crm_report_prev_{report_id}",
        next_key=f"crm_report_next_{report_id}",
        label="rows",
    )
    _render_drilldown(report_id, page_rows)
    reminder_reports = {
        "payment_promise_report",
        "overdue_collection_follow_ups",
        "customers_with_outstanding_balance_and_no_collection_activity",
        "customers_with_payments",
    }
    reminder_rows = [
        row for row in page_rows if text(row.get("customer_id"))
    ]
    if report_id in reminder_reports and reminder_rows:
        labels = {
            _row_label(row): text(row.get("customer_id")) for row in reminder_rows
        }
        controls = st.columns([3, 1])
        choice = controls[0].selectbox(
            "Customer for WhatsApp reminder",
            list(labels),
            key=f"crm_report_reminder_customer_{report_id}",
            label_visibility="collapsed",
        )
        if controls[1].button(
            "WhatsApp reminder",
            key=f"crm_report_reminder_{report_id}",
            width="stretch",
        ):
            arm_reminder_dialog(labels[choice])
            st.rerun()
    open_reminder_dialog_if_armed(services, adapter)


def _render_drilldown(report_id: str, page_rows: list[dict]) -> None:
    drillable = [(row, *_drill_row(row)) for row in page_rows]
    drillable = [item for item in drillable if item[1]]
    if not drillable:
        return
    labels = {
        f"{index + 1}. {_row_label(row)}": (record, route)
        for index, (row, record, route) in enumerate(drillable)
    }
    st.markdown("**Open a record**")
    cols = st.columns([3, 1])
    choice = cols[0].selectbox(
        "Row",
        list(labels),
        key=f"crm_report_drill_{report_id}",
        label_visibility="collapsed",
    )
    if cols[1].button("Open →", key=f"crm_report_drill_go_{report_id}", width="stretch"):
        record, route = labels[choice]
        navigation.go_to_detail(route, record)


def _row_label(row: dict) -> str:
    for key in (
        "customer_name",
        "lead_name",
        "party_name",
        "name",
        "enquiry_number",
        "lead_number",
        "activity_type",
        "sales_representative",
    ):
        value = text(row.get(key))
        if value:
            return value
    return "row"


def _summary(summary: Any) -> None:
    if not isinstance(summary, dict) or not summary:
        return
    items = [(key.replace("_", " ").title(), value) for key, value in summary.items()]
    cols = st.columns(min(len(items), 4))
    for index, (label, value) in enumerate(items):
        cols[index % len(cols)].metric(label, value)


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.context import set_current_page

    set_current_page(PAGE_KEY)
    st.header("CRM Reports")

    adapter = page_adapter(services)
    if not adapter.available:
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    catalog = adapter.list_reports()
    groups = _grouped(catalog)
    titles = {report["title"]: report["id"] for report in catalog}

    picker = st.columns([2, 3])
    category = picker[0].selectbox(
        "Category", list(groups), key="crm_reports_category"
    )
    options = [report["title"] for report in groups.get(category, [])]
    title = picker[1].selectbox("Report", options, key="crm_reports_report")
    report_id = titles.get(title, "")
    st.caption(f"{len(catalog)} CRM reports available.")

    bar = render_filter_sort_bar(
        CRM_REPORT_FILTERS, services=services, title=title or "CRM Reports"
    )
    filters = _build_filters(bar["filters"])

    try:
        result = adapter.run_report(report_id, filters)
    except Exception as exc:  # noqa: BLE001 - report engines raise domain errors
        st.error(f"Could not run this report: {exc}")
        return
    if result is None:
        st.info("This report is not available yet.")
        return

    rows = list(field(result, "rows", default=[]) or [])
    columns = list(field(result, "columns", default=[]) or [])
    _summary(field(result, "summary", default={}))

    st.caption(f"{len(rows)} rows")
    if adapter.can("crm.reports.export"):
        st.download_button(
            "Export CSV",
            data=rows_to_csv(rows, columns or (list(rows[0]) if rows else [])),
            file_name=export_filename(f"crm_{report_id or 'report'}"),
            mime="text/csv",
            key=f"crm_report_export_{report_id}",
            disabled=not rows,
            icon=":material/download:",
        )

    if not rows:
        st.info("No rows match the selected filters.")
        return
    _render_rows(report_id or "report", columns, rows, services, adapter)
