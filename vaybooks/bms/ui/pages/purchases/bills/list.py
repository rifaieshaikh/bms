"""Purchase bills list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.purchases.purchase_bill_dialog import (
    arm_purchase_bill_dialog,
    open_purchase_bill_dialog_if_armed,
)
from vaybooks.bms.ui.components.purchases.purchase_card import purchase_cards
from vaybooks.bms.ui.purchase_list_schemas import STORE_PURCHASES
from vaybooks.bms.ui.session_keys import filters_key


def _load(services, filters, sort):
    try:
        return services["purchases"].list_purchase_bills()
    except Exception:
        return []


def _apply_vendor_deep_link() -> None:
    vendor_id = navigation.consume_list_param("purchases_list", "vendor")
    if not vendor_id:
        return
    key = filters_key(STORE_PURCHASES.entity_key)
    committed = st.session_state.setdefault(key, F.default_filters(STORE_PURCHASES))
    committed["vendor_id"] = vendor_id
    st.session_state.pop(f"{STORE_PURCHASES.entity_key}_flt_vendor_id", None)


def render(services: dict) -> None:
    _apply_vendor_deep_link()
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
        page_key_nav="purchases_list",
    )
    if bar["primary_clicked"]:
        arm_purchase_bill_dialog()
        st.rerun()
    open_purchase_bill_dialog_if_armed(services)
