"""Billing tab — quotations, work orders, invoices, RA, proforma, variations."""

from __future__ import annotations

from datetime import date
from typing import Callable

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import (
    ProjectQuotationStatus,
    ProjectRABillStatus,
    ProjectVariationStatus,
    VoucherType,
)
from vaybooks.bms.ui.pages.projects.workspace import helpers as H


def _store_account_options(services: dict) -> dict[str, str]:
    try:
        accounts = services["accounting"].get_store_accounts()
    except Exception:
        return {}
    return {a.account_name: a.id for a in accounts}


def render_billing(services: dict, project) -> None:
    subtab = st.session_state.get(H.BILLING_SUBTAB, H.BILLING_SUBTABS[0])
    if subtab not in H.BILLING_SUBTABS:
        subtab = H.BILLING_SUBTABS[0]
    picked = st.radio(
        "Billing",
        options=H.BILLING_SUBTABS,
        index=H.BILLING_SUBTABS.index(subtab),
        horizontal=True,
        key="prj_billing_subnav",
        label_visibility="collapsed",
    )
    st.session_state[H.BILLING_SUBTAB] = picked

    if picked == "Quotations":
        _render_quotations(services, project)
    elif picked == "Work Orders":
        _render_work_orders(services, project)
    elif picked == "Measurements":
        _render_measurements(services, project)
    elif picked == "Tax Invoices":
        _render_tax_invoices(services, project)
    elif picked == "RA Bills":
        _render_ra_bills(services, project)
    elif picked == "Proforma":
        _render_proforma(services, project)
    elif picked == "Variations":
        _render_variations(services, project)


