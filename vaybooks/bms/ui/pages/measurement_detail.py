"""Measurement detail route."""

from vaybooks.bms.ui.pages.measurements import render_measurement_detail


def render(services: dict) -> None:
    render_measurement_detail(services)
