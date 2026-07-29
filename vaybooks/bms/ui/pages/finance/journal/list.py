"""Journal Entries route."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.common.voucher_card import voucher_cards
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags
from vaybooks.bms.ui.list_schemas import JOURNAL
from vaybooks.bms.ui.pages.finance.accounts import list as acc


def _load(services, filters, sort):
    try:
        from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
        from vaybooks.bms.ui.auth.session import working_location_list_context

        working, accessible = working_location_list_context(services)
        filt = location_id_mongo_filter(working, accessible)
        return services["accounting"].list_vouchers_by_type(
            VoucherType.JOURNAL, location_filter=filt
        )
    except Exception:
        return []


def _cards(page_vouchers, services):
    voucher_cards(
        page_vouchers,
        suffix="journal",
        show_journal_lines=True,
        show_type_badge=False,
        card_min_width=280,
    )


def render(services: dict):
    bar = render_list(
        JOURNAL,
        services=services,
        load_fn=_load,
        card_renderer=_cards,
        primary_label="+ New Journal Entry",
        primary_key="journal_create_btn",
        count_label="entries",
        empty_text="No journal entries yet.",
        page_key_nav="journal_list",
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        acc._journal_dialog(services)
    acc.open_pending_dialogs(services)
