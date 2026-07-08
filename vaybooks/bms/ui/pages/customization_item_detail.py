"""Customization Item detail route (`?id=<item_id>&order_id=<order_id>`)."""

from vaybooks.bms.ui.pages.customization_items import render_item_detail


def render(services: dict):
    render_item_detail(services)
