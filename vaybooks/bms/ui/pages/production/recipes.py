from __future__ import annotations

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.production.entities import (
    Recipe,
    RecipeInput,
    RecipeOutput,
    RecipeStage,
)
from vaybooks.bms.domain.shared.enums import (
    ProductionCostAllocationMethod,
    ProductionOutputRole,
)


def _product_options(inventory) -> tuple[list[str], dict[str, object]]:
    products = inventory.list_products(active_only=True)
    labels = {f"{item.sku} — {item.name}": item for item in products}
    return list(labels), labels


@st.dialog("Production Recipe", width="large")
def _recipe_dialog(service, inventory, recipe_id: str = "") -> None:
    recipe = service.get_recipe(recipe_id) if recipe_id else None
    labels, products = _product_options(inventory)
    if not labels:
        st.error("Create inventory products before defining a recipe.")
        return
    name = st.text_input("Recipe name", value=recipe.name if recipe else "")
    c1, c2 = st.columns(2)
    code = c1.text_input("Code", value=recipe.code if recipe else "")
    base_quantity = c2.number_input(
        "Base quantity",
        min_value=0.0001,
        value=float(recipe.base_quantity if recipe else 1),
    )
    method_values = [item.value for item in ProductionCostAllocationMethod]
    current_method = recipe.allocation_method.value if recipe else method_values[0]
    method = st.selectbox(
        "Cost allocation method",
        method_values,
        index=method_values.index(current_method),
    )
    description = st.text_area(
        "Description", value=recipe.description if recipe else ""
    )

    st.markdown("**Inputs**")
    input_rows = []
    for line in recipe.inputs if recipe else []:
        product = inventory.get_product(line.product_id)
        input_rows.append(
            {
                "Product": (
                    f"{product.sku} — {product.name}" if product else line.product_name
                ),
                "Quantity": line.qty,
                "Scrap %": line.scrap_pct,
            }
        )
    input_df = st.data_editor(
        pd.DataFrame(input_rows or [{"Product": labels[0], "Quantity": 1.0, "Scrap %": 0.0}]),
        num_rows="dynamic",
        column_config={
            "Product": st.column_config.SelectboxColumn(options=labels, required=True),
            "Quantity": st.column_config.NumberColumn(min_value=0.0001, required=True),
            "Scrap %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0),
        },
        width="stretch",
        key=f"recipe_inputs_{recipe_id or 'new'}",
    )

    st.markdown("**Outputs**")
    output_rows = []
    for line in recipe.outputs if recipe else []:
        product = inventory.get_product(line.product_id)
        output_rows.append(
            {
                "Product": (
                    f"{product.sku} — {product.name}" if product else line.product_name
                ),
                "Expected qty": line.expected_qty,
                "Role": line.role.value,
                "Allocation %": line.allocation_pct,
                "NRV rate": line.nrv_rate,
            }
        )
    output_df = st.data_editor(
        pd.DataFrame(
            output_rows
            or [
                {
                    "Product": labels[0],
                    "Expected qty": 1.0,
                    "Role": ProductionOutputRole.MAIN.value,
                    "Allocation %": 100.0,
                    "NRV rate": 0.0,
                }
            ]
        ),
        num_rows="dynamic",
        column_config={
            "Product": st.column_config.SelectboxColumn(options=labels, required=True),
            "Expected qty": st.column_config.NumberColumn(min_value=0.0001),
            "Role": st.column_config.SelectboxColumn(
                options=[item.value for item in ProductionOutputRole]
            ),
            "Allocation %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0),
            "NRV rate": st.column_config.NumberColumn(min_value=0.0),
        },
        width="stretch",
        key=f"recipe_outputs_{recipe_id or 'new'}",
    )

    stage_text = st.text_area(
        "Activities / stages (one per line)",
        value="\n".join(stage.name for stage in (recipe.stages if recipe else [])),
        placeholder="Cleaning\nMilling\nPacking",
    )
    is_active = st.checkbox(
        "Active", value=recipe.is_active if recipe else True
    )
    if st.button("Save recipe", type="primary", width="stretch"):
        try:
            entity = recipe or Recipe(name="", inputs=[], outputs=[])
            entity.name = name
            entity.code = code
            entity.description = description
            entity.base_quantity = float(base_quantity)
            entity.allocation_method = ProductionCostAllocationMethod(method)
            entity.is_active = is_active
            entity.inputs = [
                RecipeInput(
                    product_id=products[row["Product"]].id,
                    product_name=products[row["Product"]].name,
                    unit=products[row["Product"]].unit,
                    qty=float(row["Quantity"]),
                    scrap_pct=float(row.get("Scrap %", 0) or 0),
                )
                for row in input_df.to_dict("records")
                if row.get("Product") in products and float(row.get("Quantity") or 0) > 0
            ]
            entity.outputs = [
                RecipeOutput(
                    product_id=products[row["Product"]].id,
                    product_name=products[row["Product"]].name,
                    unit=products[row["Product"]].unit,
                    expected_qty=float(row["Expected qty"]),
                    role=ProductionOutputRole(row["Role"]),
                    allocation_pct=float(row.get("Allocation %", 0) or 0),
                    nrv_rate=float(row.get("NRV rate", 0) or 0),
                )
                for row in output_df.to_dict("records")
                if row.get("Product") in products
                and float(row.get("Expected qty") or 0) > 0
            ]
            entity.stages = [
                RecipeStage(name=value.strip(), sequence=index)
                for index, value in enumerate(stage_text.splitlines(), start=1)
                if value.strip()
            ]
            service.save_recipe(entity)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render(services: dict) -> None:
    st.header("Production Recipes")
    service = services.get("production")
    inventory = services.get("inventory")
    if not service or not inventory:
        st.error("Production or inventory service is unavailable.")
        return
    if st.button("New recipe", type="primary"):
        _recipe_dialog(service, inventory)
    recipes = service.list_recipes(active_only=False)
    for recipe in recipes:
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 2, 1])
            c1.markdown(f"**{recipe.name}**  \n{recipe.code or 'No code'}")
            c2.caption(
                f"{len(recipe.inputs)} inputs · {len(recipe.outputs)} outputs · "
                f"{len(recipe.stages)} activities"
            )
            if c3.button("Edit", key=f"recipe_edit_{recipe.id}"):
                _recipe_dialog(service, inventory, recipe.id)
    if not recipes:
        st.info("No production recipes yet.")
