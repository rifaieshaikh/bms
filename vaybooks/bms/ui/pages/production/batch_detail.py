from __future__ import annotations

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.production.entities import BatchCost
from vaybooks.bms.domain.shared.enums import ProductionBatchStatus, ProductionOutputRole
from vaybooks.bms.ui import navigation


def _save_grid(service, batch, issue_df, output_df) -> None:
    issue_rows = issue_df.to_dict("records")
    for line, row in zip(batch.issues, issue_rows):
        line.qty = float(row.get("Quantity") or 0)
        line.location_id = str(row.get("Location") or batch.location_id)
    output_rows = output_df.to_dict("records")
    for line, row in zip(batch.outputs, output_rows):
        line.qty = float(row.get("Quantity") or 0)
        line.nrv_rate = float(row.get("NRV rate") or 0)
        line.allocation_pct = float(row.get("Allocation %") or 0)
        line.location_id = str(row.get("Location") or batch.location_id)
    service.save_batch(batch)


def render(services: dict) -> None:
    service = services.get("production")
    accounting = services.get("accounting")
    if not service:
        st.error("Production service is unavailable.")
        return
    batch_id = navigation.current_detail_id("production_batch_detail")
    batch = service.get_batch(batch_id or "")
    if not batch:
        st.error("Production batch not found.")
        return
    if st.button("← Back to batches"):
        navigation.go_to_list("production_batches")
    st.header(batch.batch_number)
    st.caption(
        f"{batch.recipe_name} · {batch.batch_date:%d %b %Y} · {batch.status.value}"
    )

    editable = batch.is_editable
    tabs = st.tabs(["Activities", "Materials & outputs", "Expenses", "Cost sheet"])
    with tabs[0]:
        if not batch.stages:
            st.info("This recipe has no configured activities.")
        for stage in sorted(batch.stages, key=lambda item: item.sequence):
            checked = st.checkbox(
                stage.name,
                value=stage.completed,
                disabled=not editable or stage.completed,
                key=f"batch_stage_{stage.id}",
            )
            if checked and not stage.completed:
                service.complete_stage(batch.id, stage.id)
                st.rerun()
            if stage.notes:
                st.caption(stage.notes)

    with tabs[1]:
        st.markdown("**Raw materials issued**")
        issue_df = st.data_editor(
            pd.DataFrame(
                [
                    {
                        "Product": line.product_name,
                        "Quantity": line.qty,
                        "Unit": line.unit,
                        "Unit cost": line.unit_cost,
                        "Location": line.location_id or batch.location_id,
                    }
                    for line in batch.issues
                ]
            ),
            disabled=["Product", "Unit", "Unit cost"],
            width="stretch",
            key=f"batch_issues_{batch.id}",
        )
        st.markdown("**Outputs received**")
        output_df = st.data_editor(
            pd.DataFrame(
                [
                    {
                        "Product": line.product_name,
                        "Quantity": line.qty,
                        "Unit": line.unit,
                        "Role": line.role.value,
                        "NRV rate": line.nrv_rate,
                        "Allocation %": line.allocation_pct,
                        "Location": line.location_id or batch.location_id,
                    }
                    for line in batch.outputs
                ]
            ),
            disabled=["Product", "Unit", "Role"],
            width="stretch",
            key=f"batch_outputs_{batch.id}",
        )
        if editable and st.button("Save quantities and rates", type="primary"):
            try:
                _save_grid(service, batch, issue_df, output_df)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with tabs[2]:
        for cost in batch.costs:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(cost.cost_type)
            c1.caption(cost.description or "No description")
            c2.write(f"₹{cost.amount:,.2f}")
            if editable and c3.button("Remove", key=f"remove_cost_{cost.id}"):
                service.remove_cost(batch.id, cost.id)
                st.rerun()
        if editable:
            with st.form(f"batch_cost_form_{batch.id}", clear_on_submit=True):
                c1, c2 = st.columns(2)
                cost_type = c1.selectbox(
                    "Expense type",
                    ["Labour", "Power", "Fuel", "Packing", "Freight", "Overhead", "Other"],
                )
                amount = c2.number_input("Amount", min_value=0.0)
                stage_options = {"Not activity-specific": ""}
                stage_options.update({stage.name: stage.id for stage in batch.stages})
                stage_label = st.selectbox("Activity", list(stage_options))
                account_options = {"Use default expense clearing": ""}
                if accounting:
                    account_options.update(
                        {
                            account.account_name: account.id
                            for account in accounting.list_accounts(active_only=True)
                        }
                    )
                account_label = st.selectbox("Cost / clearing account", list(account_options))
                description = st.text_input("Description")
                if st.form_submit_button("Add expense", type="primary"):
                    try:
                        service.add_cost(
                            batch.id,
                            BatchCost(
                                cost_type=cost_type,
                                amount=float(amount),
                                activity_id=stage_options[stage_label],
                                account_id=account_options[account_label],
                                description=description,
                            ),
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    with tabs[3]:
        batch = service.get_batch(batch.id) or batch
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Material cost", f"₹{batch.material_cost:,.2f}")
        c2.metric("Expenses", f"₹{batch.expense_cost:,.2f}")
        c3.metric("Total cost", f"₹{batch.total_cost:,.2f}")
        c4.metric("Batch margin", f"₹{batch.batch_margin:,.2f}")
        st.dataframe(
            [
                {
                    "Output": output.product_name,
                    "Role": (
                        output.role.value
                        if isinstance(output.role, ProductionOutputRole)
                        else output.role
                    ),
                    "Quantity": output.qty,
                    "Allocated cost": output.allocated_cost,
                    "Cost / unit": output.unit_cost,
                    "Expected value": output.qty * output.nrv_rate,
                }
                for output in batch.outputs
            ],
            width="stretch",
            hide_index=True,
        )
        if batch.status != ProductionBatchStatus.POSTED:
            st.warning(
                "Posting issues raw materials, receives outputs, updates output WAC, "
                "and creates balanced production journals."
            )
            if st.button("Post production batch", type="primary", disabled=not editable):
                try:
                    service.post_batch(batch.id)
                    st.success("Batch posted.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        else:
            st.success(
                f"Posted with {len(batch.posting.movement_ids)} stock movements and "
                f"{len(batch.posting.voucher_ids)} vouchers."
            )
