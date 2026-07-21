"""BOQ tab — register + dialog CRUD (Customization-style)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectBoqItemType
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.pages.projects.workspace import helpers as H

BOQ_ADD = "prj_boq_add_dialog"
BOQ_EDIT = "prj_boq_edit_dialog"
BOQ_EDIT_ID = "prj_boq_edit_id"
BOQ_DEL = "prj_boq_del_dialog"
BOQ_DEL_ID = "prj_boq_del_id"
BOQ_IMPORT = "prj_boq_import_dialog"
BOQ_RATE = "prj_boq_rate_dialog"
BOQ_RATE_ID = "prj_boq_rate_id"


def _boq_tree_rows(items) -> list[dict]:
    by_parent: dict[str | None, list] = {}
    for item in sorted(items, key=lambda i: (i.sort_order, i.code)):
        by_parent.setdefault(item.parent_id, []).append(item)

    rows: list[dict] = []

    def walk(parent_id, depth=0):
        for item in by_parent.get(parent_id, []):
            prefix = "  " * depth
            contracted = (item.contracted_qty or 0) + (item.varied_qty or 0)
            rows.append(
                {
                    "id": item.id,
                    "code": f"{prefix}{item.code}",
                    "description": item.description,
                    "type": item.item_type.value,
                    "unit": item.unit,
                    "est qty": item.estimated_qty,
                    "sell rate": item.selling_rate,
                    "estimated value": item.estimated_value,
                    "contracted qty": item.contracted_qty,
                    "contracted rate": item.contracted_rate,
                    "measured": item.measured_qty,
                    "certified": item.certified_qty,
                    "billed": item.billed_qty,
                    "balance": round(contracted - (item.billed_qty or 0), 4),
                }
            )
            walk(item.id, depth + 1)

    walk(None)
    return rows


def _phase_options(project) -> dict[str, str | None]:
    opts: dict[str, str | None] = {"— None —": None}
    for phase in sorted(project.phases or [], key=lambda p: p.sort_order):
        opts[phase.name] = phase.id
    return opts


@st.dialog("Add BOQ item", width="large", on_dismiss=make_dismiss_handler(BOQ_ADD))
def _add_boq_dialog(boq_svc, project, items) -> None:
    sections = [i for i in items if i.item_type == ProjectBoqItemType.SECTION]
    parent_opts = {"— Root —": None}
    parent_opts.update({f"{s.code} — {s.description}": s.id for s in sections})
    phase_opts = _phase_options(project)

    c1, c2 = st.columns(2)
    code = c1.text_input("Code", key="prj_boq_dlg_code")
    description = c2.text_input("Description", key="prj_boq_dlg_desc")
    c3, c4, c5 = st.columns(3)
    item_type = c3.selectbox(
        "Type",
        options=[t.value for t in ProjectBoqItemType],
        index=1,
        key="prj_boq_dlg_type",
    )
    unit = c4.text_input("Unit", value="Nos", key="prj_boq_dlg_unit")
    est_qty = c5.number_input("Est qty", min_value=0.0, value=0.0, key="prj_boq_dlg_qty")
    c6, c7, c8 = st.columns(3)
    sell_rate = c6.number_input(
        "Sell rate", min_value=0.0, value=0.0, step=100.0, key="prj_boq_dlg_rate"
    )
    parent_label = c7.selectbox(
        "Parent section", options=list(parent_opts.keys()), key="prj_boq_dlg_parent"
    )
    phase_label = c8.selectbox(
        "Phase", options=list(phase_opts.keys()), key="prj_boq_dlg_phase"
    )

    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(BOQ_ADD, None)
        st.rerun()
    if cols[1].button("Add item", type="primary", use_container_width=True):
        H.run_action(
            lambda: boq_svc.create_item(
                project.id,
                code,
                description,
                item_type=item_type,
                parent_id=parent_opts[parent_label],
                unit=unit,
                estimated_qty=est_qty,
                selling_rate=sell_rate,
                phase_id=phase_opts[phase_label],
            ),
            "BOQ item added",
        )
        st.session_state.pop(BOQ_ADD, None)


@st.dialog("Edit BOQ item", width="large", on_dismiss=make_dismiss_handler(BOQ_EDIT, BOQ_EDIT_ID))
def _edit_boq_dialog(boq_svc, item_id: str) -> None:
    item = boq_svc.get_item(item_id)
    if not item:
        st.error("BOQ item not found")
        return
    c1, c2 = st.columns(2)
    code = c1.text_input("Code", value=item.code, key="prj_boq_edit_code")
    description = c2.text_input(
        "Description", value=item.description, key="prj_boq_edit_desc"
    )
    c3, c4, c5 = st.columns(3)
    est_qty = c3.number_input(
        "Est qty",
        min_value=0.0,
        value=float(item.estimated_qty or 0),
        key="prj_boq_edit_qty",
    )
    sell_rate = c4.number_input(
        "Sell rate",
        min_value=0.0,
        value=float(item.selling_rate or 0),
        step=100.0,
        key="prj_boq_edit_rate",
    )
    unit = c5.text_input("Unit", value=item.unit, key="prj_boq_edit_unit")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(BOQ_EDIT, None)
        st.session_state.pop(BOQ_EDIT_ID, None)
        st.rerun()
    if cols[1].button("Save changes", type="primary", use_container_width=True):
        H.run_action(
            lambda: boq_svc.update_item(
                item.id,
                code=code,
                description=description,
                estimated_qty=est_qty,
                selling_rate=sell_rate,
                unit=unit,
            ),
            "BOQ item updated",
        )
        st.session_state.pop(BOQ_EDIT, None)
        st.session_state.pop(BOQ_EDIT_ID, None)


@st.dialog("Remove BOQ item", on_dismiss=make_dismiss_handler(BOQ_DEL, BOQ_DEL_ID))
def _delete_boq_dialog(boq_svc, item_id: str) -> None:
    item = boq_svc.get_item(item_id)
    if not item:
        st.error("BOQ item not found")
        return
    st.write(f"Remove **{item.code} — {item.description}**?")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(BOQ_DEL, None)
        st.session_state.pop(BOQ_DEL_ID, None)
        st.rerun()
    if cols[1].button("Remove", type="primary", use_container_width=True):
        H.run_action(lambda: boq_svc.delete_item(item.id), "BOQ item deleted")
        st.session_state.pop(BOQ_DEL, None)
        st.session_state.pop(BOQ_DEL_ID, None)


@st.dialog("Import BOQ CSV", width="large", on_dismiss=make_dismiss_handler(BOQ_IMPORT))
def _import_boq_dialog(boq_svc, project) -> None:
    st.caption(
        "Required: **code**, **description**. "
        "`item_type` is Section or Item. Use `parent_code` for hierarchy."
    )
    st.download_button(
        "Download sample CSV",
        data=boq_svc.sample_csv(),
        file_name="boq_sample.csv",
        mime="text/csv",
        key="prj_boq_dlg_sample",
        use_container_width=True,
    )
    uploaded = st.file_uploader("BOQ CSV", type=["csv"], key="prj_boq_dlg_upload")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(BOQ_IMPORT, None)
        st.rerun()
    if cols[1].button("Import", type="primary", use_container_width=True):
        if uploaded is None:
            st.error("Choose a CSV file first")
            return
        csv_text = uploaded.getvalue().decode("utf-8", errors="replace")
        try:
            result = boq_svc.import_csv(project.id, csv_text)
            created = len(result.get("created") or [])
            errors = result.get("errors") or []
            if created:
                st.success(f"Imported {created} item(s)")
            for err in errors:
                st.warning(err)
            if created:
                st.session_state.pop(BOQ_IMPORT, None)
                st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog(
    "Rate analysis",
    width="large",
    on_dismiss=make_dismiss_handler(BOQ_RATE, BOQ_RATE_ID),
)
def _rate_analysis_dialog(boq_svc, item_id: str) -> None:
    item = boq_svc.get_item(item_id)
    if not item:
        st.error("BOQ item not found")
        return
    st.caption(f"{item.code} — {item.description}")
    c1, c2, c3 = st.columns(3)
    material = c1.number_input(
        "Material", min_value=0.0, value=float(item.material_cost or 0), key="prj_ra_mat"
    )
    labour = c2.number_input(
        "Labour", min_value=0.0, value=float(item.labour_cost or 0), key="prj_ra_lab"
    )
    equipment = c3.number_input(
        "Equipment",
        min_value=0.0,
        value=float(item.equipment_cost or 0),
        key="prj_ra_eq",
    )
    c4, c5, c6 = st.columns(3)
    subcon = c4.number_input(
        "Subcon", min_value=0.0, value=float(item.subcon_cost or 0), key="prj_ra_sub"
    )
    overhead = c5.number_input(
        "Overhead",
        min_value=0.0,
        value=float(item.overhead_cost or 0),
        key="prj_ra_oh",
    )
    contingency = c6.number_input(
        "Contingency",
        min_value=0.0,
        value=float(item.contingency_cost or 0),
        key="prj_ra_cont",
    )
    margin = st.number_input("Margin %", min_value=0.0, value=10.0, key="prj_ra_margin")
    override = st.number_input(
        "Override selling rate (optional, 0 = use margin)",
        min_value=0.0,
        value=0.0,
        key="prj_ra_sell",
    )
    reason = st.text_input("Override reason", key="prj_ra_reason")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(BOQ_RATE, None)
        st.session_state.pop(BOQ_RATE_ID, None)
        st.rerun()
    if cols[1].button("Save analysis", type="primary", use_container_width=True):
        kwargs = dict(
            material_cost=material,
            labour_cost=labour,
            equipment_cost=equipment,
            subcon_cost=subcon,
            overhead_cost=overhead,
            contingency_cost=contingency,
        )
        if override > 0:
            kwargs["selling_rate"] = override
            kwargs["override_reason"] = reason
        else:
            kwargs["margin_pct"] = margin
        H.run_action(
            lambda: boq_svc.save_rate_analysis(item.id, **kwargs),
            "Rate analysis saved",
        )
        st.session_state.pop(BOQ_RATE, None)
        st.session_state.pop(BOQ_RATE_ID, None)


def render_boq(services: dict, project) -> None:
    from vaybooks.bms.ui.pages.projects.session_user import can_view_internal_cost

    boq_svc = services.get("project_boq")
    if boq_svc is None:
        st.warning("BOQ service is not configured.")
        return
    view_cost = can_view_internal_cost(services, project.id)

    try:
        items = boq_svc.list_items(project.id)
        totals = boq_svc.rollup_totals(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("Line items", totals.get("item_count", 0))
    metric_cols[1].metric("Estimated value", H.fmt_money(totals.get("estimated_value")))
    metric_cols[2].metric("Contracted value", H.fmt_money(totals.get("contracted_value")))
    metric_cols[3].metric(
        "Measured / Certified / Billed",
        f"{totals.get('measured_qty_total', 0):,.1f} / "
        f"{totals.get('certified_qty_total', 0):,.1f} / "
        f"{totals.get('billed_qty_total', 0):,.1f}",
    )

    actions = st.columns(4)
    if actions[0].button("Add item", type="primary", key="prj_boq_add_btn"):
        st.session_state[BOQ_ADD] = True
        st.rerun()
    if actions[1].button("Import CSV", key="prj_boq_import_open"):
        st.session_state[BOQ_IMPORT] = True
        st.rerun()
    if actions[2].button("Seed apartment interior", key="prj_boq_seed"):
        H.run_action(
            lambda: boq_svc.seed_from_apartment_interior(project.id),
            "BOQ seeded",
        )

    if items:
        rows = _boq_tree_rows(items)
        st.dataframe(
            pd.DataFrame([{k: v for k, v in r.items() if k != "id"} for r in rows]),
            use_container_width=True,
            hide_index=True,
        )
        id_by_code = {r["code"].strip(): r["id"] for r in rows}
        pick = st.selectbox(
            "Select item to edit or remove",
            options=list(id_by_code.keys()),
            key="prj_boq_pick",
        )
        item_id = id_by_code.get(pick)
        e1, e2, e3 = st.columns(3)
        if e1.button("Edit selected", key="prj_boq_edit_btn", use_container_width=True):
            st.session_state[BOQ_EDIT] = True
            st.session_state[BOQ_EDIT_ID] = item_id
            st.rerun()
        if e2.button(
            "Rate analysis", key="prj_boq_rate_btn", use_container_width=True
        ):
            if not view_cost:
                st.error("You do not have permission to view or edit internal cost rates.")
            else:
                st.session_state[BOQ_RATE] = True
                st.session_state[BOQ_RATE_ID] = item_id
                st.rerun()
        if e3.button("Remove selected", key="prj_boq_del_btn", use_container_width=True):
            st.session_state[BOQ_DEL] = True
            st.session_state[BOQ_DEL_ID] = item_id
            st.rerun()
    else:
        H.empty_state("No BOQ items yet. Add an item or import CSV.")

    if st.session_state.get(BOQ_ADD):
        _add_boq_dialog(boq_svc, project, items)
    if st.session_state.get(BOQ_EDIT) and st.session_state.get(BOQ_EDIT_ID):
        _edit_boq_dialog(boq_svc, st.session_state[BOQ_EDIT_ID])
    if view_cost and st.session_state.get(BOQ_RATE) and st.session_state.get(BOQ_RATE_ID):
        _rate_analysis_dialog(boq_svc, st.session_state[BOQ_RATE_ID])
    if st.session_state.get(BOQ_DEL) and st.session_state.get(BOQ_DEL_ID):
        _delete_boq_dialog(boq_svc, st.session_state[BOQ_DEL_ID])
    if st.session_state.get(BOQ_IMPORT):
        _import_boq_dialog(boq_svc, project)
