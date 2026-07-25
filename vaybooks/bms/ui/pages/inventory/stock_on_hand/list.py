"""Stock on Hand — optional location filter with per-location breakdown."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.inventory.inventory_product_card import inventory_product_card
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_STOCK

_ALL_LOCATIONS = "All locations"


def _load_stock(services, filters, sort):
    try:
        return services["inventory"].get_stock_on_hand()
    except Exception:
        return []


def _location_options(inventory) -> dict[str, str]:
    options = {_ALL_LOCATIONS: ""}
    try:
        for loc in inventory.list_locations(active_only=False):
            options[f"{loc.code} — {loc.name}"] = loc.id
    except Exception:
        pass
    return options


def _breakdown_caption(inventory, product_id: str, loc_names: dict[str, str]) -> str:
    try:
        balances = inventory.list_balances_by_product(product_id)
    except Exception:
        return ""
    parts = [
        f"{loc_names.get(b.location_id, b.location_id)}: {b.qty:g}"
        for b in balances
        if b.qty
    ]
    return " · ".join(parts) if parts else ""


def _render_cards(page_products, services, *, location_id, location_qty, loc_names):
    inventory = services["inventory"]

    def _render(product, _i):
        qty_override = location_qty.get(product.id, 0.0) if location_id else None
        breakdown = "" if location_id else _breakdown_caption(inventory, product.id, loc_names)
        view, _edit = inventory_product_card(
            product,
            key_prefix="inv_stock",
            show_qty=True,
            qty_override=qty_override,
            breakdown_caption=breakdown,
        )
        if view:
            navigation.go_to_detail("inventory_product_detail", product.id)

    render_card_grid(page_products, _render, suffix="inv_stock", card_min_width=240)


def render(services: dict):
    mark_wired("list.filters.open", "list.sort.open", "list.view_nth.1")
    inventory = services["inventory"]

    options = _location_options(inventory)
    labels = list(options.keys())
    selected_label = st.selectbox("Location", labels, key="inv_stock_location_filter")
    location_id = options.get(selected_label, "")

    location_qty: dict[str, float] = {}
    loc_names: dict[str, str] = {}
    try:
        loc_names = {loc.id: loc.name for loc in inventory.list_locations(active_only=False)}
    except Exception:
        loc_names = {}
    if location_id:
        try:
            location_qty = {
                bal.product_id: bal.qty
                for bal in inventory.list_balances_by_location(location_id)
            }
        except Exception:
            location_qty = {}

    bar = render_list(
        INVENTORY_STOCK,
        services=services,
        load_fn=_load_stock,
        card_renderer=lambda products, svc: _render_cards(
            products,
            svc,
            location_id=location_id,
            location_qty=location_qty,
            loc_names=loc_names,
        ),
        count_label="products",
        empty_text="No stock records yet.",
        page_key_nav="inventory_stock_list",
    )
    if bar.get("view_nth"):
        navigation.go_to_detail("inventory_product_detail", bar["view_nth"])
