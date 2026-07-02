import streamlit as st

from vaybooks.bms.domain.orders.bill_status import bill_is_invoiced
from vaybooks.bms.domain.orders.entities import CustomizationOrder


def invoice_form(services: dict, order: CustomizationOrder, invoices: list):
    invoice_service = services["invoices"]
    allow_override = st.checkbox(
        "Allow re-invoicing already invoiced items",
        key=f"inv_override_{order.id}",
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
            and not bill_is_invoiced(item.item_id, invoices)
        ]

    if not available:
        st.info("No completed items are available to invoice.")
        return

    labels = {
        f"{item.bill_number} — {item.description or 'No description'}": item.item_id
        for item in available
    }
    selected_labels = st.multiselect(
        "Items to invoice",
        list(labels.keys()),
        key=f"inv_bills_{order.id}",
    )
    bill_ids = [labels[label] for label in selected_labels]
    amount = st.number_input("Invoice Amount", min_value=0.0, key=f"inv_amt_{order.id}")

    if bill_ids and amount > 0:
        preview = invoice_service.preview_mph(order.id, bill_ids, amount)
        st.write(
            f"Preview MPH: {preview.get('margin_per_hour')} | "
            f"Margin: ₹{preview.get('margin_amount', 0):,.0f}"
        )

    if st.button("Generate Invoice", key=f"inv_btn_{order.id}"):
        try:
            invoice = invoice_service.generate_invoice(
                order.id,
                bill_ids,
                amount,
                allow_already_invoiced=allow_override,
            )
            st.success(f"Invoice {invoice.invoice_number} generated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
