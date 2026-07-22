import streamlit as st

from vaybooks.bms.domain.boutique.orders.bill_status import bill_is_delivered
from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder


def delivery_form(services: dict, order: CustomizationOrder, deliveries: list):
    delivery_service = services["deliveries"]
    allow_override = st.checkbox(
        "Allow re-delivering already delivered items",
        key=f"del_override_{order.id}",
    )

    if allow_override:
        available = [
            item
            for item in order.customization_items
            if order.item_activities_complete(item.item_id)
        ]
    else:
        available = [
            item
            for item in order.customization_items
            if order.item_activities_complete(item.item_id)
            and not bill_is_delivered(item.item_id, deliveries)
        ]

    if not available:
        st.info("No completed items are available to deliver.")
        return

    labels = {
        f"{item.bill_number} — {item.description or 'No description'}": item.item_id
        for item in available
    }
    selected_labels = st.multiselect(
        "Items to deliver",
        list(labels.keys()),
        key=f"del_bills_{order.id}",
    )
    bill_ids = [labels[label] for label in selected_labels]
    delivery_date = st.date_input("Delivery Date", key=f"del_date_{order.id}")
    delivery_notes = st.text_area("Delivery Notes", key=f"del_notes_{order.id}")

    if st.button("Record Delivery", key=f"del_btn_{order.id}"):
        try:
            delivery_service.record_delivery(
                order.id,
                bill_ids,
                delivery_date,
                delivery_notes,
                allow_already_delivered=allow_override,
            )
            st.success("Delivery recorded")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
