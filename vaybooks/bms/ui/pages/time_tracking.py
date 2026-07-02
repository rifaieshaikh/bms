import streamlit as st

from vaybooks.bms.ui.components.bill_selector import bill_selector
from vaybooks.bms.ui.components.order_selector import order_selector
from vaybooks.bms.ui.components.time_entry_form import time_entry_form


def render(services: dict):
    st.title("Time Tracking")
    time_service = services["time_tracking"]
    order_service = services["orders"]
    activity_service = services["activities"]

    tab1, tab2 = st.tabs(["Record Time", "View / Search"])

    with tab1:
        order_id = order_selector(services, "time_ord")
        if order_id:
            order = order_service.get_order_detail(order_id)
            bill_id = bill_selector(order, "time_bill")
            activities = [
                a for a in order.order_activities if a.is_required
            ]
            act_options = {a.activity_name: a.activity_id for a in activities}
            act_name = st.selectbox("Activity", list(act_options.keys()))
            activity_id = act_options[act_name]

            form = time_entry_form("record_time")
            if st.button("Save Time Entry"):
                try:
                    time_service.record_time_entry(
                        order_id=order_id,
                        bill_id=bill_id,
                        activity_id=activity_id,
                        work_date=form["work_date"],
                        start_time=form["start_time"],
                        end_time=form["end_time"],
                        worker_name=form["worker_name"],
                        notes=form["notes"],
                    )
                    st.success("Time entry saved")
                except Exception as e:
                    st.error(str(e))

    with tab2:
        bill_search = st.text_input("Search by Bill Number")
        if bill_search:
            entries = time_service.get_entries_by_bill(bill_search)
        else:
            entries = time_service.list_all()

        for e in entries:
            st.write(
                f"{e.order_number} | {e.bill_number} | {e.activity_name} | "
                f"{e.work_date} | {e.start_time}-{e.end_time} | {e.duration_minutes} min"
            )

        summary = time_service.get_summary()
        st.subheader("Totals")
        st.write(f"Total Stitching: {summary['total_stitching_hours']} hours")
        st.write(f"Total Hand Work: {summary['total_hand_work_hours']} hours")
        if summary["by_bill"]:
            st.write("**By Bill Number:**")
            for bill, mins in summary["by_bill"].items():
                st.write(f"- {bill}: {mins / 60:.2f} hours")
        if summary["by_activity"]:
            st.write("**By Activity:**")
            for act, mins in summary["by_activity"].items():
                st.write(f"- {act}: {mins / 60:.2f} hours")
