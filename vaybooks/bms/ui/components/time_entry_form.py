import streamlit as st

from vaybooks.bms.domain.shared.date_utils import calculate_duration_minutes


def time_entry_form(
    services: dict | None = None,
    *,
    activity_id: str | None = None,
    key_prefix: str = "time",
    field_errors: dict | None = None,
):
    field_errors = field_errors or {}
    work_date = st.date_input("Work Date", key=f"{key_prefix}_date")
    start_time = st.text_input("Start Time (HH:MM)", value="", key=f"{key_prefix}_start")
    if field_errors.get("start_time"):
        st.error(field_errors["start_time"])
    end_time = st.text_input("End Time (HH:MM)", value="", key=f"{key_prefix}_end")
    if field_errors.get("end_time"):
        st.error(field_errors["end_time"])
    ends_next_day = st.checkbox(
        "Ends next day (overnight shift)",
        key=f"{key_prefix}_ends_next_day",
    )
    workers = (
        services["workers"].list_workers_by_activity(activity_id)
        if services and activity_id and services.get("workers")
        else []
    )
    worker_options = [w.worker_name for w in workers] if workers else ["—"]
    selected_worker = st.selectbox("Worker", worker_options, key=f"{key_prefix}_worker")
    worker_name = "" if selected_worker == "—" else selected_worker
    notes = st.text_area("Notes", key=f"{key_prefix}_notes")

    duration = None
    try:
        if start_time and end_time:
            duration = calculate_duration_minutes(
                start_time, end_time, ends_next_day=ends_next_day
            )
            st.info(f"Duration: {duration} minutes ({duration / 60:.2f} hours)")
    except Exception as e:
        st.error(str(e))

    return {
        "work_date": work_date,
        "start_time": start_time,
        "end_time": end_time,
        "ends_next_day": ends_next_day,
        "worker_name": worker_name,
        "notes": notes,
        "duration_minutes": duration,
    }