def _render_quotations(services: dict, project) -> None:
    quote_svc = services.get("project_quotations")
    if quote_svc is None:
        st.warning("Quotation service is not configured.")
        return

    try:
        quotations = quote_svc.list_by_project(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    if quotations:
        reg_rows = [
            {
                "Number": q.quotation_number,
                "Date": q.quotation_date,
                "Status": q.status.value,
                "Subtotal": q.subtotal,
                "Rev": q.revision_no,
            }
            for q in sorted(quotations, key=lambda x: x.quotation_date, reverse=True)
        ]
        st.dataframe(pd.DataFrame(reg_rows), use_container_width=True, hide_index=True)

    st.subheader("Create quotation")
    notes = st.text_input("Notes", key="prj_q_new_notes")
    q_cols = st.columns(3)
    if q_cols[0].button("Load from phases", type="primary", key="prj_q_load_phases"):
        lines = quote_svc.default_lines_from_phases(project.id)
        H.reset_line_editor("prj_q_new", lines)
        st.rerun()
    if q_cols[1].button("Load defaults from activities", key="prj_q_load_defaults"):
        lines = quote_svc.default_lines_from_activities(project.id)
        H.reset_line_editor("prj_q_new", lines)
        st.rerun()
    if q_cols[2].button("Load from BOQ", key="prj_q_load_boq"):
        try:
            lines = quote_svc.default_lines_from_boq(project.id)
            H.reset_line_editor("prj_q_new", lines)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    lines = H.dynamic_line_editor("prj_q_new", project=project)
    if st.button("Create quotation", type="primary", key="prj_q_create"):
        H.run_action(
            lambda: quote_svc.create_quotation(project.id, lines=lines, notes=notes),
            "Quotation created",
        )

    if not quotations:
        H.empty_state("No quotations yet.")
        return

    st.divider()
    for quotation in sorted(quotations, key=lambda q: q.quotation_date, reverse=True):
        with st.container(border=True):
            st.write(
                f"**{quotation.quotation_number}** · {quotation.quotation_date} · "
            )
            H.render_badge(quotation.status.value)
            st.caption(
                f"Subtotal {H.fmt_money(quotation.subtotal)} · rev {quotation.revision_no}"
            )
            if quotation.lines:
                line_rows = [
                    {
                        "Description": ln.description,
                        "Qty": ln.quantity,
                        "Rate": (
                            "—"
                            if getattr(ln, "hide_rate", False)
                            or (float(ln.rate or 0) == 0 and ln.boq_item_id)
                            else ln.rate
                        ),
                        "Total": ln.line_total,
                    }
                    for ln in quotation.lines
                ]
                st.dataframe(
                    pd.DataFrame(line_rows),
                    use_container_width=True,
                    hide_index=True,
                )

            status = quotation.status.value
            qid = quotation.id
            actions: list[tuple[str, Callable | None]] = []

            if status == ProjectQuotationStatus.DRAFT.value:
                actions = [
                    ("Submit", lambda q=quotation: quote_svc.submit_for_approval(q.id)),
                    ("Cancel", lambda q=quotation: quote_svc.cancel_quotation(q.id)),
                ]
            elif status == ProjectQuotationStatus.PENDING_APPROVAL.value:
                actions = [
                    ("Approve", lambda q=quotation: quote_svc.approve_quotation(q.id)),
                    ("Request changes", lambda q=quotation: quote_svc.request_changes(q.id)),
                ]
            elif status == ProjectQuotationStatus.APPROVED.value:
                actions = [
                    ("Send", lambda q=quotation: quote_svc.send_quotation(q.id)),
                    ("Revise", lambda q=quotation: quote_svc.revise_quotation(q.id)),
                    ("PDF", None),
                ]
            elif status == ProjectQuotationStatus.SENT.value:
                actions = [
                    ("Accept", lambda q=quotation: quote_svc.accept_quotation(q.id)),
                    ("Reject", lambda q=quotation: quote_svc.reject_quotation(q.id)),
                    ("Revise", lambda q=quotation: quote_svc.revise_quotation(q.id)),
                    ("PDF", None),
                ]
            elif status == ProjectQuotationStatus.ACCEPTED.value:
                set_cv = st.checkbox(
                    "Set contract value from quotation",
                    value=True,
                    key=f"prj_q_set_cv_{qid}",
                )
                create_wo = st.checkbox(
                    "Create work order",
                    value=True,
                    key=f"prj_q_create_wo_{qid}",
                )
                actions = [
                    (
                        "Convert",
                        lambda q=quotation, sc=set_cv, cw=create_wo: quote_svc.convert_to_project(
                            q.id,
                            set_contract_value=sc,
                            create_work_order=cw,
                        ),
                    ),
                    ("PDF", None),
                ]
            else:
                actions = [("PDF", None)]

            if actions:
                cols = st.columns(len(actions))
                for i, (label, cb) in enumerate(actions):
                    if label == "PDF":
                        if cols[i].button("PDF", key=f"q_pdf_btn_{qid}"):
                            try:
                                st.session_state[f"prj_q_pdf_{qid}"] = quote_svc.generate_pdf(qid)
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                        pdf_key = f"prj_q_pdf_{qid}"
                        if pdf_key in st.session_state:
                            cols[i].download_button(
                                "Download PDF",
                                data=st.session_state[pdf_key],
                                file_name=f"{quotation.quotation_number}.pdf",
                                mime="application/pdf",
                                key=f"q_pdf_dl_{qid}",
                            )
                    elif cols[i].button(label, key=f"q_act_{qid}_{label}"):
                        H.run_action(cb, label)

            if status == ProjectQuotationStatus.DRAFT.value:
                with st.expander("Edit draft lines", expanded=False):
                    init = [
                        {
                            "description": ln.description,
                            "quantity": ln.quantity,
                            "rate": ln.rate,
                            "discount_pct": ln.discount_pct,
                            "hsn_sac": ln.hsn_sac,
                            "activity_id": ln.activity_id,
                        }
                        for ln in quotation.lines
                    ]
                    if f"prj_q_edit_{qid}_lines" not in st.session_state:
                        H.reset_line_editor(f"prj_q_edit_{qid}", init)
                    edit_lines = H.dynamic_line_editor(f"prj_q_edit_{qid}", project=project)
                    if st.button("Update quotation", key=f"prj_q_update_{qid}"):
                        H.run_action(
                            lambda q=quotation, ln=edit_lines: quote_svc.update_quotation(
                                q.id, lines=ln
                            ),
                            "Quotation updated",
                        )


def _render_work_orders(services: dict, project) -> None:
    billing_svc = services.get("project_billing")
    if billing_svc is None:
        st.warning("Billing service is not configured.")
        return

    st.subheader("Create work order")
    description = st.text_input("Description", key="prj_wo_desc")
    if st.button("Create work order", type="primary", key="prj_wo_create"):
        H.run_action(
            lambda: billing_svc.create_work_order(project.id, description=description),
            "Work order created",
        )

    try:
        work_orders = billing_svc.list_work_orders(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    if not work_orders:
        H.empty_state("No work orders yet.")
        return

    rows = [
        {
            "Number": wo.wo_number,
            "Date": wo.wo_date,
            "Status": wo.status,
            "Description": wo.description or "—",
        }
        for wo in work_orders
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_tax_invoices(services: dict, project) -> None:
    billing_svc = services.get("project_billing")
    report_svc = services.get("reports_projects")
    if billing_svc is None:
        st.warning("Billing service is not configured.")
        return

    if report_svc is not None:
        try:
            register = report_svc.billing_register(project.id)
            inv_rows = [
                r
                for r in register.get("rows") or []
                if r.get("voucher_type") == VoucherType.SALES_INVOICE.value
            ]
            if inv_rows:
                st.subheader("Register")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Number": r["voucher_number"],
                                "Date": r["voucher_date"],
                                "Net": r["net"],
                                "Collected": r["collected"],
                                "Outstanding": r["outstanding"],
                            }
                            for r in inv_rows
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        except Exception as exc:
            st.caption(str(exc))

    store_opts = _store_account_options(services)
    st.subheader("Create tax invoice")
    if not store_opts:
        st.warning("Configure at least one store/cash/bank account.")
    line_items = H.dynamic_line_editor("prj_inv_create", project=project)
    store_label = st.selectbox(
        "Store account",
        options=list(store_opts.keys()) if store_opts else [""],
        key="prj_inv_store",
    )
    amount_received = st.number_input(
        "Amount received",
        min_value=0.0,
        value=0.0,
        step=100.0,
        key="prj_inv_received",
    )
    confirm_over = st.checkbox("Confirm over contract", key="prj_inv_over_contract")
    if st.button("Create tax invoice", type="primary", key="prj_inv_create_btn"):
        if not store_opts:
            st.error("Store account is required")
        elif not line_items:
            st.error("Add at least one line item")
        else:
            H.run_action(
                lambda: billing_svc.create_tax_invoice(
                    project.id,
                    line_items=line_items,
                    store_account_id=store_opts[store_label],
                    amount_received=amount_received,
                    confirm_over_contract=confirm_over,
                ),
                "Tax invoice created",
            )


def _render_measurements(services: dict, project) -> None:
    meas_svc = services.get("project_measurement")
    boq_svc = services.get("project_boq")
    if meas_svc is None:
        st.warning("Measurement service is not configured.")
        return

    try:
        measurements = meas_svc.list_by_project(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    boq_labels: dict[str, str] = {}
    boq_opts: dict[str, str] = {}
    if boq_svc:
        try:
            for item in boq_svc.list_items(project.id):
                if item.item_type.value == "Item":
                    label = f"{item.code} — {item.description}"
                    boq_labels[item.id] = label
                    boq_opts[label] = item.id
        except Exception:
            pass

    if measurements:
        rows = []
        for m in sorted(measurements, key=lambda x: x.measurement_date, reverse=True):
            rows.append(
                {
                    "Date": m.measurement_date,
                    "BOQ": boq_labels.get(m.boq_item_id, m.boq_item_id[:8]),
                    "Qty": m.quantity,
                    "Cumulative": m.cumulative_quantity,
                    "Location": m.location or "—",
                    "Status": m.status.value,
                    "RA": m.ra_bill_id[:8] if m.ra_bill_id else "—",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("Create measurement")
    if not boq_opts:
        st.info("Add BOQ line items before recording measurements.")
    else:
        boq_label = st.selectbox("BOQ item", options=list(boq_opts.keys()), key="prj_meas_boq")
        m_date = st.date_input("Date", value=date.today(), key="prj_meas_date")
        qty = st.number_input("Quantity", min_value=0.01, value=1.0, key="prj_meas_qty")
        location = st.text_input("Location", key="prj_meas_loc")
        dimensions = st.text_input("Dimensions", key="prj_meas_dim")
        if st.button("Create measurement", type="primary", key="prj_meas_create"):
            H.run_action(
                lambda: meas_svc.create(
                    project.id,
                    boq_opts[boq_label],
                    m_date,
                    qty,
                    location=location,
                    dimensions=dimensions,
                ),
                "Measurement created",
            )

    if not measurements:
        H.empty_state("No measurements yet.")
        return

    st.divider()
    for measurement in sorted(measurements, key=lambda m: m.measurement_date, reverse=True):
        with st.container(border=True):
            st.write(
                f"**{measurement.measurement_date}** · "
                f"{boq_labels.get(measurement.boq_item_id, measurement.boq_item_id)} · "
                f"qty {measurement.quantity} · "
            )
            H.render_badge(measurement.status.value)
            if measurement.location:
                st.caption(f"Location: {measurement.location}")
            if measurement.dimensions:
                st.caption(f"Dimensions: {measurement.dimensions}")
            if measurement.ra_bill_id:
                st.caption(f"Linked RA: {measurement.ra_bill_id[:12]}…")

            status = measurement.status.value
            mid = measurement.id
            cols = st.columns(4)
            if status == "Draft" and cols[0].button("Submit", key=f"meas_submit_{mid}"):
                H.run_action(
                    lambda m=measurement: meas_svc.submit(m.id),
                    "Submitted",
                )
            if status == "Submitted" and cols[1].button("Verify", key=f"meas_verify_{mid}"):
                H.run_action(
                    lambda m=measurement: meas_svc.verify(m.id),
                    "Verified",
                )
            if status in ("Submitted", "Engineer Verified") and cols[2].button(
                "Certify", key=f"meas_certify_{mid}"
            ):
                H.run_action(
                    lambda m=measurement: meas_svc.certify(m.id),
                    "Certified",
                )


def _render_ra_bills(services: dict, project) -> None:
    billing_svc = services.get("project_billing")
    meas_svc = services.get("project_measurement")
    if billing_svc is None:
        st.warning("Billing service is not configured.")
        return

    store_opts = _store_account_options(services)

    st.subheader("Create RA from measurements")
    eligible = []
    if meas_svc is not None:
        try:
            eligible = meas_svc.eligible_for_ra(project.id)
        except Exception:
            pass

    if eligible:
        boq_svc = services.get("project_boq")
        boq_labels: dict[str, str] = {}
        if boq_svc:
            try:
                for item in boq_svc.list_items(project.id):
                    boq_labels[item.id] = f"{item.code} — {item.description}"
            except Exception:
                pass
        meas_options = {
            f"{m.measurement_date} · {boq_labels.get(m.boq_item_id, m.boq_item_id[:8])} · qty {m.quantity}": m.id
            for m in eligible
        }
        selected_labels = st.multiselect(
            "Eligible measurements",
            options=list(meas_options.keys()),
            key="prj_ra_meas_pick",
        )
        ra_desc = st.text_input("Description", key="prj_ra_desc")
        retention_pct = st.number_input(
            "Retention %",
            min_value=0.0,
            max_value=100.0,
            value=float(project.retention_pct or 0),
            key="prj_ra_retention",
        )
        if st.button("Create RA bill", type="primary", key="prj_ra_create"):
            ids = [meas_options[lbl] for lbl in selected_labels]
            if not ids:
                st.error("Select at least one measurement")
            else:
                H.run_action(
                    lambda: billing_svc.create_ra_from_measurements(
                        project.id,
                        ids,
                        description=ra_desc,
                        retention_pct=retention_pct,
                    ),
                    "RA bill created",
                )
    else:
        st.caption("No eligible measurements (submit/verify/certify measurements first).")

    try:
        ra_bills = billing_svc.list_ra_bills(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    if ra_bills:
        reg_rows = []
        for ra in sorted(ra_bills, key=lambda r: r.ra_date, reverse=True):
            ra_status = ra.status.value if hasattr(ra.status, "value") else ra.status
            reg_rows.append(
                {
                    "Number": ra.ra_number,
                    "Date": ra.ra_date,
                    "Status": ra_status,
                    "Claimed": ra.gross_claimed,
                    "Certified": ra.gross_certified,
                    "Invoiced": ra_status == ProjectRABillStatus.INVOICED.value,
                }
            )
        st.subheader("RA register")
        st.dataframe(pd.DataFrame(reg_rows), use_container_width=True, hide_index=True)

    if not ra_bills:
        H.empty_state("No RA bills yet.")
        return

    for ra in sorted(ra_bills, key=lambda r: r.ra_date, reverse=True):
        with st.container(border=True):
            ra_status = ra.status.value if hasattr(ra.status, "value") else ra.status
            st.write(
                f"**{ra.ra_number}** · {ra.ra_date} · "
            )
            H.render_badge(ra_status)
            st.caption(
                f"Claimed {H.fmt_money(ra.gross_claimed)} · "
                f"Certified {H.fmt_money(ra.gross_certified)} · "
                f"Net certified {H.fmt_money(ra.net_certified)}"
            )
            if ra.lines:
                line_rows = [
                    {
                        "Description": ln.description,
                        "Claimed qty": ln.current_claimed_qty,
                        "Certified qty": ln.current_certified_qty,
                        "Rate": ln.rate,
                        "Claimed": ln.claimed_value,
                        "Certified": ln.certified_value,
                    }
                    for ln in ra.lines
                ]
                st.dataframe(
                    pd.DataFrame(line_rows),
                    use_container_width=True,
                    hide_index=True,
                )

            cols = st.columns(4)
            if ra_status == ProjectRABillStatus.DRAFT.value:
                if cols[0].button("Submit", key=f"ra_submit_{ra.id}"):
                    H.run_action(
                        lambda r=ra: billing_svc.submit_ra(r.id),
                        "RA submitted",
                    )
                if cols[1].button("Mark claimed", key=f"ra_claim_{ra.id}"):
                    H.run_action(
                        lambda r=ra: billing_svc.mark_claimed(r.id),
                        "Marked claimed",
                    )
            if ra_status in (
                ProjectRABillStatus.DRAFT.value,
                ProjectRABillStatus.SUBMITTED.value,
                ProjectRABillStatus.CLAIMED.value,
            ):
                with st.expander("Certify lines", expanded=False):
                    cert_inputs = []
                    for ln in ra.lines:
                        qty = st.number_input(
                            f"Certify qty · {ln.description or ln.boq_item_id[:8]}",
                            min_value=0.0,
                            max_value=float(ln.current_claimed_qty),
                            value=float(ln.current_claimed_qty),
                            key=f"ra_cert_qty_{ra.id}_{ln.id}",
                        )
                        cert_inputs.append(
                            {"line_id": ln.id, "current_certified_qty": qty}
                        )
                    if st.button("Certify", key=f"ra_certify_{ra.id}"):
                        H.run_action(
                            lambda r=ra, ci=cert_inputs: billing_svc.certify_ra(
                                r.id, ci
                            ),
                            "RA certified",
                        )

            if ra_status in (
                ProjectRABillStatus.CERTIFIED.value,
                ProjectRABillStatus.PARTIALLY_CERTIFIED.value,
            ):
                if store_opts:
                    store_label = cols[2].selectbox(
                        "Store account",
                        options=list(store_opts.keys()),
                        key=f"ra_store_{ra.id}",
                    )
                    if cols[3].button("Convert to invoice", key=f"ra_convert_{ra.id}"):
                        H.run_action(
                            lambda r=ra, s=store_label: billing_svc.convert_ra_to_invoice(
                                r.id,
                                store_account_id=store_opts[s],
                            ),
                            "RA converted to invoice",
                        )
                else:
                    cols[2].caption("Configure store accounts to convert.")


def _render_proforma(services: dict, project) -> None:
    billing_svc = services.get("project_billing")
    if billing_svc is None:
        st.warning("Billing service is not configured.")
        return

    st.subheader("Create proforma")
    description = st.text_input("Description", key="prj_pf_desc")
    lines = H.dynamic_line_editor("prj_pf_create", project=project)
    if st.button("Create proforma", type="primary", key="prj_pf_create"):
        H.run_action(
            lambda: billing_svc.create_proforma(
                project.id,
                description=description,
                lines=lines,
            ),
            "Proforma created",
        )

    try:
        proformas = billing_svc.list_proformas(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    if not proformas:
        H.empty_state("No proformas yet.")
        return

    rows = [
        {
            "Number": pf.proforma_number,
            "Date": pf.proforma_date,
            "Status": pf.status,
            "Amount": pf.amount,
            "Description": pf.description or "—",
        }
        for pf in proformas
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_variations(services: dict, project) -> None:
    billing_svc = services.get("project_billing")
    if billing_svc is None:
        st.warning("Billing service is not configured.")
        return

    st.subheader("Create variation")
    new_value = st.number_input(
        "New contract value",
        min_value=0.0,
        value=float(project.contract_value),
        step=1000.0,
        key="prj_var_value",
    )
    reason = st.text_input("Reason", key="prj_var_reason")
    if st.button("Create variation", type="primary", key="prj_var_create"):
        H.run_action(
            lambda: billing_svc.create_variation(
                project.id,
                new_contract_value=new_value,
                reason=reason,
            ),
            "Variation created",
        )

    try:
        variations = billing_svc.list_variations(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    if not variations:
        H.empty_state("No variations yet.")
        return

    for variation in sorted(variations, key=lambda v: v.variation_date, reverse=True):
        with st.container(border=True):
            st.write(
                f"**{variation.variation_number}** · {variation.variation_date} · "
                f"{variation.status} · {H.fmt_money(variation.old_contract_value)} → "
                f"{H.fmt_money(variation.new_contract_value)}"
            )
            st.caption(variation.reason)
            if (
                variation.status == ProjectVariationStatus.DRAFT.value
                and st.button("Approve", key=f"var_approve_{variation.id}")
            ):
                H.run_action(
                    lambda v=variation: billing_svc.approve_variation(v.id),
                    "Variation approved",
                )
