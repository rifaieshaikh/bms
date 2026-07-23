"""Purchase returns list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.purchases.purchase_return_card import (
    _return_row,
    purchase_return_cards,
)
from vaybooks.bms.ui.components.purchases.purchase_return_dialog import (
    arm_return_dialog,
    open_return_dialog_if_armed,
)
from vaybooks.bms.ui.purchase_list_schemas import PURCHASE_RETURNS
from vaybooks.bms.ui.session_keys import filters_key


def _load(services, filters, sort):
    try:
        return [_return_row(r) for r in services["purchases"].list_purchase_returns()]
    except Exception:
        return []


def _apply_vendor_deep_link() -> None:
    vendor_id = navigation.consume_list_param("purchase_returns_list", "vendor")
    if not vendor_id:
        return
    key = filters_key(PURCHASE_RETURNS.entity_key)
    committed = st.session_state.setdefault(key, F.default_filters(PURCHASE_RETURNS))
    committed["vendor_id"] = vendor_id
    st.session_state.pop(f"{PURCHASE_RETURNS.entity_key}_flt_vendor_id", None)


def render(services: dict) -> None:
    _apply_vendor_deep_link()
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
        page_key_nav="purchase_returns_list",
    )
    if bar["primary_clicked"]:
        arm_return_dialog()
        st.rerun()
    if bar.get("view_nth"):
        navigation.go_to_detail("purchase_return_detail", bar["view_nth"])
    open_return_dialog_if_armed(services)
