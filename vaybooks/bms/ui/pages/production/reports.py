import streamlit as st


REPORT_METHODS = {
    "Batch Register": "batch_register_report",
    "Batch Cost Sheet": "batch_cost_sheet_report",
    "Batch Margin": "batch_margin_report",
    "Yield vs Recipe (variance)": "yield_variance_report",
    "Production Expenses (by type / activity)": "production_expense_report",
    "Output Summary (by product / period)": "output_summary_report",
    "RM Consumption": "rm_consumption_report",
    "WIP / Unposted Batches": "wip_open_batches_report",
    "Cost per Unit Trend": "cost_per_unit_trend_report",
    "Recipe Master List": "recipe_master_report",
}


def render(services: dict) -> None:
    st.header("Production Reports")
    reports = services.get("reports_production")
    if not reports:
        st.error("Production reports service is unavailable.")
        return
    title = st.selectbox("Report", list(REPORT_METHODS))
    method = getattr(reports, REPORT_METHODS[title])
    try:
        rows = method(None)
    except TypeError:
        rows = method()
    st.dataframe(rows, width="stretch", hide_index=True)
    if rows:
        st.download_button(
            "Download CSV",
            data=reports.to_csv(rows),
            file_name=f"{REPORT_METHODS[title]}.csv",
            mime="text/csv",
        )
