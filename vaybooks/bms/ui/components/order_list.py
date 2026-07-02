import pandas as pd
import streamlit as st

from vaybooks.bms.domain.orders.entities import CustomizationOrder


def order_list_table(orders: list[CustomizationOrder], key_prefix: str = "ord"):
    if not orders:
        st.info("No orders found.")
        return

    rows = []
    for o in orders:
        rows.append(
            {
                "Order": o.order_number,
                "Customer": o.customer_name,
                "Phone": o.phone_number,
                "Status": o.order_status.value,
                "ETD": o.expected_delivery_date,
                "Bills": len(o.bill_numbers),
                "_id": o.id,
            }
        )

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_id"])
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    options = {f"{r['Order']} — {r['Customer']}": r["_id"] for r in rows}
    choice = st.selectbox("Open order", ["—"] + list(options.keys()), key=f"{key_prefix}_sel")
    if choice != "—":
        st.session_state.selected_order_id = options[choice]
