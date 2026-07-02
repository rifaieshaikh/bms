import streamlit as st

from vaybooks.bms.domain.activities.entities import (
    COMPLETED_STATUS,
    CREATED_STATUS,
    category_metadata,
)
from vaybooks.bms.domain.shared.enums import ActivityCategory

PENDING_EDIT_ACTIVITY = "pending_edit_activity"


def _category_options() -> list[str]:
    return [category.value for category in ActivityCategory]


def _parse_statuses(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _statuses_caption() -> None:
    st.caption(
        f"Every activity starts at **{CREATED_STATUS}** and ends at "
        f"**{COMPLETED_STATUS}**. Add any custom statuses in between, one per line."
    )


@st.dialog("Add Activity")
def _add_activity_dialog(activity_service):
    name = st.text_input("Activity Name", key="add_act_name")
    category_value = st.selectbox(
        "Activity Type",
        _category_options(),
        key="add_act_category",
    )
    category = ActivityCategory(category_value)
    meta = category_metadata(category)

    hourly_expense = 0.0
    if meta["requires_pricing"]:
        st.caption("Time tracking is required. Set the default hourly expense.")
        hourly_expense = st.number_input(
            "Default Hourly Expense", min_value=0.0, key="add_act_expense"
        )
    else:
        st.caption("No pricing needed — this is just an activity of this type.")

    st.markdown("**Statuses**")
    _statuses_caption()
    custom_statuses_raw = st.text_area(
        "Custom Statuses",
        placeholder="e.g.\nCutting\nStitching\nQuality Check",
        key="add_act_statuses",
    )

    if st.button("Create Activity", type="primary"):
        if not name.strip():
            st.error("Activity name is required")
            return
        try:
            activity_service.create_activity(
                name,
                category_value,
                hourly_expense,
                _parse_statuses(custom_statuses_raw),
            )
            st.success(f"Created {name}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Activity")
def _edit_activity_dialog(activity_service, activity_id: str):
    activity = activity_service.get_activity(activity_id)
    if not activity:
        st.error("Activity not found")
        return

    name = st.text_input("Activity Name", value=activity.activity_name, key="edit_act_name")
    options = _category_options()
    category_value = st.selectbox(
        "Activity Type",
        options,
        index=options.index(activity.activity_category.value),
        key="edit_act_category",
    )
    category = ActivityCategory(category_value)
    meta = category_metadata(category)

    hourly_expense = activity.default_hourly_expense
    if meta["requires_pricing"]:
        st.caption("Time tracking is required. Set the default hourly expense.")
        hourly_expense = st.number_input(
            "Default Hourly Expense",
            min_value=0.0,
            value=float(activity.default_hourly_expense),
            key="edit_act_expense",
        )
    else:
        st.caption("No pricing needed — this is just an activity of this type.")

    st.markdown("**Statuses**")
    _statuses_caption()
    custom_statuses_raw = st.text_area(
        "Custom Statuses",
        value="\n".join(activity.custom_statuses),
        placeholder="e.g.\nCutting\nStitching\nQuality Check",
        key="edit_act_statuses",
    )
    st.caption("Flow: " + " → ".join(activity.statuses))

    is_active = st.checkbox("Active", value=activity.is_active, key="edit_act_active")

    if st.button("Save Changes", type="primary"):
        if not name.strip():
            st.error("Activity name is required")
            return
        try:
            activity_service.update_activity_details(
                activity_id,
                name,
                category_value,
                hourly_expense,
                is_active,
                _parse_statuses(custom_statuses_raw),
            )
            st.success("Activity updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _activity_card(activity, index: int):
    with st.container(border=True):
        status = "Active" if activity.is_active else "Inactive"
        st.markdown(f"**{activity.activity_name}**")
        st.caption(f"{activity.activity_category.value} · {status}")

        if activity.requires_time_tracking:
            st.write("Time tracking: Required")
        else:
            st.write("Time tracking: Not required")

        if activity.requires_pricing:
            st.write(f"Hourly Expense: ₹{activity.default_hourly_expense:,.0f}")

        st.write("Statuses: " + " → ".join(activity.statuses))

        if st.button(
            "Edit",
            key=f"edit_act_btn_{index}_{activity.id}",
            use_container_width=True,
        ):
            st.session_state[PENDING_EDIT_ACTIVITY] = activity.id


def render(services: dict):
    st.title("Activity Configuration")
    activity_service = services["activities"]

    header_cols = st.columns([4, 1])
    with header_cols[0]:
        st.caption("Configure the activities that can be applied to customization items.")
    with header_cols[1]:
        if st.button("Add Activity", type="primary", use_container_width=True):
            _add_activity_dialog(activity_service)

    activities = activity_service.list_activities(active_only=False)
    if not activities:
        st.info("No activities configured yet.")
        return

    for row_start in range(0, len(activities), 3):
        row = activities[row_start : row_start + 3]
        cols = st.columns(len(row))
        for col_index, (col, activity) in enumerate(zip(cols, row)):
            with col:
                _activity_card(activity, row_start + col_index)

    pending = st.session_state.pop(PENDING_EDIT_ACTIVITY, None)
    if pending:
        _edit_activity_dialog(activity_service, pending)
