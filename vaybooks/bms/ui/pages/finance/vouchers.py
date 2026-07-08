"""All Vouchers route."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags
from vaybooks.bms.ui.list_schemas import VOUCHERS
from vaybooks.bms.ui.pages import accounts as acc


def _load(services, filters, sort):
    try:
        return services["accounting"].list_vouchers()
    except Exception:
        return []


def _cards(page_vouchers, services):
    for v in page_vouchers:
        vtype = v.voucher_type.value if hasattr(v.voucher_type, "value") \
            else str(v.voucher_type)
        order_ref = " · Order linked" if v.reference_order_id else ""
        with st.container(border=True):
            st.markdown(f"**{v.voucher_number}** — ₹{v.total_debit:,.0f}  ·  _{vtype}_")
            st.caption(
                f"{acc._fmt_date(v.voucher_date)} | {v.description or '—'}{order_ref}"
            )
            if v.voucher_type == VoucherType.JOURNAL:
                for line in v.lines:
                    side = (f"Dr ₹{line.debit_amount:,.0f}" if line.debit_amount
                            else f"Cr ₹{line.credit_amount:,.0f}")
                    st.caption(f"• {line.account_name}: {side}")


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
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        acc._journal_dialog(services["accounting"])
    acc.open_pending_dialogs(services)
