"""Read-only cards for purchase bills list."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.shared import CardAction, card
from vaybooks.bms.ui.styles import render_card_grid

_PURCHASE_COLOR = "var(--color-teal-text)"


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _payment_badge_tuple(outstanding: float) -> tuple[str, str | None]:
    return ("Credit", None) if outstanding > 0.01 else ("Paid", None)


def _purchase_card(row: dict, suffix: str) -> None:
    bill_no = row.get("vendor_bill_number") or row.get("voucher_number") or "—"
    total = float(row.get("total") or 0)
    outstanding = float(row.get("outstanding") or 0)
    vtype = row.get("voucher_type") or "Purchase Bill"

    def _on_view() -> None:
        navigation.go_to_detail("purchase_detail", row.get("id"))

    with st.container(border=True):
        card(
            bill_no,
            amount=f"₹{total:,.0f}",
            amount_style=f"color:{_PURCHASE_COLOR};font-weight:600;",
            badges=[_payment_badge_tuple(outstanding)],
            caption_lines=[row.get("vendor_name") or "Vendor", _fmt_date(row.get("bill_date")), vtype],
            actions=[
                CardAction(
                    "View",
                    key=f"purchase_view_{suffix}_{row.get('id')}",
                    kind="secondary",
                    on_click=_on_view,
                )
            ],
        )


def purchase_cards(rows: list[dict], suffix: str = "purchases") -> None:
    render_card_grid(rows, lambda row, _idx: _purchase_card(row, suffix), suffix=suffix)
