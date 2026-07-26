import streamlit as st


def render(services: dict) -> None:
    st.header("Production Yield & Variance")
    service = services.get("production")
    if not service:
        st.error("Production service is unavailable.")
        return
    rows = []
    for batch in service.list_batches():
        recipe = service.get_recipe(batch.recipe_id)
        if not recipe:
            continue
        scale = batch.planned_quantity / recipe.base_quantity
        expected = {line.product_id: line.expected_qty * scale for line in recipe.outputs}
        for output in batch.outputs:
            expected_qty = float(expected.get(output.product_id, 0))
            variance = float(output.qty) - expected_qty
            rows.append(
                {
                    "Date": batch.batch_date,
                    "Batch": batch.batch_number,
                    "Output": output.product_name,
                    "Expected": expected_qty,
                    "Actual": output.qty,
                    "Variance": variance,
                    "Variance %": (
                        round(variance / expected_qty * 100, 2) if expected_qty else 0
                    ),
                }
            )
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("No production yield data yet.")
