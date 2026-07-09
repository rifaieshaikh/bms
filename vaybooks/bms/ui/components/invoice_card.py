from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional, Sequence

import streamlit as st

from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.orders.entities import CustomizationOrder
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags, register_armed_dialog
from vaybooks.bms.ui.styles import render_card_grid, status_badge


@dataclass(frozen=True)
class InvoiceEditAction:
    flag_key: str
    button_key: str
    clear_dialogs: bool = False
    register_dialog: bool = False
    before_edit: Optional[Callable[[], None]] = None


def _item_labels(order: CustomizationOrder, invoice: Invoice) -> list[str]:
    return [
        it.bill_number
        for bill_id in invoice.bill_ids
        if (it := order.get_item_by_id(bill_id))
    ]


def invoice_card(
    invoice: Invoice,
    order: CustomizationOrder,
    *,
    posted: bool = False,
    edit: InvoiceEditAction | None = None,
) -> None:
    item_labels = _item_labels(order, invoice)
    items_text = ", ".join(item_labels) or "—"
    item_count = len(item_labels)

    with st.container(border=True):
        st.markdown(
            f'<p class="z-card-title">{invoice.invoice_number}</p>',
            unsafe_allow_html=True,
        )

        if invoice.discount_amount > 0:
            st.markdown(
                f'<p class="z-card-amount" style="color:#2E7D46">'
                f"₹{invoice.net_amount:,.0f}</p>",
                unsafe_allow_html=True,
            )
            badges = status_badge(
                f"Gross ₹{invoice.invoice_amount:,.0f}", "gray", compact=True
            )
        else:
            st.markdown(
                f'<p class="z-card-amount" style="color:#2E7D46">'
                f"₹{invoice.invoice_amount:,.0f}</p>",
                unsafe_allow_html=True,
            )
            badges = ""

        if posted:
            badges = (badges + " ") if badges else ""
            badges += status_badge("Posted", "blue", compact=True)
        if badges:
            st.markdown(badges, unsafe_allow_html=True)

        items_part = (
            f"{item_count} item{'s' if item_count != 1 else ''}: {items_text}"
            if item_count
            else f"Items: {items_text}"
        )
        st.caption(f"{invoice.invoice_date} · {items_part}")

        if invoice.discount_amount > 0:
            st.caption(f"Discount ₹{invoice.discount_amount:,.0f}")

        margin_badges = (
            status_badge(f"Margin ₹{invoice.margin_amount:,.0f}", "violet", compact=True)
            + " "
            + status_badge(
                f"MPH ₹{invoice.margin_per_hour:,.0f}/h"
                if invoice.margin_per_hour is not None
                else "MPH —",
                "gray",
                compact=True,
            )
        )
        st.markdown(margin_badges, unsafe_allow_html=True)

        if edit and st.button(
            "Edit",
            key=edit.button_key,
            type="primary",
            use_container_width=True,
        ):
            if edit.before_edit:
                edit.before_edit()
            if edit.clear_dialogs:
                clear_all_dialog_flags()
            st.session_state[edit.flag_key] = invoice.id
            if edit.register_dialog:
                register_armed_dialog(edit.flag_key)
            st.rerun()


def invoice_cards(
    invoices: Sequence[Invoice],
    order: CustomizationOrder,
    *,
    suffix: str,
    posted_lookup: Optional[Callable[[str], bool]] = None,
    card_builder: Optional[Callable[[Invoice], dict]] = None,
    card_min_width: int = 240,
    **card_kwargs,
) -> None:
    def _render(invoice: Invoice, _index: int) -> None:
        kwargs = dict(card_kwargs)
        if posted_lookup:
            kwargs["posted"] = posted_lookup(invoice.id)
        if card_builder:
            kwargs.update(card_builder(invoice))
        invoice_card(invoice, order, **kwargs)

    render_card_grid(
        invoices,
        _render,
        suffix=suffix,
        card_min_width=card_min_width,
    )
