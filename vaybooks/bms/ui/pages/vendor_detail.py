"""Vendor detail route (`?id=<vendor_id>`)."""

from vaybooks.bms.ui.pages.vendors import render_vendor_detail


def render(services: dict):
    render_vendor_detail(services)
