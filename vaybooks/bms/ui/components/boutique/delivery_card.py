from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional, Sequence

import streamlit as st

from vaybooks.bms.domain.boutique.deliveries.entities import Delivery
from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags, register_armed_dialog
from vaybooks.bms.ui.styles import render_card_grid, status_badge


@dataclass(frozen=True)
class DeliveryEditAction:
    flag_key: str
    button_key: str
    clear_dialogs: bool = False
    register_dialog: bool = False
    before_edit: Optional[Callable[[], None]] = None


def _fmt_date(value: date) -> str:
    return value.strftime("%d %b %Y")


def _truncate(text: str, limit: int = 60) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _item_labels(order: CustomizationOrder, delivery: Delivery) -> list[str]:
    return [
        it.bill_number
        for bill_id in delivery.bill_ids
        if (it := order.get_item_by_id(bill_id))
    ]


def delivery_card(
    delivery: Delivery,
    order: CustomizationOrder,
    *,
    edit: DeliveryEditAction | None = None,
) -> None:
    item_labels = _item_labels(order, delivery)
    item_count = len(item_labels)
    items_text = ", ".join(item_labels) or "—"

    with st.container(border=True):
        st.markdown(
            f'<p class="z-card-title">{_fmt_date(delivery.delivery_date)}</p>',
            unsafe_allow_html=True,
        )
        if item_count:
            st.markdown(
                status_badge(
                    f"{item_count} item{'s' if item_count != 1 else ''}", "orange", compact=True
                ),
                unsafe_allow_html=True,
            )
        notes = _truncate(delivery.delivery_notes)
        if notes:
            st.caption(f"{items_text} · {notes}")
        else:
            st.caption(items_text)

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
            st.session_state[edit.flag_key] = delivery.id
            if edit.register_dialog:
                register_armed_dialog(edit.flag_key)
            st.rerun()


def delivery_cards(
    deliveries: Sequence[Delivery],
    order: CustomizationOrder,
    *,
    suffix: str,
    card_builder: Optional[Callable[[Delivery], dict]] = None,
    card_min_width: int = 240,
    **card_kwargs,
) -> None:
    def _render(delivery: Delivery, _index: int) -> None:
        kwargs = dict(card_kwargs)
        if card_builder:
            kwargs.update(card_builder(delivery))
        delivery_card(delivery, order, **kwargs)

    render_card_grid(
        deliveries,
        _render,
        suffix=suffix,
        card_min_width=card_min_width,
    )
