import streamlit as st

from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.filtering import ListSchema, SortOption
from vaybooks.bms.ui.styles import render_card_grid


PENDING_EDIT_WORKER = "pending_edit_worker"


def _activity_options(services) -> dict:
    activities = services["activities"].list_activities(active_only=False)
    return {a.activity_name: a.id for a in activities}


def _resolve_activity_ids(options: dict, selected_names: list[str]) -> list[str]:
    return [options[n] for n in selected_names if n in options]


@st.dialog("Add Worker")
def _add_worker_dialog(worker_service, services: dict):
    name = st.text_input("Worker Name", key="add_worker_name")
    act_opts = _activity_options(services)
    selected = st.multiselect(
        "Activities",
        list(act_opts.keys()),
        key="add_worker_acts",
        placeholder="Select activities this worker can do…",
    )
    if st.button("Create Worker", type="primary"):
        if not name.strip():
            st.error("Worker name is required")
            return
        try:
            worker_service.create_worker(name, _resolve_activity_ids(act_opts, selected))
            st.success(f"Created {name}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Worker")
def _edit_worker_dialog(worker_service, services: dict, worker_id: str):
    worker = worker_service.get_worker(worker_id)
    if not worker:
        st.error("Worker not found")
        return

    act_opts = _activity_options(services)
    act_name_by_id = {v: k for k, v in act_opts.items()}
    current_names = [act_name_by_id.get(aid) for aid in worker.activity_ids]
    current_names = [n for n in current_names if n]

    name = st.text_input("Worker Name", value=worker.worker_name, key="edit_worker_name")
    selected = st.multiselect(
        "Activities",
        list(act_opts.keys()),
        default=current_names,
        key="edit_worker_acts",
        placeholder="Select activities this worker can do…",
    )
    is_active = st.checkbox("Active", value=worker.is_active, key="edit_worker_active")

    if st.button("Save Changes", type="primary"):
        if not name.strip():
            st.error("Worker name is required")
            return
        try:
            worker_service.update_worker(
                worker_id,
                name,
                _resolve_activity_ids(act_opts, selected),
                is_active,
            )
            st.success("Worker updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _worker_card(worker, activity_names: dict, index: int):
    with st.container(border=True):
        status = "Active" if worker.is_active else "Inactive"
        st.markdown(f"**{worker.worker_name}**")
        st.caption(status)
        acts = [activity_names.get(aid, "⚠️ Unknown activity") for aid in worker.activity_ids]
        st.write("Activities: " + (", ".join(acts) if acts else "—"))
        if st.button(
            "Edit",
            key=f"edit_worker_btn_{index}_{worker.id}",
            use_container_width=True,
        ):
            st.session_state[PENDING_EDIT_WORKER] = worker.id


def _load_workers(services, filters, sort):
    try:
        return services["workers"].list_workers(active_only=False)
    except Exception:
        return []


def _render_cards(page_workers, services):
    activities = services["activities"].list_activities(active_only=False)
    activity_names = {a.id: a.activity_name for a in activities}
    render_card_grid(
        page_workers,
        lambda worker, i: _worker_card(worker, activity_names, i),
        suffix="workers",
    )


def render(services: dict):
    worker_service = services["workers"]
    # Local schema (simple list page with only pagination/search handled by base component).
    WORKERS = ListSchema(
        entity_key="workers",
        title="Workers",
        filter_fields=[],
        sort_options=[
            SortOption("created_at", "Created (newest)"),
            SortOption("worker_name", "Worker name"),
        ],
        default_sort="created_at",
    )
    bar = render_list(
        WORKERS,
        services=services,
        load_fn=_load_workers,
        card_renderer=_render_cards,
        primary_label="Add Worker",
        primary_key="workers_add_btn",
        count_label="workers",
        empty_text="No workers configured yet.",
    )
    if bar["primary_clicked"]:
        _add_worker_dialog(worker_service, services)

    pending = st.session_state.pop(PENDING_EDIT_WORKER, None)
    if pending:
        _edit_worker_dialog(worker_service, services, pending)

