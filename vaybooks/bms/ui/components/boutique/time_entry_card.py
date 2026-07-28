import streamlit as st

from vaybooks.bms.domain.shared.date_utils import minutes_to_hours
from vaybooks.bms.domain.boutique.time_tracking.entities import TimeEntry
from vaybooks.bms.ui.styles import status_badge
from vaybooks.bms.ui.theme.icons import icon_caption


def time_entry_card(entry: TimeEntry, key_prefix: str) -> tuple[bool, bool]:
    hours = minutes_to_hours(entry.duration_minutes)
    with st.container(border=True):
        st.markdown(f"**🧵 {entry.activity_name}**")
        st.markdown(
            status_badge(f"{hours:.1f} hrs", "gold"), unsafe_allow_html=True
        )
        st.caption(f"{entry.order_number} · {entry.bill_number}")
        st.write(f"📅 {entry.work_date}  ·  🕑 {entry.start_time}–{entry.end_time}")
        icon_caption(entry.worker_name or "—", icon="user")
        if entry.notes:
            icon_caption(entry.notes, icon="notes")

        cols = st.columns(2)
        edit_clicked = cols[0].button(
            "Edit",
            key=f"{key_prefix}_edit_{entry.id}",
            use_container_width=True,
        )
        delete_clicked = cols[1].button(
            "Delete",
            key=f"{key_prefix}_del_{entry.id}",
            use_container_width=True,
        )

    return edit_clicked, delete_clicked
