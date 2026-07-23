"""Goods receipt list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.purchases.grn_card import _grn_row, grn_cards
from vaybooks.bms.ui.components.purchases.grn_dialog import arm_grn_dialog, open_grn_dialog_if_armed
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.purchase_list_schemas import GOODS_RECEIPTS
from vaybooks.bms.ui.session_keys import filters_key


def _load(services, filters, sort):
    try:
        return [_grn_row(g) for g in services["purchases"].list_goods_receipts()]
    except Exception:
        return []


def _apply_vendor_deep_link() -> None:
    vendor_id = navigation.consume_list_param("goods_receipt_list", "vendor")
    if not vendor_id:
        return
    key = filters_key(GOODS_RECEIPTS.entity_key)
    committed = st.session_state.setdefault(key, F.default_filters(GOODS_RECEIPTS))
    committed["vendor_id"] = vendor_id
    st.session_state.pop(f"{GOODS_RECEIPTS.entity_key}_flt_vendor_id", None)


def render(services: dict) -> None:
    _apply_vendor_deep_link()
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
        page_key_nav="goods_receipt_list",
    )
    if bar["primary_clicked"]:
        arm_grn_dialog()
        st.rerun()
    open_grn_dialog_if_armed(services)
