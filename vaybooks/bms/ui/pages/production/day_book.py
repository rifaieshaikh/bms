from datetime import date

import streamlit as st


def render(services: dict) -> None:
    st.header("Production Day Book")
    service = services.get("production")
    if not service:
        st.error("Production service is unavailable.")
        return
    c1, c2 = st.columns(2)
    start = c1.date_input("From", value=date.today().replace(day=1))
    end = c2.date_input("To", value=date.today())
    if start > end:
        st.error("From date must not be after To date.")
        return
    rows = service.day_book(start, end)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("No production or accounting activity in this period.")
