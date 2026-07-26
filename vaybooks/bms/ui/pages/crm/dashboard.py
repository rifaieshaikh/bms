"""CRM dashboard: KPIs, work queues, and drill-down into the CRM lists."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Sequence

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.crm.common import (
    CRM_UNAVAILABLE_TEXT,
    fmt_datetime,
    fmt_money,
    owner_label,
    page_adapter,
    status_color,
)
from vaybooks.bms.ui.components.crm.whatsapp import (
    arm_reminder_dialog,
    open_reminder_dialog_if_armed,
)
from vaybooks.bms.ui.crm_adapters import field, record_id, text
from vaybooks.bms.ui.crm_list_schemas import (
    CRM_ACTIVITIES,
    CRM_ENQUIRIES,
    CRM_LEADS,
    OPEN_ENQUIRY_STATUSES,
    OPEN_LEAD_STATUSES,
)
from vaybooks.bms.ui.pages.crm.drilldown import open_filtered_list
from vaybooks.bms.ui.styles import metric_grid, render_card_grid, status_badge

PAGE_KEY = "crm_dashboard"
QUEUE_LIMIT = 8
PERIOD_OPTIONS = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}


def _snapshot_value(snapshot: Any, name: str, default: Any = 0) -> Any:
    value = field(snapshot, name)
    return default if value is None else value


def _kpi_row(snapshot: Any) -> None:
    metric_grid(
        [
            ("Active leads", _snapshot_value(snapshot, "total_active_leads")),
            ("New in period", _snapshot_value(snapshot, "new_leads_in_period")),
            (
                "Unassigned leads",
                _snapshot_value(snapshot, "unassigned_leads"),
                "warn" if _snapshot_value(snapshot, "unassigned_leads") else "neutral",
            ),
            ("Open enquiries", _snapshot_value(snapshot, "open_enquiries")),
        ],
        suffix="crm_dash_pipeline",
    )
    metric_grid(
        [
            ("Follow-ups due today", _snapshot_value(snapshot, "follow_ups_due_today")),
            (
                "Overdue follow-ups",
                _snapshot_value(snapshot, "overdue_follow_ups"),
                "danger" if _snapshot_value(snapshot, "overdue_follow_ups") else "neutral",
            ),
            ("Visits scheduled today", _snapshot_value(snapshot, "visits_scheduled_today")),
            (
                "Not contacted recently",
                _snapshot_value(snapshot, "customers_not_contacted_recently"),
            ),
        ],
        suffix="crm_dash_activity",
    )
    metric_grid(
        [
            ("Converted in period", _snapshot_value(snapshot, "leads_converted_in_period")),
            (
                "Orders from CRM leads",
                _snapshot_value(snapshot, "orders_generated_from_crm_leads"),
            ),
            (
                "Collected after follow-up",
                fmt_money(
                    _snapshot_value(snapshot, "payments_collected_after_followups"), "₹0"
                ),
            ),
            ("Customers contacted", _snapshot_value(snapshot, "customers_contacted_in_period")),
        ],
        suffix="crm_dash_outcome",
    )


def _drilldowns() -> None:
    st.markdown("**Drill down**")
    cols = st.columns(5)
    if cols[0].button("Active leads", key="crm_dash_dd_active", width="stretch"):
        open_filtered_list(
            CRM_LEADS, "crm_leads_list", {"statuses": list(OPEN_LEAD_STATUSES)}
        )
    if cols[1].button("Unassigned", key="crm_dash_dd_unassigned", width="stretch"):
        open_filtered_list(CRM_LEADS, "crm_leads_list", {"assignment": "unassigned"})
    if cols[2].button("Overdue follow-ups", key="crm_dash_dd_overdue", width="stretch"):
        open_filtered_list(CRM_ACTIVITIES, "crm_activities_list", {"due": "overdue"})
    if cols[3].button("Due today", key="crm_dash_dd_today", width="stretch"):
        open_filtered_list(CRM_ACTIVITIES, "crm_activities_list", {"due": "today"})
    if cols[4].button("Open enquiries", key="crm_dash_dd_enquiries", width="stretch"):
        open_filtered_list(
            CRM_ENQUIRIES, "crm_enquiries_list", {"statuses": list(OPEN_ENQUIRY_STATUSES)}
        )


def _queue(
    title: str,
    rows: Sequence[Any],
    key_prefix: str,
    *,
    accent: str,
    title_fn: Callable[[Any], str],
    subtitle_fn: Callable[[Any], str],
    route: str,
    empty_msg: str,
) -> None:
    st.markdown(f"#### {title} &nbsp; :{accent}[{len(rows)}]")
    if not rows:
        st.caption(empty_msg)
        st.divider()
        return

    def _render(row: Any, index: int) -> None:
        with st.container(border=True):
            st.markdown(f"**{title_fn(row)}**")
            subtitle = subtitle_fn(row)
            if subtitle:
                st.caption(subtitle)
            status = text(field(row, "status"))
            if status:
                st.markdown(
                    status_badge(status, status_color(status), compact=True),
                    unsafe_allow_html=True,
                )
            if st.button(
                "Open →", key=f"{key_prefix}_open_{index}", width="stretch"
            ):
                navigation.go_to_detail(route, record_id(row))

    render_card_grid(list(rows[:QUEUE_LIMIT]), _render, suffix=key_prefix)
    if len(rows) > QUEUE_LIMIT:
        st.caption(f"+ {len(rows) - QUEUE_LIMIT} more")
    st.divider()


def _activity_subtitle(activity: Any) -> str:
    parts = [
        text(field(activity, "party_name")),
        fmt_datetime(field(activity, "scheduled_at")),
        owner_label(activity),
    ]
    return " · ".join(p for p in parts if p and p != "—")


def _lead_subtitle(lead: Any) -> str:
    parts = [text(field(lead, "phone")), text(field(lead, "city")), owner_label(lead)]
    return " · ".join(p for p in parts if p)


def _rep_summary(snapshot: Any) -> None:
    rows = _snapshot_value(snapshot, "sales_representative_activity_summary", [])
    if not rows:
        return
    st.markdown("#### Sales representative activity")
    st.dataframe(
        [
            {
                "Representative": row.get("assigned_user_name") or "Unassigned",
                "Activities": row.get("total", 0),
                "Completed": row.get("completed", 0),
                "Overdue": row.get("overdue", 0),
            }
            for row in rows
        ],
        width="stretch",
        hide_index=True,
    )


def _outstanding(snapshot: Any) -> None:
    rows = _snapshot_value(snapshot, "customers_with_outstanding_balances", [])
    if not rows:
        return
    st.markdown("#### Customers with outstanding balances")
    st.dataframe(
        [
            {
                "Customer": row.get("customer_name") or row.get("customer_id"),
                "Outstanding": fmt_money(row.get("outstanding_balance"), "₹0"),
            }
            for row in rows
        ],
        width="stretch",
        hide_index=True,
    )
    options = {
        (row.get("customer_name") or row.get("customer_id")): row.get("customer_id")
        for row in rows
        if row.get("customer_id")
    }
    if options:
        controls = st.columns([3, 1])
        selected = controls[0].selectbox(
            "Customer for payment reminder",
            list(options),
            key="crm_dash_outstanding_customer",
            label_visibility="collapsed",
        )
        if controls[1].button(
            "WhatsApp reminder",
            key="crm_dash_outstanding_whatsapp",
            width="stretch",
        ):
            arm_reminder_dialog(options[selected])
            st.rerun()


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.context import set_current_page

    set_current_page(PAGE_KEY)
    st.header("CRM Dashboard")

    adapter = page_adapter(services)
    if not adapter.available:
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    label = st.segmented_control(
        "Period",
        list(PERIOD_OPTIONS),
        default="Last 30 days",
        key="crm_dash_period",
    )
    days = PERIOD_OPTIONS.get(label or "Last 30 days", 30)
    period_end = datetime.now()
    period_start = period_end - timedelta(days=days)
    st.caption(f"Period: **{period_start:%d %b %Y}** → **{period_end:%d %b %Y}**")

    snapshot = adapter.dashboard_snapshot(
        period_start=period_start, period_end=period_end
    )
    if snapshot is None:
        st.info("CRM metrics are not available yet.")
        return

    _kpi_row(snapshot)
    _drilldowns()

    _queue(
        "My tasks today",
        _snapshot_value(snapshot, "my_tasks_today", []),
        "crm_dash_tasks",
        accent="blue",
        title_fn=lambda r: text(field(r, "activity_type"), default="Activity"),
        subtitle_fn=_activity_subtitle,
        route="crm_activity_detail",
        empty_msg="Nothing scheduled for today.",
    )
    _queue(
        "Overdue activities",
        _snapshot_value(snapshot, "overdue_activities", []),
        "crm_dash_overdue",
        accent="red",
        title_fn=lambda r: text(field(r, "activity_type"), default="Activity"),
        subtitle_fn=_activity_subtitle,
        route="crm_activity_detail",
        empty_msg="All clear — no overdue activities.",
    )
    _queue(
        "Upcoming visits",
        _snapshot_value(snapshot, "upcoming_visits", []),
        "crm_dash_visits",
        accent="orange",
        title_fn=lambda r: text(field(r, "party_name"), default="Visit"),
        subtitle_fn=_activity_subtitle,
        route="crm_activity_detail",
        empty_msg="No visits planned.",
    )
    _queue(
        "Leads requiring attention",
        _snapshot_value(snapshot, "leads_requiring_attention", []),
        "crm_dash_attention",
        accent="red",
        title_fn=lambda r: text(field(r, "name"), default="Lead"),
        subtitle_fn=_lead_subtitle,
        route="crm_lead_detail",
        empty_msg="No leads need attention right now.",
    )
    _queue(
        "Recently added leads",
        _snapshot_value(snapshot, "recently_added_leads", []),
        "crm_dash_recent",
        accent="blue",
        title_fn=lambda r: text(field(r, "name"), default="Lead"),
        subtitle_fn=_lead_subtitle,
        route="crm_lead_detail",
        empty_msg="No leads captured yet.",
    )

    _rep_summary(snapshot)
    _outstanding(snapshot)
    open_reminder_dialog_if_armed(services, adapter)
