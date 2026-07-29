from datetime import date

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.auth.session import require_specific_location


@st.dialog("New Production Batch")
def _new_batch_dialog(services: dict) -> None:
    service = services.get("production")
    inventory = services.get("inventory")
    recipes = service.list_recipes(active_only=True)
    locations = inventory.list_locations(active_only=True)
    if not recipes or not locations:
        st.error("An active recipe and production location are required.")
        return
    try:
        working_location_id = require_specific_location(services)
    except Exception as exc:
        st.error(str(exc))
        return
    recipe_labels = {recipe.name: recipe for recipe in recipes}
    location_labels = {location.name: location for location in locations}
    default_loc_name = next(
        (name for name, loc in location_labels.items() if loc.id == working_location_id),
        list(location_labels)[0],
    )
    batch_number = st.text_input(
        "Batch number", value=f"PB-{date.today():%Y%m%d}-"
    )
    recipe_label = st.selectbox("Recipe", list(recipe_labels))
    location_label = st.selectbox(
        "Location",
        list(location_labels),
        index=list(location_labels).index(default_loc_name),
    )
    c1, c2 = st.columns(2)
    batch_date = c1.date_input("Batch date", value=date.today())
    planned_qty = c2.number_input(
        "Planned quantity", min_value=0.0001, value=1.0
    )
    notes = st.text_area("Notes")
    if st.button("Create batch", type="primary", width="stretch"):
        try:
            batch = service.create_batch(
                batch_number=batch_number,
                recipe_id=recipe_labels[recipe_label].id,
                batch_date=batch_date,
                location_id=location_labels[location_label].id,
                planned_quantity=float(planned_qty),
                notes=notes,
            )
            navigation.go_to_detail("production_batch_detail", batch.id)
        except Exception as exc:
            st.error(str(exc))


def render(services: dict) -> None:
    st.header("Production Batches")
    service = services.get("production")
    inventory = services.get("inventory")
    if not service or not inventory:
        st.error("Production or inventory service is unavailable.")
        return
    if st.button("New batch", type="primary"):
        _new_batch_dialog(services)
    from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
    from vaybooks.bms.ui.auth.session import working_location_list_context

    working, accessible = working_location_list_context(services)
    filt = location_id_mongo_filter(working, accessible)
    batches = service.list_batches(location_filter=filt)
    if not batches:
        st.info("No production batches yet.")
        return
    status = st.multiselect(
        "Status",
        sorted({batch.status.value for batch in batches}),
        default=[],
    )
    rows = [batch for batch in batches if not status or batch.status.value in status]
    for batch in rows:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.markdown(f"**{batch.batch_number}**  \n{batch.recipe_name}")
            c2.write(batch.batch_date.strftime("%d %b %Y"))
            c2.caption(batch.status.value)
            c3.write(f"Cost ₹{batch.total_cost:,.2f}")
            c3.caption(f"Margin ₹{batch.batch_margin:,.2f}")
            if c4.button("Open", key=f"batch_open_{batch.id}"):
                navigation.go_to_detail("production_batch_detail", batch.id)
