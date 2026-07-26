"""Chronological CRM activity timeline shared by lead / enquiry / customer views."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import streamlit as st

from vaybooks.bms.ui.components.crm.common import fmt_datetime, status_color
from vaybooks.bms.ui.crm_adapters import field, text
from vaybooks.bms.ui.styles import status_badge

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _stamp(activity: Any) -> datetime:
    value = (
        field(activity, "activity_at")
        or field(activity, "completed_at")
        or field(activity, "scheduled_at")
        or field(activity, "created_at")
    )
    if not isinstance(value, datetime):
        return _EPOCH
    # Mixed naive/aware stamps would break comparison during sorting.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def sort_timeline(activities: Iterable[Any], *, newest_first: bool = True) -> list:
    return sorted(activities, key=_stamp, reverse=newest_first)


def render_timeline(
    activities: Iterable[Any],
    *,
    limit: int = 25,
    empty_text: str = "No CRM activity recorded yet.",
) -> None:
    ordered = sort_timeline(activities)
    if not ordered:
        st.caption(empty_text)
        return

    for activity in ordered[:limit]:
        status = text(field(activity, "status"))
        automatic = text(field(activity, "origin")) == "Automatic"
        stamp = _stamp(activity)
        head_col, badge_col = st.columns([4, 2], vertical_alignment="center")
        with head_col:
            st.markdown(
                f"**{text(field(activity, 'activity_type'), default='Activity')}** · "
                f"{fmt_datetime(stamp) if stamp != _EPOCH else '—'}"
            )
        with badge_col:
            badges = status_badge(status, status_color(status), compact=True)
            if automatic:
                badges += " " + status_badge("Auto", "violet", compact=True)
            st.markdown(badges, unsafe_allow_html=True)

        details = [
            text(field(activity, "party_name")),
            text(field(activity, "assigned_user_name")),
            text(field(activity, "outcome")),
        ]
        detail_line = " · ".join(d for d in details if d)
        if detail_line:
            st.caption(detail_line)
        notes = text(field(activity, "notes"))
        if notes:
            st.caption(notes)
        st.divider()

    if len(ordered) > limit:
        st.caption(f"Showing the latest {limit} of {len(ordered)} activities.")
