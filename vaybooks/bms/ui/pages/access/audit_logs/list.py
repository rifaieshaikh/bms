"""Access — Audit Logs: per-user access audit trail with filters."""

from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from vaybooks.bms.domain.identity.audit import ACCESS_AUDIT_ACTIONS
from vaybooks.bms.ui.auth.guard import require_page_access


def _detail_summary(detail: dict) -> str:
    if not detail:
        return ""
    parts = []
    for key, value in detail.items():
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value)
        parts.append(f"{key}: {value}")
    return "; ".join(parts)


def render(services: dict):
    from vaybooks.bms.ui.keyboard.context import set_current_page

    set_current_page("audit_logs")
    if not require_page_access(services, "audit-logs"):
        return

    st.title("Audit Logs")
    st.caption("Sign-ins and access-administration changes, most recent first.")

    audit = services.get("access_audit")
    if audit is None:
        st.error("Audit service is not available.")
        return

    users = services["users"].list_users()
    user_labels = {u.id: f"{u.display_name or u.username} ({u.username})" for u in users}

    f_user, f_action, f_range, f_refresh = st.columns([3, 3, 2, 1])
    actor_id = f_user.selectbox(
        "User",
        options=[""] + list(user_labels),
        format_func=lambda uid: "All users" if not uid else user_labels[uid],
    )
    action = f_action.selectbox(
        "Action",
        options=[""] + list(ACCESS_AUDIT_ACTIONS),
        format_func=lambda a: "All actions" if not a else a,
    )
    range_choice = f_range.selectbox(
        "Period",
        options=["all", "7", "30", "90"],
        format_func=lambda v: {
            "all": "All time",
            "7": "Last 7 days",
            "30": "Last 30 days",
            "90": "Last 90 days",
        }[v],
        index=0,
    )
    if f_refresh.button("Refresh", use_container_width=True):
        st.rerun()

    start = end = None
    if range_choice != "all":
        days = int(range_choice)
        # Use naive UTC bounds so they match utc_now() timestamps in Mongo.
        end = datetime.utcnow()
        start = end - timedelta(days=days)

    try:
        total = audit.count_entries()
        entries = audit.list_entries(
            actor_id=actor_id, action=action, start=start, end=end, limit=500
        )
    except Exception as exc:
        st.error(f"Could not load audit logs: {exc}")
        return

    st.caption(f"{len(entries)} shown · {total} total in database")

    if not entries:
        if total == 0:
            st.info(
                "No audit entries yet. Sign out and sign back in, or create/edit a "
                "user or role under Access — those actions write audit records."
            )
        else:
            st.info("No audit entries match the selected filters.")
        return

    hdr = st.columns([2, 2, 2, 3, 3])
    for col, label in zip(hdr, ("Time", "Actor", "Action", "Target", "Detail")):
        col.caption(label)
    for entry in entries:
        cols = st.columns([2, 2, 2, 3, 3])
        created = entry.created_at
        if hasattr(created, "strftime"):
            cols[0].write(created.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            cols[0].write(str(created))
        cols[1].write(entry.actor_name or entry.actor_id or "—")
        cols[2].code(entry.action, language=None)
        target = entry.target_label or entry.target_id
        cols[3].write(f"{entry.target_type}: {target}" if target else "—")
        cols[4].write(_detail_summary(entry.detail) or "—")
