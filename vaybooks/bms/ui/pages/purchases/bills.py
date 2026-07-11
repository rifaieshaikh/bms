"""Purchase bills list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.purchase_bill_dialog import (
    arm_purchase_bill_dialog,
    open_purchase_bill_dialog_if_armed,
)
from vaybooks.bms.ui.components.purchase_card import purchase_cards
from vaybooks.bms.ui.purchase_list_schemas import STORE_PURCHASES


def _load(services, filters, sort):
    try:
        return services["purchases"].list_purchase_bills()
    except Exception:
        return []


def render(services: dict) -> None:
    bar = render_list(
        STORE_PURCHASES,
        services=services,
        load_fn=_load,
        card_renderer=lambda rows, s: purchase_cards(rows, suffix="bills"),
        primary_label="+ Record Purchase",
        primary_key="purchase_create_btn",
        title="Purchase Bills",
        count_label="bills",
        empty_text="No purchase bills yet.",
    )
    if bar["primary_clicked"]:
        arm_purchase_bill_dialog()
        st.rerun()
    open_purchase_bill_dialog_if_armed(services)
