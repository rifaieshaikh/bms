"""Salary and commission payments route."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.common.voucher_card import VoucherEditAction, voucher_cards
from vaybooks.bms.ui.keyboard.actions import consume_action
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.list_schemas import PAYMENTS
from vaybooks.bms.ui.pages.finance.accounts import list as acc


def _load_payments(services, filters, sort):
    try:
        accounting = services["accounting"]
        salaries = accounting.list_vouchers_by_type(VoucherType.SALARY_PAYMENT)
        commissions = accounting.list_vouchers_by_type(VoucherType.COMMISSION_PAYMENT)
        return sorted(
            list(salaries) + list(commissions),
            key=lambda v: v.voucher_date,
            reverse=True,
        )
    except Exception:
        return []


def _cards(page_vouchers, services):
    def _builder(v):
        if v.voucher_type == VoucherType.COMMISSION_PAYMENT:
            return {
                "service_label": "Commission",
                "edit": VoucherEditAction(
                    flag_key=acc.COMM,
                    button_key=f"edit_comm_{v.id}",
                ),
            }
        return {
            "service_label": "Salary",
            "edit": VoucherEditAction(
                flag_key=acc.SAL,
                button_key=f"edit_sal_{v.id}",
            ),
        }

    voucher_cards(page_vouchers, suffix="payments", card_builder=_builder)


def render(services: dict):
    accounting_service = services["accounting"]
    mark_wired("list.primary", "finance.salary.add")
    st.info(
        "Vendor purchases are recorded under **Purchases → Purchase Bills**. "
        "This page shows salary and commission payments."
    )
    cols = st.columns(2)
    if cols[0].button(
        "+ Record Salary",
        type="primary",
        key="btn_rec_sal",
        width="stretch",
    ) or consume_action("list.primary"):
        acc._clear_other_payment_dialog_flags(acc.SAL)
        acc._salary_dialog(accounting_service)
    if cols[1].button(
        "+ Record Commission",
        type="secondary",
        key="btn_rec_comm",
        width="stretch",
    ):
        # Arm only — open_pending_dialogs opens the dialog once (avoids duplicate ID).
        acc._clear_other_payment_dialog_flags(acc.COMM)
        st.session_state[acc.COMM] = "new"

    render_list(
        PAYMENTS,
        services=services,
        load_fn=_load_payments,
        card_renderer=_cards,
        count_label="payments",
        empty_text="No salary or commission payments recorded yet.",
        page_key_nav="payments_list",
    )
    acc.open_pending_dialogs(services)
