from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Optional, Sequence

import streamlit as st

from vaybooks.bms.domain.finance.accounting.entities import Voucher, VoucherLine
from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.shared import CardAction, card
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags, register_armed_dialog
from vaybooks.bms.ui.styles import render_card_grid


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _truncate(text: str, limit: int = 60) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def invoice_gross_amount(voucher: Voucher) -> float:
    """Gross invoice amount from voucher credit lines."""
    return max((line.credit_amount for line in voucher.lines), default=0.0)


def voucher_display_amount(voucher: Voucher) -> float:
    vtype = voucher.voucher_type
    if vtype in (
        VoucherType.VENDOR_PAYMENT,
        VoucherType.SALARY_PAYMENT,
        VoucherType.ADVANCE,
        VoucherType.RECEIPT,
        VoucherType.REFUND,
    ):
        return voucher.cash_movement_amount
    if vtype in (VoucherType.SALES_INVOICE, VoucherType.CUSTOMIZATION_INVOICE):
        return invoice_gross_amount(voucher)
    return voucher.total_debit


def voucher_type_label(voucher: Voucher, *, short: bool = False) -> str:
    vtype = voucher.voucher_type
    if short:
        short_map = {
            VoucherType.SALARY_PAYMENT: "Salary",
            VoucherType.VENDOR_PAYMENT: "Vendor",
            VoucherType.CUSTOMIZATION_INVOICE: "Custom",
            VoucherType.SALES_INVOICE: "Sales",
            VoucherType.PURCHASE_EXPENSE: "Expense",
        }
        if vtype in short_map:
            return short_map[vtype]
        value = vtype.value if hasattr(vtype, "value") else str(vtype)
        return value
    if vtype == VoucherType.ADVANCE:
        return "Advance"
    if vtype == VoucherType.RECEIPT:
        return "Receipt"
    if vtype == VoucherType.SALARY_PAYMENT:
        return "Salary"
    if vtype == VoucherType.VENDOR_PAYMENT:
        return "Vendor Payment"
    if vtype == VoucherType.CUSTOMIZATION_INVOICE:
        return "Customization"
    if vtype == VoucherType.SALES_INVOICE:
        return "Sales"
    value = vtype.value if hasattr(vtype, "value") else str(vtype)
    return value


def _party_redundant(party_name: str, description: str) -> bool:
    if not party_name or not description:
        return False
    party = party_name.strip().lower()
    desc = description.strip().lower()
    return party in desc


def _strip_vendor_prefix(account_name: str) -> str:
    prefix = "Vendor - "
    if account_name.startswith(prefix):
        return account_name[len(prefix) :]
    return account_name


def _party_display_name(voucher: Voucher, party_name: str) -> str:
    if voucher.voucher_type == VoucherType.VENDOR_PAYMENT:
        return _strip_vendor_prefix(party_name)
    return party_name


def voucher_amount_color(vtype: VoucherType) -> str:
    if vtype in (VoucherType.RECEIPT, VoucherType.ADVANCE):
        return "green"
    if vtype in (
        VoucherType.PAYMENT,
        VoucherType.REFUND,
        VoucherType.VENDOR_PAYMENT,
        VoucherType.SALARY_PAYMENT,
        VoucherType.PURCHASE_EXPENSE,
    ):
        return "red"
    if vtype in (
        VoucherType.JOURNAL,
        VoucherType.SALES_INVOICE,
        VoucherType.CUSTOMIZATION_INVOICE,
    ):
        return "violet"
    return "plum"


def voucher_type_color(vtype: VoucherType) -> str:
    if vtype == VoucherType.JOURNAL:
        return "blue"
    if vtype in (VoucherType.SALES_INVOICE, VoucherType.CUSTOMIZATION_INVOICE):
        return "violet"
    return "gray"


def voucher_default_party(voucher: Voucher) -> tuple[Optional[str], Optional[str]]:
    """Return (party_label, party_name) inferred from voucher lines."""
    if voucher.voucher_type in (VoucherType.VENDOR_PAYMENT, VoucherType.SALARY_PAYMENT):
        party_name = voucher.lines[1].account_name if len(voucher.lines) > 1 else None
        label = "Account" if voucher.voucher_type == VoucherType.SALARY_PAYMENT else "Vendor"
        return label, party_name
    if voucher.voucher_type in (VoucherType.RECEIPT, VoucherType.ADVANCE):
        customer_line = next(
            (
                line
                for line in voucher.lines
                if line.credit_amount > 0 and line.description == "Payment received"
            ),
            voucher.lines[1] if len(voucher.lines) > 1 else None,
        )
        if customer_line:
            label = "Customer"
            return label, customer_line.account_name
        return None, None
    if voucher.voucher_type == VoucherType.REFUND:
        if voucher.is_advance_refund:
            customer_line = next(
                (
                    line
                    for line in voucher.lines
                    if line.credit_amount > 0 and line.description == "Advance released"
                ),
                None,
            )
            if customer_line:
                return "Customer", customer_line.account_name
        else:
            customer_line = voucher.lines[0] if voucher.lines else None
            if customer_line and customer_line.debit_amount > 0:
                return "Customer", customer_line.account_name
        return None, None
    if voucher.voucher_type in (
        VoucherType.SALES_INVOICE,
        VoucherType.CUSTOMIZATION_INVOICE,
    ):
        customer_line = next(
            (
                line
                for line in voucher.lines
                if line.debit_amount > 0
                and line.description not in ("Advance applied", "Discount allowed")
                and "discount" not in line.account_name.lower()
            ),
            None,
        )
        if customer_line:
            return "Customer", customer_line.account_name
        advance_line = next(
            (line for line in voucher.lines if line.description == "Advance applied"),
            None,
        )
        if advance_line:
            return "Advance applied", f"₹{advance_line.debit_amount:,.0f}"
        return None, None
    return None, None


