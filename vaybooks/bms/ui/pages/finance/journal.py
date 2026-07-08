"""Journal Entries route."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags
from vaybooks.bms.ui.list_schemas import JOURNAL
from vaybooks.bms.ui.pages import accounts as acc


def _load(services, filters, sort):
    try:
        return services["accounting"].list_vouchers_by_type(VoucherType.JOURNAL)
    except Exception:
        return []


def _cards(page_vouchers, services):
    for v in page_vouchers:
        with st.container(border=True):
            st.markdown(f"**{v.voucher_number}** — ₹{v.total_debit:,.0f}")
            st.caption(f"{acc._fmt_date(v.voucher_date)} | {v.description or '—'}")
            for line in v.lines:
                side = (f"Dr ₹{line.debit_amount:,.0f}" if line.debit_amount
                        else f"Cr ₹{line.credit_amount:,.0f}")
                st.caption(f"• {line.account_name}: {side}")


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
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        acc._journal_dialog(services["accounting"])
    acc.open_pending_dialogs(services)
