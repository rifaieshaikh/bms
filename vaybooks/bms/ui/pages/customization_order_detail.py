"""Customization Order detail route (`?id=<order_id>`)."""

from vaybooks.bms.ui.pages.customization_orders import render_order_detail


def render(services: dict):
    render_order_detail(services)
