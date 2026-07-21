"""Costs tab — expenses and allocation."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectExpenseSource
from vaybooks.bms.ui.pages.projects.workspace import helpers as H

SELECTED_EXPENSE = "prj_costs_selected_expense"


def render_costs(services: dict, project) -> None:
    expense_svc = services.get("project_expenses")
    if expense_svc is None:
        st.warning("Expense service is not configured.")
        return

    try:
        expenses = expense_svc.list_by_project(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    total = sum(e.amount for e in expenses)
    by_source: dict[str, float] = {}
    for exp in expenses:
        src = exp.expense_source.value
        by_source[src] = by_source.get(src, 0.0) + exp.amount
    unallocated = sum(e.amount for e in expenses if not e.activity_id)

    cols = st.columns(4)
    cols[0].metric("Total costs", H.fmt_money(total))
    for i, (src, amt) in enumerate(sorted(by_source.items())):
        if i + 1 < len(cols):
            cols[i + 1].metric(src, H.fmt_money(amt))
    if len(by_source) < 3:
        cols[-1].metric("Unallocated", H.fmt_money(unallocated))

    st.subheader("Add expense")
    act_opts = H.activity_tree_options(project, include_blank=True, blank_label="— Unallocated —")
    boq_svc = services.get("project_boq")
    boq_opts: dict[str, str] = {"— None —": ""}
    if boq_svc is not None:
        try:
            for item in boq_svc.list_items(project.id):
                if getattr(item.item_type, "value", "") == "Section":
                    continue
                label = f"{item.code} — {item.description}" if item.code else item.description
                boq_opts[label] = item.id
        except Exception:
            pass
    with st.form("prj_exp_add"):
        expense_date = st.date_input("Date", value=date.today())
        expense_name = st.text_input("Name")
        expense_source = st.selectbox(
            "Source",
            options=[s.value for s in ProjectExpenseSource],
        )
        amount = st.number_input("Amount", min_value=0.01, value=100.0, step=100.0)
        act_labels = list(act_opts.keys())
        activity_label = st.selectbox("Activity", options=act_labels)
        boq_label = st.selectbox("BOQ item (optional)", options=list(boq_opts.keys()))
        vendor_name = st.text_input("Vendor (optional)")
        notes = st.text_input("Notes")
        submitted = st.form_submit_button("Save expense", type="primary")
    if submitted:
        if not expense_name.strip():
            st.error("Name is required")
        else:
            H.run_action(
                lambda: expense_svc.create_expense(
                    project.id,
                    expense_date,
                    expense_name.strip(),
                    expense_source,
                    amount,
                    activity_id=act_opts[activity_label],
                    boq_item_id=boq_opts.get(boq_label, ""),
                    vendor_name=vendor_name,
                    notes=notes,
                ),
                "Expense saved",
            )

    selected_id = st.session_state.get(SELECTED_EXPENSE)
    if selected_id:
        expense = expense_svc.get_expense(selected_id)
        if expense:
            st.subheader(f"Edit expense · {expense.expense_name}")
            id_to_label = {v: k for k, v in act_opts.items()}
            cur_label = id_to_label.get(expense.activity_id, "— Unallocated —")
            boq_id_to_label = {v: k for k, v in boq_opts.items()}
            cur_boq = boq_id_to_label.get(expense.boq_item_id or "", "— None —")
            with st.form(f"prj_exp_edit_{selected_id}"):
                edit_date = st.date_input("Date", value=expense.expense_date)
                edit_name = st.text_input("Name", value=expense.expense_name)
                edit_source = st.selectbox(
                    "Source",
                    options=[s.value for s in ProjectExpenseSource],
                    index=[s.value for s in ProjectExpenseSource].index(
                        expense.expense_source.value
                    ),
                )
                edit_amount = st.number_input(
                    "Amount",
                    min_value=0.01,
                    value=float(expense.amount),
                    step=100.0,
                )
                labels = list(act_opts.keys())
                edit_act = st.selectbox(
                    "Activity",
                    options=labels,
                    index=labels.index(cur_label) if cur_label in labels else 0,
                )
                boq_labels = list(boq_opts.keys())
                edit_boq = st.selectbox(
                    "BOQ item (optional)",
                    options=boq_labels,
                    index=boq_labels.index(cur_boq) if cur_boq in boq_labels else 0,
                )
                edit_vendor = st.text_input("Vendor", value=expense.vendor_name or "")
                edit_notes = st.text_input("Notes", value=expense.notes or "")
                c1, c2 = st.columns(2)
                save = c1.form_submit_button("Save changes", type="primary")
                cancel = c2.form_submit_button("Cancel edit")
            if cancel:
                st.session_state.pop(SELECTED_EXPENSE, None)
                st.rerun()
            if save:
                H.run_action(
                    lambda: expense_svc.update_expense(
                        selected_id,
                        edit_date,
                        edit_name.strip(),
                        edit_source,
                        edit_amount,
                        activity_id=act_opts[edit_act],
                        boq_item_id=boq_opts.get(edit_boq, ""),
                        vendor_name=edit_vendor,
                        notes=edit_notes,
                    ),
                    "Expense updated",
                )
                st.session_state.pop(SELECTED_EXPENSE, None)

    st.divider()
    st.subheader("Register")
    if not expenses:
        H.empty_state("No expenses yet.")
    else:
        for exp in sorted(expenses, key=lambda e: e.expense_date, reverse=True):
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                c1.write(
                    f"**{exp.expense_name}** · {exp.expense_date} · "
                    f"{exp.expense_source.value} · {H.fmt_money(exp.amount)}"
                )
                c1.caption(
                    f"Activity: {H.activity_label(project, exp.activity_id) if exp.activity_id else 'Unallocated'}"
                    f"{(' · ' + exp.vendor_name) if exp.vendor_name else ''}"
                )
                if c2.button("Edit", key=f"prj_exp_edit_btn_{exp.id}"):
                    st.session_state[SELECTED_EXPENSE] = exp.id
                    st.rerun()
                if c3.button("Delete", key=f"prj_exp_del_{exp.id}"):
                    H.run_action(
                        lambda eid=exp.id: expense_svc.delete_expense(eid),
                        "Expense deleted",
                    )

    with st.expander("Costs by activity", expanded=False):
        by_activity: dict[str | None, float] = {}
        for exp in expenses:
            by_activity[exp.activity_id] = by_activity.get(exp.activity_id, 0.0) + exp.amount

        labour_by_activity: dict[str | None, float] = {}
        profitability = services.get("projects_profitability")
        if profitability is not None:
            try:
                summary = profitability.get_project_profitability(project.id)
                for row in summary.activity_rows:
                    labour_by_activity[row.activity_id] = row.labour_cost
            except Exception:
                pass

        activity_ids = set(by_activity.keys()) | set(labour_by_activity.keys())
        activity_ids.discard(None)
        if not activity_ids and not by_activity.get(None):
            st.caption("No activity costs yet.")
        else:
            table_rows = []
            if by_activity.get(None):
                table_rows.append(
                    {
                        "Activity": "— Unallocated —",
                        "Expenses": by_activity[None],
                        "Labour": labour_by_activity.get(None, 0.0),
                    }
                )
            for aid in sorted(activity_ids, key=lambda x: H.activity_label(project, x)):
                table_rows.append(
                    {
                        "Activity": H.activity_label(project, aid),
                        "Expenses": by_activity.get(aid, 0.0),
                        "Labour": labour_by_activity.get(aid, 0.0),
                    }
                )
            st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
