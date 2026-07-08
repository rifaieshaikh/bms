import streamlit as st

from vaybooks.bms.ui.components.dashboard_cards import (
    maybe_navigate_to_order_detail,
    maybe_navigate_to_orders_page,
    queue_order_detail_navigation,
    queue_orders_page_navigation,
)
from vaybooks.bms.ui.components.item_detail_panel import customization_item_detail_panel
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE, paginate_list, render_page_controls
from vaybooks.bms.ui.session_keys import EDITING_ITEM


def _render_item_editor(services: dict, order_id: str, item_id: str):
    order_service = services["orders"]
    invoice_service = services["invoices"]
    delivery_service = services["deliveries"]

    if st.button("← Back to items", key="item_editor_back"):
        st.session_state.pop(EDITING_ITEM, None)

    detail = order_service.get_customization_item_detail(order_id, item_id)
    if not detail:
        st.error("Customization item not found")
        return

    order, item = detail
    invoices = invoice_service.list_invoices_by_order(order.id)
    deliveries = delivery_service.list_by_order(order.id)

    customization_item_detail_panel(
        services,
        order,
        item,
        invoices,
        deliveries,
        key_prefix=f"item_page_{item_id}",
        show_header=True,
        show_item_edit=True,
        allow_activity_dialogs=True,
    )


def _item_summary_card(services: dict, item: dict, index: int):
    with st.container(border=True):
        st.markdown(f"**{item['bill_number']}**")
        st.write(item["description"] or "—")
        st.caption(
            f"{item['customer_name']} | {item['phone_number']} | "
            f"Order {item['order_number']}"
        )
        st.write(f"Item status: {item['item_status']}")
        st.write(f"Order status: {item['order_status']}")

        if item.get("mph_snapshot_at"):
            mph = item.get("margin_per_hour")
            mph_txt = f"\u20b9{mph:,.0f}/h" if mph is not None else "— (no hours)"
            margin = item.get("margin_amount") or 0
            st.markdown(f"**MPH:** {mph_txt}  |  Margin \u20b9{margin:,.0f}")
        else:
            st.caption("MPH pending (invoice + delivery)")

        if st.button(
            "Edit Item",
            key=f"item_edit_{index}_{item['item_id']}",
            type="primary",
            use_container_width=True,
        ):
            st.session_state[EDITING_ITEM] = {
                "order_id": item["order_id"],
                "item_id": item["item_id"],
            }

        st.button(
            "View Order",
            key=f"item_view_{index}_{item['item_id']}",
            use_container_width=True,
            on_click=queue_order_detail_navigation,
            args=(str(item["order_id"]),),
        )


def render(services: dict):
    st.title("Customization Items")
    order_service = services["orders"]

    editing = st.session_state.get(EDITING_ITEM)
    if editing:
        _render_item_editor(services, editing["order_id"], editing["item_id"])
        return

    header_cols = st.columns([4, 1])
    with header_cols[0]:
        query = st.text_input(
            "Search items",
            placeholder="Bill number, description, order number, customer...",
            key="items_search",
        )
    with header_cols[1]:
        st.button(
            "View Orders",
            use_container_width=True,
            on_click=queue_orders_page_navigation,
        )

    if query:
        items = order_service.search_customization_items(query)
    else:
        items = order_service.list_all_customization_items()

    if not items:
        st.info("No customization items found.")
        return

    page_items, page, total_pages = paginate_list(
        items,
        page_key="items_page",
        page_size=CARD_PAGE_SIZE,
        filter_key="items_search",
        filter_value=query,
    )
    for row_start in range(0, len(page_items), 3):
        row_items = page_items[row_start : row_start + 3]
        cols = st.columns(len(row_items))
        for col_index, (col, item) in enumerate(zip(cols, row_items)):
            with col:
                _item_summary_card(services, item, row_start + col_index)
    render_page_controls(
        page, total_pages, len(items),
        page_key="items_page", prev_key="items_prev", next_key="items_next",
        label="items",
    )
    maybe_navigate_to_order_detail()
    maybe_navigate_to_orders_page()
