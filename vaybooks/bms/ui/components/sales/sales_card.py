"""Read-only cards for store sales list rows."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.shared import CardAction, card
from vaybooks.bms.ui.styles import render_card_grid

_SALES_AMOUNT_COLOR = "var(--color-violet-text)"


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _customer_name(party_name: str) -> str:
    rest = (party_name or "").strip()
    if rest.startswith("Customer - "):
        rest = rest[len("Customer - ") :].strip()
    if " - " in rest:
        name, _phone = rest.rsplit(" - ", 1)
        return name.strip() or "Customer"
    return rest or "Customer"


def _payment_badge_tuple(balance: float) -> tuple[str, str]:
    if abs(balance) <= 0.01:
        return ("Paid", "green")
    if balance > 0:
        return ("Unpaid", "red")
    return ("Credit", "blue")


def _sales_card(row: dict, suffix: str) -> None:
    store_no = row.get("store_invoice_number") or "—"
    gross = float(row.get("gross") or 0)
    net = float(row.get("net") or gross)
    balance = float(row.get("outstanding") or 0)

    project_id = row.get("reference_project_id") or ""
    project_name = (row.get("project_name") or "").strip()
    if project_name:
        project_line = f"Project: {project_name}"
    elif project_id:
        project_line = f"Project: {project_id[:8]}…"
    else:
        project_line = ""

    sale_id = row.get("id")
    status_label = (row.get("payment_status_label") or "").strip()
    if status_label:
        outstanding = float(row.get("outstanding") or 0)
        collected = float(row.get("collected") or 0)
        if outstanding <= 0.01:
            badge = (status_label, "green")
        elif collected > 0.01:
            badge = (status_label, "orange")
        else:
            badge = (status_label, "red")
    else:
        badge = _payment_badge_tuple(balance)

    def _on_view() -> None:
        if sale_id:
            navigation.go_to_detail("sales_detail", sale_id)

    with st.container(border=True):
        card(
            store_no,
            amount=f"₹{net:,.0f}",
            amount_style=f"color:{_SALES_AMOUNT_COLOR}",
            badges=[badge],
            caption_lines=[
                _customer_name(row.get("party_name") or ""),
                project_line,
                _fmt_date(row.get("sale_date")),
            ],
            actions=(
                [
                    CardAction(
                        "View",
                        key=f"{suffix}_view_{sale_id}",
                        kind="secondary",
                        on_click=_on_view,
                    )
                ]
                if sale_id
                else []
            ),
        )


def sales_cards(rows: list[dict], *, suffix: str = "store_sales") -> None:
    render_card_grid(
        rows,
        lambda row, _i: _sales_card(row, suffix),
        suffix=suffix,
        card_min_width=240,
    )
