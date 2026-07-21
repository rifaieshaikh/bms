import streamlit as st

from vaybooks.bms.domain.projects.activity_catalog import (
    COMPLETED_STATUS,
    CREATED_STATUS,
    category_metadata,
)
from vaybooks.bms.domain.shared.enums import ActivityCategory
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.list_schemas import PROJECT_ACTIVITIES

PENDING_EDIT_PROJECT_ACTIVITY = "pending_edit_project_activity"

_SYSTEM_ACTIVITY_NAMES = frozenset(
    {
        "Demolition",
        "Electrical",
        "Civil Works",
        "Plumbing",
        "Carpentry",
        "Painting",
        "Material Supply",
        "Specialist Subcon",
    }
)


def _category_options() -> list[str]:
    return [category.value for category in ActivityCategory]


def _parse_statuses(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _statuses_caption() -> None:
    st.caption(
        f"Every activity starts at **{CREATED_STATUS}** and ends at "
        f"**{COMPLETED_STATUS}**. Add any custom statuses in between, one per line."
    )


@st.dialog("Add Project Activity")
def _add_activity_dialog(activity_service):
    name = st.text_input("Activity Name", key="add_prj_act_name")
    category_value = st.selectbox(
        "Activity Type",
        _category_options(),
        key="add_prj_act_category",
    )
    category = ActivityCategory(category_value)
    meta = category_metadata(category)

    default_amount = st.number_input(
        "Default Amount (₹)",
        min_value=0.0,
        key="add_prj_act_amount",
    )

    hourly_rate = 0.0
    if meta["requires_pricing"]:
        st.caption("Time tracking is required. Set the default hourly rate.")
        hourly_rate = st.number_input(
            "Default Hourly Rate", min_value=0.0, key="add_prj_act_rate"
        )
    else:
        st.caption("No pricing needed — this is just an activity of this type.")

    st.markdown("**Statuses**")
    _statuses_caption()
    custom_statuses_raw = st.text_area(
        "Custom Statuses",
        placeholder="e.g.\nCutting\nStitching\nQuality Check",
        key="add_prj_act_statuses",
    )

    if st.button("Create Activity", type="primary"):
        if not name.strip():
            st.error("Error: Activity name is required")
            return
        try:
            activity_service.create_activity(
                name,
                category_value,
                hourly_rate,
                default_amount,
                _parse_statuses(custom_statuses_raw),
            )
            st.success(f"Created {name}")
            st.rerun()
        except Exception as exc:
            st.error(f"Error: {exc}")


@st.dialog("Edit Project Activity")
def _edit_activity_dialog(activity_service, activity_id: str):
    activity = activity_service.get_activity(activity_id)
    if not activity:
        st.error("Error: Activity not found")
        return

    name = st.text_input(
        "Activity Name", value=activity.activity_name, key="edit_prj_act_name"
    )
    options = _category_options()
    category_value = st.selectbox(
        "Activity Type",
        options,
        index=options.index(activity.activity_category.value),
        key="edit_prj_act_category",
    )
    category = ActivityCategory(category_value)
    meta = category_metadata(category)

    default_amount = st.number_input(
        "Default Amount (₹)",
        min_value=0.0,
        value=float(activity.default_amount or 0),
        key="edit_prj_act_amount",
    )

    hourly_rate = activity.default_hourly_rate
    if meta["requires_pricing"]:
        st.caption("Time tracking is required. Set the default hourly rate.")
        hourly_rate = st.number_input(
            "Default Hourly Rate",
            min_value=0.0,
            value=float(activity.default_hourly_rate or 0),
            key="edit_prj_act_rate",
        )
    else:
        st.caption("No pricing needed — this is just an activity of this type.")

    st.markdown("**Statuses**")
    _statuses_caption()
    custom_statuses_raw = st.text_area(
        "Custom Statuses",
        value="\n".join(activity.custom_statuses),
        placeholder="e.g.\nCutting\nStitching\nQuality Check",
        key="edit_prj_act_statuses",
    )
    st.caption("Flow: " + " → ".join(activity.statuses))

    is_active = st.checkbox("Active", value=activity.is_active, key="edit_prj_act_active")

    if st.button("Save Changes", type="primary"):
        if not name.strip():
            st.error("Error: Activity name is required")
            return
        try:
            activity_service.update_activity_details(
                activity_id,
                name,
                category_value,
                hourly_rate,
                default_amount,
                is_active,
                _parse_statuses(custom_statuses_raw),
            )
            st.success("Activity updated")
            st.rerun()
        except Exception as exc:
            st.error(f"Error: {exc}")


def _activity_card(activity, index: int):
    with st.container(border=True):
        status = "Active" if activity.is_active else "Inactive"
        st.markdown(f"**{activity.activity_name}**")
        tags = [activity.activity_category.value, status]
        if activity.is_system or activity.activity_name in _SYSTEM_ACTIVITY_NAMES:
            tags.append("System")
        st.caption(" · ".join(tags))

        if activity.default_amount:
            st.write(f"Default amount: ₹{activity.default_amount:,.0f}")

        if activity.requires_time_tracking:
            st.write("Time tracking: Required")
        else:
            st.write("Time tracking: Not required")

        if activity.requires_pricing:
            st.write(f"Hourly rate: ₹{activity.default_hourly_rate:,.0f}")

        st.write("Statuses: " + " → ".join(activity.statuses))

        if st.button(
            "Edit",
            key=f"edit_prj_act_btn_{index}_{activity.id}",
            use_container_width=True,
        ):
            st.session_state[PENDING_EDIT_PROJECT_ACTIVITY] = activity.id


def _load_activities(services, filters, sort):
    try:
        return services["project_activity_configs"].list_activities(active_only=False)
    except Exception:
        return []


def _render_cards(page_activities, services):
    render_card_grid(
        page_activities,
        lambda activity, i: _activity_card(activity, i),
        suffix="project_activities",
    )


def render(services: dict):
    activity_service = services["project_activity_configs"]
    bar = render_list(
        PROJECT_ACTIVITIES,
        services=services,
        load_fn=_load_activities,
        card_renderer=_render_cards,
        primary_label="Add Activity",
        primary_key="project_activities_add_btn",
        count_label="activities",
        empty_text="No project activities configured yet.",
        page_key_nav="project_activities_list",
    )
    if bar["primary_clicked"]:
        _add_activity_dialog(activity_service)

    pending = st.session_state.pop(PENDING_EDIT_PROJECT_ACTIVITY, None)
    if pending:
        _edit_activity_dialog(activity_service, pending)
