"""All Vouchers route."""

import streamlit as st

from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.common.voucher_card import voucher_cards
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags
from vaybooks.bms.ui.list_schemas import VOUCHERS
from vaybooks.bms.ui.pages.finance.accounts import list as acc


def _load(services, filters, sort):
    try:
        from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
        from vaybooks.bms.ui.auth.session import working_location_list_context

        working, accessible = working_location_list_context(services)
        filt = location_id_mongo_filter(working, accessible)
        return services["accounting"].list_vouchers(location_filter=filt)
    except Exception:
        return []


def _cards(page_vouchers, services):
    voucher_cards(
        page_vouchers,
        suffix="vouchers",
        show_journal_lines=True,
        card_min_width=280,
    )


def render(services: dict):
    bar = render_list(
        VOUCHERS,
        services=services,
        load_fn=_load,
        card_renderer=_cards,
        primary_label="+ Create Voucher",
        primary_key="vouchers_create_btn",
        count_label="vouchers",
        empty_text="No vouchers recorded yet.",
        page_key_nav="vouchers_list",
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        acc._journal_dialog(services)
    acc.open_pending_dialogs(services)
