import streamlit as st

from vaybooks.bms.domain.boutique.orders.order_refs import compact_order_ref
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.item_detail_panel import customization_item_detail_panel
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.styles import render_card_grid, status_badge
from vaybooks.bms.ui.list_schemas import ITEMS


def _render_item_editor(services: dict, order_id: str, item_id: str):
    from vaybooks.bms.ui.keyboard.actions import consume_action

    order_service = services["orders"]
    invoice_service = services["invoices"]
    delivery_service = services["deliveries"]

    if st.button("← Back to items", key="item_editor_back") or consume_action("nav.back"):
        navigation.go_back_to_list("items", "items_list")
        return

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
        st.caption(item["description"] or "—")
        st.caption(
            f"{item['customer_name']} · {item['phone_number']} · "
            f"{compact_order_ref(item['order_number'])}"
        )
        st.markdown(status_badge(item["item_status"]), unsafe_allow_html=True)

        if item.get("mph_snapshot_at"):
            mph = item.get("margin_per_hour")
            mph_txt = f"\u20b9{mph:,.0f}/h" if mph is not None else "— (no hours)"
            margin = item.get("margin_amount") or 0
            st.markdown(f"**MPH:** {mph_txt}  |  Margin \u20b9{margin:,.0f}")
        else:
            st.caption("MPH pending (invoice + delivery)")

        if st.button(
            "Edit",
            key=f"item_edit_{index}_{item['item_id']}",
            type="primary",
            use_container_width=True,
        ):
            navigation.go_to_detail(
                "item_detail", item["item_id"], order_id=item["order_id"]
            )

        if st.button(
            "Order",
            key=f"item_view_{index}_{item['item_id']}",
            use_container_width=True,
        ):
            navigation.go_to_detail("order_detail", str(item["order_id"]))


def _load_items(services, filters, sort):
    try:
        return services["orders"].list_all_customization_items()
    except Exception:
        return []


def _render_cards(page_items, services):
    render_card_grid(
        page_items,
        lambda item, i: _item_summary_card(services, item, i),
        suffix="items",
    )


def render(services: dict):
    render_list(
        ITEMS,
        services=services,
        load_fn=_load_items,
        card_renderer=_render_cards,
        count_label="items",
        empty_text="No customization items found.",
        page_key_nav="items_list",
    )


def render_item_detail(services: dict):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("item_detail")
    mark_wired("nav.back")
    item_id = navigation.current_detail_id("item_detail")
    order_id = navigation.current_detail_param("item_detail", "order_id")
    if not item_id or not order_id:
        st.error("No item selected.")
        if st.button("← Back to items") or consume_action("nav.back"):
            navigation.go_back_to_list("items", "items_list")
        return
    _render_item_editor(services, order_id, item_id)
