"""Sales returns list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.sales_return_card import _return_row, sales_return_cards
from vaybooks.bms.ui.components.sales_return_dialog import (
    arm_sales_return_dialog,
    open_sales_return_dialog_if_armed,
)
from vaybooks.bms.ui.sales_list_schemas import SALES_RETURNS


def _load(services, filters, sort):
    try:
        return [_return_row(r) for r in services["sales"].list_sales_returns()]
    except Exception:
        return []


def render(services: dict) -> None:
    bar = render_list(
        SALES_RETURNS,
        services=services,
        load_fn=_load,
        card_renderer=lambda rows, s: sales_return_cards(rows, suffix="sales_returns_list"),
        primary_label="+ Record Return",
        primary_key="sales_return_create_btn",
        title="Sales Returns",
        count_label="returns",
        empty_text="No sales returns yet.",
    )
    if bar["primary_clicked"]:
        arm_sales_return_dialog()
        st.rerun()
    open_sales_return_dialog_if_armed(services)
