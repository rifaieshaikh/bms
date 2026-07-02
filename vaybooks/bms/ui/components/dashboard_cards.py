import streamlit as st


def order_action_cards(title: str, orders: list, key_prefix: str):
    st.subheader(title)
    if not orders:
        st.caption("None")
        return

    cols = st.columns(min(len(orders), 3))
    for i, o in enumerate(orders):
        order_id = o.get("id") or o.get("_id")
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{o.get('order_number')}**")
                st.caption(o.get("customer_name", ""))
                etd = o.get("expected_delivery_date")
                if etd:
                    st.write(f"ETD: {etd}")
                status = o.get("order_status", "")
                if status:
                    st.write(f"Status: {status}")
                if st.button("Open", key=f"{key_prefix}_{order_id}"):
                    st.session_state.selected_order_id = order_id
                    st.session_state.navigate_to_orders = True
                    st.rerun()
