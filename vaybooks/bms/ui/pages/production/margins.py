import streamlit as st

from vaybooks.bms.domain.shared.enums import ProductionBatchStatus


def render(services: dict) -> None:
    st.header("Production Cost & Margin")
    service = services.get("production")
    if not service:
        st.error("Production service is unavailable.")
        return
    batches = service.list_batches(ProductionBatchStatus.POSTED)
    rows = [
        {
            "Date": batch.batch_date,
            "Batch": batch.batch_number,
            "Recipe": batch.recipe_name,
            "Material cost": batch.material_cost,
            "Expenses": batch.expense_cost,
            "Total cost": batch.total_cost,
            "Expected sales value": batch.expected_sales_value,
            "Margin": batch.batch_margin,
            "Margin %": (
                round(batch.batch_margin / batch.expected_sales_value * 100, 2)
                if batch.expected_sales_value
                else 0
            ),
        }
        for batch in batches
    ]
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Post a production batch to see margin analysis.")
