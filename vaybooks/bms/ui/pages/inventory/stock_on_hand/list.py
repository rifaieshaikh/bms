import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.inventory.inventory_product_card import inventory_product_card
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_STOCK


def _load_stock(services, filters, sort):
    try:
        return services["inventory"].get_stock_on_hand()
    except Exception:
        return []


def _render_cards(page_products, services):
    def _render(product, _i):
        view, _edit = inventory_product_card(
            product, key_prefix="inv_stock", show_qty=True
        )
        if view:
            navigation.go_to_detail("inventory_product_detail", product.id)

    render_card_grid(page_products, _render, suffix="inv_stock", card_min_width=240)


def render(services: dict):
    mark_wired("list.filters.open", "list.sort.open", "list.view_nth.1")
    bar = render_list(
        INVENTORY_STOCK,
        services=services,
        load_fn=_load_stock,
        card_renderer=_render_cards,
        count_label="products",
        empty_text="No stock records yet.",
        page_key_nav="inventory_stock_list",
    )
    if bar.get("view_nth"):
        navigation.go_to_detail("inventory_product_detail", bar["view_nth"])
