import streamlit as st

from vaybooks.bms.domain.orders.bill_status import bill_is_delivered, bill_is_invoiced
from vaybooks.bms.domain.orders.entities import BillNumber, CustomizationOrder
from vaybooks.bms.domain.shared.enums import ExpenseSource
from vaybooks.bms.ui.components.activity_checklist import activity_checklist
from vaybooks.bms.ui.components.time_entry_form import time_entry_form


def _status_badges(bill: BillNumber, order: CustomizationOrder, invoices, deliveries) -> str:
    parts = []
    if order.bill_activities_complete(bill.bill_id):
        parts.append("Activities done")
    else:
        parts.append("Activities pending")
    if bill_is_invoiced(bill.bill_id, invoices):
        parts.append("Invoiced")
    else:
        parts.append("Not invoiced")
    if bill_is_delivered(bill.bill_id, deliveries):
        parts.append("Delivered")
    else:
        parts.append("Not delivered")
    return " · ".join(parts)


def bill_card(
    services: dict,
    order: CustomizationOrder,
    bill: BillNumber,
    invoices: list,
    deliveries: list,
):
    time_service = services["time_tracking"]
    expense_service = services["expenses"]

    with st.container(border=True):
        st.markdown(f"### Bill {bill.bill_number}")
        st.caption(_status_badges(bill, order, invoices, deliveries))
        st.write(f"**Item:** {bill.item_description or '—'}")

        tab_acts, tab_time, tab_exp = st.tabs(["Activities", "Time", "Expenses"])

        with tab_acts:
            activity_checklist(services, order, bill_id=bill.bill_id)

        with tab_time:
            entries = [
                e for e in time_service.get_entries_by_order(order.id)
                if e.bill_id == bill.bill_id
            ]
            if entries:
                for e in entries:
                    st.write(
                        f"{e.activity_name} | {e.work_date} | "
                        f"{e.start_time}-{e.end_time} ({e.duration_minutes} min)"
                    )
            else:
                st.caption("No time entries yet.")

            bill_activities = [
                a for a in order.activities_for_bill(bill.bill_id) if a.is_required
            ]
            if bill_activities:
                act_map = {a.activity_name: a.activity_id for a in bill_activities}
                with st.form(f"time_form_{bill.bill_id}"):
                    act_name = st.selectbox(
                        "Activity", list(act_map.keys()), key=f"time_act_{bill.bill_id}"
                    )
                    form_data = time_entry_form(
                        services,
                        activity_id=act_map.get(act_name),
                        key_prefix=f"time_{bill.bill_id}",
                    )
                    if st.form_submit_button("Record Time"):
                        try:
                            time_service.record_time_entry(
                                order_id=order.id,
                                bill_id=bill.bill_id,
                                activity_id=act_map[act_name],
                                work_date=form_data["work_date"],
                                start_time=form_data["start_time"],
                                end_time=form_data["end_time"],
                                worker_name=form_data["worker_name"],
                                notes=form_data["notes"],
                            )
                            st.success("Time recorded")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

        with tab_exp:
            expenses = expense_service.get_expenses_by_bill(bill.bill_id)
            if expenses:
                for exp in expenses:
                    st.write(
                        f"{exp.expense_name} — Purchase: ₹{exp.total_purchase_price:,.0f} | "
                        f"Selling: ₹{exp.total_selling_price:,.0f}"
                    )
            else:
                st.caption("No expenses yet.")

            with st.form(f"exp_form_{bill.bill_id}"):
                name = st.text_input("Expense Name", key=f"exp_name_{bill.bill_id}")
                source = st.selectbox(
                    "Source",
                    [e.value for e in ExpenseSource],
                    key=f"exp_src_{bill.bill_id}",
                )
                purchase = st.number_input(
                    "Purchase Price", min_value=0.0, key=f"exp_pur_{bill.bill_id}"
                )
                selling = st.number_input(
                    "Selling Price", min_value=0.0, key=f"exp_sel_{bill.bill_id}"
                )
                quantity = st.number_input(
                    "Quantity", min_value=0.01, value=1.0, key=f"exp_qty_{bill.bill_id}"
                )
                vendor = st.text_input(
                    "Vendor / Worker", key=f"exp_vnd_{bill.bill_id}"
                )
                notes = st.text_area("Notes", key=f"exp_notes_{bill.bill_id}")
                if st.form_submit_button("Add Expense"):
                    try:
                        from datetime import date

                        expense_service.add_expense(
                            order_id=order.id,
                            expense_date=date.today(),
                            expense_name=name,
                            expense_source=source,
                            purchase_price=purchase,
                            selling_price=selling,
                            quantity=quantity,
                            bill_id=bill.bill_id,
                            vendor_or_worker_name=vendor,
                            notes=notes,
                        )
                        st.success("Expense added")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
