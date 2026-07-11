"""Goods receipt list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.components.grn_card import _grn_row, grn_cards
from vaybooks.bms.ui.components.grn_dialog import arm_grn_dialog, open_grn_dialog_if_armed
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.purchase_list_schemas import GOODS_RECEIPTS


def _load(services, filters, sort):
    try:
        return [_grn_row(g) for g in services["purchases"].list_goods_receipts()]
    except Exception:
        return []


def render(services: dict) -> None:
    bar = render_list(
        GOODS_RECEIPTS,
        services=services,
        load_fn=_load,
        card_renderer=lambda rows, s: grn_cards(rows, suffix="grn_list"),
        primary_label="+ Receive GRN",
        primary_key="grn_create_btn",
        title="Goods Receipt",
        count_label="receipts",
        empty_text="No goods receipts yet.",
    )
    if bar["primary_clicked"]:
        arm_grn_dialog()
        st.rerun()
    open_grn_dialog_if_armed(services)
