import streamlit as st


def measurement_form(key_prefix: str = "meas"):
    st.subheader("Measurements")
    if f"{key_prefix}_rows" not in st.session_state:
        st.session_state[f"{key_prefix}_rows"] = [{"name": "", "value": "", "unit": "inch"}]

    rows = st.session_state[f"{key_prefix}_rows"]
    measurements = []

    for i, row in enumerate(rows):
        cols = st.columns([2, 2, 1, 2])
        row["name"] = cols[0].text_input("Name", value=row["name"], key=f"{key_prefix}_n_{i}")
        row["value"] = cols[1].text_input("Value", value=row["value"], key=f"{key_prefix}_v_{i}")
        row["unit"] = cols[2].text_input("Unit", value=row["unit"], key=f"{key_prefix}_u_{i}")
        row["notes"] = cols[3].text_input("Notes", value=row.get("notes", ""), key=f"{key_prefix}_no_{i}")
        if row["name"] and row["value"]:
            measurements.append(
                {
                    "measurement_name": row["name"],
                    "measurement_value": row["value"],
                    "unit": row["unit"],
                    "notes": row.get("notes", ""),
                }
            )

    if st.button("Add measurement row", key=f"{key_prefix}_add"):
        rows.append({"name": "", "value": "", "unit": "inch"})
        st.rerun()

    return measurements
