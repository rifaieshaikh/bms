"""Salary payments route (vendor purchases moved to Purchases → Bills)."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.voucher_card import VoucherEditAction, voucher_cards
from vaybooks.bms.ui.list_schemas import PAYMENTS
from vaybooks.bms.ui.pages import accounts as acc


def _load_salaries(services, filters, sort):
    try:
        return services["accounting"].list_vouchers_by_type(VoucherType.SALARY_PAYMENT)
    except Exception:
        return []


def _cards(page_vouchers, services):
    def _builder(v):
        return {
            "service_label": None,
            "edit": VoucherEditAction(
                flag_key=acc.SAL,
                button_key=f"edit_sal_{v.id}",
            ),
        }

    voucher_cards(page_vouchers, suffix="payments", card_builder=_builder)


def render(services: dict):
    accounting_service = services["accounting"]
    st.info(
        "Vendor purchases are recorded under **Purchases → Purchase Bills**. "
        "This page shows salary payments only."
    )
    if st.button(
        "+ Record Salary",
        type="primary",
        key="btn_rec_sal",
        use_container_width=True,
    ):
        acc._clear_other_payment_dialog_flags(acc.SAL)
        acc._salary_dialog(accounting_service)

    render_list(
        PAYMENTS,
        services=services,
        load_fn=_load_salaries,
        card_renderer=_cards,
        count_label="salary payments",
        empty_text="No salary payments recorded yet.",
    )
    acc.open_pending_dialogs(services)
