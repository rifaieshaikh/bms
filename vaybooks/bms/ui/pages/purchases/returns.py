"""Purchase returns list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.purchase_return_card import (
    _return_row,
    purchase_return_cards,
)
from vaybooks.bms.ui.components.purchase_return_dialog import (
    arm_return_dialog,
    open_return_dialog_if_armed,
)
from vaybooks.bms.ui.purchase_list_schemas import PURCHASE_RETURNS


def _load(services, filters, sort):
    try:
        return [_return_row(r) for r in services["purchases"].list_purchase_returns()]
    except Exception:
        return []


def render(services: dict) -> None:
    bar = render_list(
        PURCHASE_RETURNS,
        services=services,
        load_fn=_load,
        card_renderer=lambda rows, s: purchase_return_cards(rows, suffix="returns_list"),
        primary_label="+ Record Return",
        primary_key="return_create_btn",
        title="Purchase Returns",
        count_label="returns",
        empty_text="No purchase returns yet.",
    )
    if bar["primary_clicked"]:
        arm_return_dialog()
        st.rerun()
    open_return_dialog_if_armed(services)
