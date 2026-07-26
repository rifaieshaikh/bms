import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import metric_grid


def render(services: dict) -> None:
    st.header("Production Dashboard")
    service = services.get("production")
    if not service:
        st.error("Production service is unavailable.")
        return
    summary = service.dashboard_summary()
    metric_grid(
        [
            ("Open batches", summary["open_batches"]),
            ("Posted batches", summary["posted_batches"]),
            ("WIP value", f"₹{summary['wip_value']:,.2f}"),
            ("Output value", f"₹{summary['output_value']:,.2f}"),
            ("Batch margin", f"₹{summary['margin']:,.2f}"),
        ],
        suffix="production_dashboard",
    )
    st.markdown("#### Quick actions")
    columns = st.columns(4)
    if columns[0].button("Recipes", width="stretch"):
        navigation.go_to_list("production_recipes")
    if columns[1].button("Batches", width="stretch"):
        navigation.go_to_list("production_batches")
    if columns[2].button("Day Book", width="stretch"):
        navigation.go_to_list("production_day_book")
    if columns[3].button("Reports", width="stretch"):
        navigation.go_to_list("production_reports")

    batches = service.list_batches()
    if batches:
        st.markdown("#### Recent batches")
        st.dataframe(
            [
                {
                    "Batch": batch.batch_number,
                    "Date": batch.batch_date,
                    "Recipe": batch.recipe_name,
                    "Status": batch.status.value,
                    "Cost": batch.total_cost,
                    "Margin": batch.batch_margin,
                }
                for batch in batches[:10]
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Create a recipe and production batch to get started.")
