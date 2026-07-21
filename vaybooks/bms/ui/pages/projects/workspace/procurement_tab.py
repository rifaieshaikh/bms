"""Procurement + materials tab for project workspace."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectStockMovementType
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.pages.projects.workspace import helpers as H

MR_DIALOG = "prj_mr_add_dialog"
STOCK_DIALOG = "prj_stock_add_dialog"
SUB_DIALOG = "prj_sub_add_dialog"
SUB_MEASURE = "prj_sub_measure_dialog"
SUB_MEASURE_ID = "prj_sub_measure_id"
SUB_CERTIFY = "prj_sub_certify_dialog"
SUB_CERTIFY_ID = "prj_sub_certify_id"


@st.dialog("New material request", on_dismiss=make_dismiss_handler(MR_DIALOG))
def _mr_dialog(services: dict, project) -> None:
    description = st.text_input("Item", key="prj_mr_desc")
    qty = st.number_input("Qty", min_value=0.0, value=1.0, key="prj_mr_qty")
    need_by = st.date_input("Need by", value=date.today(), key="prj_mr_need")
    invoice_party = st.selectbox(
        "Invoice party", options=["Contractor", "Customer"], key="prj_mr_party"
    )
    principal_agent = st.selectbox(
        "Principal / Agent", options=["Principal", "Agent"], key="prj_mr_pa"
    )
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(MR_DIALOG, None)
        st.rerun()
    if cols[1].button("Create", type="primary", use_container_width=True):
        try:
            services["project_procurement"].create_material_request(
                project.id,
                [{"description": description, "quantity": qty}],
                need_by=need_by,
                invoice_party=invoice_party,
                principal_agent=principal_agent,
            )
            st.session_state.pop(MR_DIALOG, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Record stock movement", on_dismiss=make_dismiss_handler(STOCK_DIALOG))
def _stock_dialog(services: dict, project) -> None:
    mtype = st.selectbox(
        "Type",
        options=[t.value for t in ProjectStockMovementType],
        key="prj_stock_type",
    )
    description = st.text_input("Description", key="prj_stock_desc")
    qty = st.number_input("Qty", value=1.0, key="prj_stock_qty")
    cost = st.number_input("Unit cost", min_value=0.0, value=0.0, key="prj_stock_cost")
    ownership = st.selectbox(
        "Ownership", options=["Contractor", "Customer"], key="prj_stock_own"
    )
    invoice_party = st.selectbox(
        "Invoice party",
        options=["Contractor", "Customer"],
        index=1 if ownership == "Customer" else 0,
        key="prj_stock_party",
    )
    principal_agent = st.selectbox(
        "Principal / Agent", options=["Principal", "Agent"], key="prj_stock_pa"
    )
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(STOCK_DIALOG, None)
        st.rerun()
    if cols[1].button("Save", type="primary", use_container_width=True):
        try:
            services["project_procurement"].record_stock_movement(
                project.id,
                mtype,
                description,
                qty,
                unit_cost=cost,
                ownership=ownership,
                invoice_party=invoice_party,
                principal_agent=principal_agent,
            )
            st.session_state.pop(STOCK_DIALOG, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("New subcontract order", on_dismiss=make_dismiss_handler(SUB_DIALOG))
def _sub_dialog(services: dict, project) -> None:
    vendor_name = st.text_input("Vendor name", key="prj_sub_vendor")
    description = st.text_input("Line description", key="prj_sub_desc")
    qty = st.number_input("Quantity", min_value=0.0, value=1.0, key="prj_sub_qty")
    rate = st.number_input("Rate", min_value=0.0, value=0.0, key="prj_sub_rate")
    retention = st.number_input(
        "Retention %", min_value=0.0, max_value=100.0, value=0.0, key="prj_sub_ret"
    )
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(SUB_DIALOG, None)
        st.rerun()
    if cols[1].button("Create", type="primary", use_container_width=True):
        try:
            services["project_subcontract"].create_order(
                project.id,
                vendor_id=vendor_name.strip().lower().replace(" ", "_") or "vendor",
                vendor_name=vendor_name,
                lines=[{"description": description, "quantity": qty, "rate": rate}],
                retention_pct=retention,
            )
            st.session_state.pop(SUB_DIALOG, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog(
    "Measure subcontract line",
    on_dismiss=make_dismiss_handler(SUB_MEASURE, SUB_MEASURE_ID),
)
def _sub_measure_dialog(services: dict, order_id: str) -> None:
    sub = services["project_subcontract"]
    try:
        order = sub.get_order(order_id)
    except Exception:
        st.error("Order not found")
        return
    line_map = {ln.description: ln.id for ln in order.lines}
    line_label = st.selectbox("Line", options=list(line_map.keys()), key="prj_sub_m_line")
    measured = st.number_input("Measured qty", min_value=0.0, value=0.0, key="prj_sub_m_qty")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(SUB_MEASURE, None)
        st.session_state.pop(SUB_MEASURE_ID, None)
        st.rerun()
    if cols[1].button("Save", type="primary", use_container_width=True):
        H.run_action(
            lambda: sub.record_measurement(order_id, line_map[line_label], measured),
            "Measured",
        )
        st.session_state.pop(SUB_MEASURE, None)
        st.session_state.pop(SUB_MEASURE_ID, None)


@st.dialog(
    "Certify subcontract line",
    on_dismiss=make_dismiss_handler(SUB_CERTIFY, SUB_CERTIFY_ID),
)
def _sub_certify_dialog(services: dict, order_id: str) -> None:
    sub = services["project_subcontract"]
    try:
        order = sub.get_order(order_id)
    except Exception:
        st.error("Order not found")
        return
    line_map = {ln.description: ln.id for ln in order.lines}
    line_label = st.selectbox("Line", options=list(line_map.keys()), key="prj_sub_c_line")
    certified = st.number_input(
        "Certified qty", min_value=0.0, value=0.0, key="prj_sub_c_qty"
    )
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(SUB_CERTIFY, None)
        st.session_state.pop(SUB_CERTIFY_ID, None)
        st.rerun()
    if cols[1].button("Save", type="primary", use_container_width=True):
        H.run_action(
            lambda: sub.certify_line(order_id, line_map[line_label], certified),
            "Certified",
        )
        st.session_state.pop(SUB_CERTIFY, None)
        st.session_state.pop(SUB_CERTIFY_ID, None)


def render_procurement(services: dict, project) -> None:
    svc = services.get("project_procurement")
    if svc is None:
        st.warning("Procurement service is not configured.")
        return
    tab_mr, tab_rfq, tab_stock, tab_sub = st.tabs(
        ["Material requests", "RFQs", "Materials", "Subcontract"]
    )
    with tab_mr:
        if st.button("New MR", key="prj_mr_new"):
            st.session_state[MR_DIALOG] = True
        if st.session_state.get(MR_DIALOG):
            _mr_dialog(services, project)
        for mr in svc.list_material_requests(project.id):
            with st.container(border=True):
                st.write(f"**{mr.request_number}** · {mr.status.value}")
                st.caption(
                    f"{len(mr.lines)} line(s) · invoice={getattr(mr, 'invoice_party', 'Contractor')} "
                    f"· {getattr(mr, 'principal_agent', 'Principal')}"
                )
                if mr.status.value == "Draft" and st.button(
                    "Submit", key=f"mr_sub_{mr.id}"
                ):
                    H.run_action(lambda m=mr: svc.submit_material_request(m.id), "Submitted")
    with tab_rfq:
        for rfq in svc.list_rfqs(project.id):
            po_note = f" · PO {rfq.po_id[:8]}…" if rfq.po_id else ""
            st.write(
                f"**{rfq.rfq_number}** · {rfq.description} · {rfq.status.value}{po_note}"
            )
        st.caption("Create RFQs from approved material requests via procurement service.")
    with tab_stock:
        if st.button("Record movement", key="prj_stock_new"):
            st.session_state[STOCK_DIALOG] = True
        if st.session_state.get(STOCK_DIALOG):
            _stock_dialog(services, project)
        try:
            recon = svc.stock_reconciliation(project.id)
            own = recon.get("by_ownership") or {}
            st.caption(
                "On-hand by ownership: "
                + " · ".join(f"{k}={v}" for k, v in own.items())
            )
        except Exception:
            pass
        for movement in svc.list_stock_movements(project.id):
            st.write(
                f"{movement.movement_type.value}: {movement.description} "
                f"× {movement.quantity} ({movement.ownership.value}"
                f" / {getattr(movement, 'invoice_party', 'Contractor')})"
            )
    with tab_sub:
        sub = services.get("project_subcontract")
        if sub is None:
            st.info("Subcontract service unavailable.")
            return
        if st.button("Create order", key="prj_sub_new"):
            st.session_state[SUB_DIALOG] = True
        if st.session_state.get(SUB_DIALOG):
            _sub_dialog(services, project)
        if st.session_state.get(SUB_MEASURE) and st.session_state.get(SUB_MEASURE_ID):
            _sub_measure_dialog(services, st.session_state[SUB_MEASURE_ID])
        if st.session_state.get(SUB_CERTIFY) and st.session_state.get(SUB_CERTIFY_ID):
            _sub_certify_dialog(services, st.session_state[SUB_CERTIFY_ID])
        orders = sub.list_orders(project.id)
        if not orders:
            H.empty_state("No subcontract orders yet.")
        for order in orders:
            with st.container(border=True):
                st.write(
                    f"**{order.order_number}** · {order.vendor_name} · "
                    f"{order.status.value} · {H.fmt_money(order.contract_value)}"
                )
                btns = st.columns(4)
                if btns[0].button("Activate", key=f"sub_act_{order.id}"):
                    H.run_action(lambda o=order: sub.activate(o.id), "Activated")
                if btns[1].button("Measure", key=f"sub_meas_{order.id}"):
                    st.session_state[SUB_MEASURE] = True
                    st.session_state[SUB_MEASURE_ID] = order.id
                    st.rerun()
                if btns[2].button("Certify", key=f"sub_cert_{order.id}"):
                    st.session_state[SUB_CERTIFY] = True
                    st.session_state[SUB_CERTIFY_ID] = order.id
                    st.rerun()
                if btns[3].button("Settle", key=f"sub_settle_{order.id}"):
                    H.run_action(lambda o=order: sub.settle(o.id), "Settled")