def voucher_receiving_account(voucher: Voucher) -> str | None:
    """Store/cash account that received funds (receipt/advance/sales debit line)."""
    if voucher.voucher_type in (VoucherType.RECEIPT, VoucherType.ADVANCE) and voucher.lines:
        return voucher.lines[0].account_name
    if voucher.voucher_type == VoucherType.SALES_INVOICE:
        for line in voucher.lines:
            if line.debit_amount > 0 and line.description == "Cash/Bank received":
                return line.account_name
    return None


def _journal_line_summary(lines: Sequence[VoucherLine], max_lines: int = 2) -> list[str]:
    rows = []
    for line in lines[:max_lines]:
        side = (
            f"Dr ₹{line.debit_amount:,.0f}"
            if line.debit_amount
            else f"Cr ₹{line.credit_amount:,.0f}"
        )
        rows.append(f"{line.account_name}: {side}")
    remaining = len(lines) - max_lines
    if remaining > 0:
        rows.append(f"+{remaining} more line(s)")
    return rows


def _journal_note(lines: Sequence[VoucherLine]) -> str | None:
    rows = _journal_line_summary(lines)
    return "<br>".join(rows) if rows else None


@dataclass(frozen=True)
class VoucherEditAction:
    flag_key: str
    button_key: str
    clear_dialogs: bool = False
    register_dialog: bool = False
    before_edit: Optional[Callable[[], None]] = None


_AMOUNT_TEXT_COLORS = {
    "green": "var(--color-success-text)",
    "red": "var(--color-danger-text)",
    "violet": "var(--color-violet-text)",
    "plum": "var(--color-primary)",
    "blue": "var(--color-info-text)",
    "gray": "var(--color-neutral-text)",
}


def voucher_card(
    voucher: Voucher,
    *,
    party_name: str | None = None,
    party_label: str | None = None,
    service_label: str | None = None,
    show_type_badge: bool = True,
    show_journal_lines: bool = False,
    show_order_linked: bool = True,
    edit: VoucherEditAction | None = None,
) -> None:
    amount = voucher_display_amount(voucher)
    vtype = voucher.voucher_type
    _, default_party = voucher_default_party(voucher)
    if party_name is None:
        party_name = default_party
    description = (voucher.description or "").strip()

    amount_color = voucher_amount_color(vtype)
    text_color = _AMOUNT_TEXT_COLORS.get(amount_color, "var(--color-text)")

    caption_lines = [_fmt_date(voucher.voucher_date)]
    if party_name and not _party_redundant(party_name, description):
        caption_lines.append(_party_display_name(voucher, party_name))

    receiving_account = voucher_receiving_account(voucher)
    link_label = "Order linked" if voucher.reference_order_id else "Not linked"
    link_color = "blue" if voucher.reference_order_id else "gray"

    note = (
        _journal_note(voucher.lines)
        if show_journal_lines and vtype == VoucherType.JOURNAL
        else None
    )

    actions = []
    if edit:

        def _on_edit() -> None:
            if edit.before_edit:
                edit.before_edit()
            if edit.clear_dialogs:
                clear_all_dialog_flags()
            st.session_state[edit.flag_key] = voucher.id
            if edit.register_dialog:
                register_armed_dialog(edit.flag_key)
            st.rerun()

        actions.append(CardAction("Edit", key=edit.button_key, on_click=_on_edit))

    with st.container(border=True):
        card(
            voucher.voucher_number,
            amount=f"₹{amount:,.0f}",
            amount_style=f"color:{text_color}",
            badges=[
                show_type_badge and (voucher_type_label(voucher, short=True), "blue"),
            ],
            caption_lines=caption_lines,
            note=note,
            footer_badges=[
                receiving_account and (receiving_account, "orange"),
                service_label and (service_label, "orange"),
                show_order_linked and (link_label, link_color),
            ],
            actions=actions,
        )


def voucher_cards(
    vouchers: Sequence[Voucher],
    *,
    suffix: str,
    card_min_width: int = 240,
    card_builder: Optional[Callable[[Voucher], dict]] = None,
    **card_kwargs,
) -> None:
    """Render vouchers in a responsive grid using ``voucher_card``."""

    def _render(voucher: Voucher, _index: int) -> None:
        kwargs = dict(card_kwargs)
        if card_builder:
            kwargs.update(card_builder(voucher))
        voucher_card(voucher, **kwargs)

    render_card_grid(
        vouchers,
        _render,
        suffix=suffix,
        card_min_width=card_min_width,
    )
