from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional, Sequence

import streamlit as st

from vaybooks.bms.domain.boutique.invoices.entities import Invoice
from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder
from vaybooks.bms.ui.components.shared import CardAction, card
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags, register_armed_dialog
from vaybooks.bms.ui.styles import render_card_grid


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
    pdf_bytes: bytes | None = None,
) -> None:
    item_labels = _item_labels(order, invoice)
    items_text = ", ".join(item_labels) or "—"
    item_count = len(item_labels)
    display_amount = invoice.grand_total if invoice.is_generated else invoice.net_amount
    show_taxable = invoice.discount_amount > 0 or (
        invoice.is_generated and invoice.total_tax > 0
    )
    amount = display_amount if show_taxable else invoice.invoice_amount

    items_part = (
        f"{item_count} item{'s' if item_count != 1 else ''}: {items_text}"
        if item_count
        else f"Items: {items_text}"
    )
    caption_lines = [f"{invoice.invoice_date} · {items_part}"]
    if invoice.discount_amount > 0:
        caption_lines.append(f"Discount ₹{invoice.discount_amount:,.0f}")
    if invoice.is_generated and invoice.total_tax > 0:
        caption_lines.append(f"GST ₹{invoice.total_tax:,.0f}")

    actions = []
    if pdf_bytes:
        actions.append(
            CardAction(
                "Download PDF",
                key=f"dl_inv_pdf_{invoice.id}",
                download_data=pdf_bytes,
                download_file_name=f"{invoice.invoice_number}.pdf",
                download_mime="application/pdf",
            )
        )
    if edit:

        def _on_edit() -> None:
            if edit.before_edit:
                edit.before_edit()
            if edit.clear_dialogs:
                clear_all_dialog_flags()
            st.session_state[edit.flag_key] = invoice.id
            if edit.register_dialog:
                register_armed_dialog(edit.flag_key)
            st.rerun()

        actions.append(CardAction("Edit", key=edit.button_key, on_click=_on_edit))

    with st.container(border=True):
        card(
            invoice.invoice_number,
            amount=f"₹{amount:,.0f}",
            badges=[
                show_taxable and (f"Taxable ₹{invoice.net_amount:,.0f}", "gray"),
                invoice.is_generated and ("Generated", "green"),
                invoice.is_cancellation and ("Cancellation", "orange"),
                posted and ("Posted", "blue"),
            ],
            caption_lines=caption_lines,
            footer_badges=[
                (f"Margin ₹{invoice.margin_amount:,.0f}", "violet"),
                (
                    f"MPH ₹{invoice.margin_per_hour:,.0f}/h"
                    if invoice.margin_per_hour is not None
                    else "MPH —",
                    "gray",
                ),
            ],
            actions=actions,
        )


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
