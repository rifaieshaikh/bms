"""Commission agent detail route — aligned with vendor/customer detail layout."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.shared import CardAction, card
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import open_dialog
from vaybooks.bms.ui.pages.parties.commission_agents import list as agent_list
from vaybooks.bms.ui.responsive import viewport_width
from vaybooks.bms.ui.styles import panel, render_card_grid, status_badge

RECENT_PAYMENT_LIMIT = 10
_COMMISSION_AMOUNT_COLOR = "var(--color-violet-text)"


def _balance_status(balance: float) -> tuple[str, str]:
    if abs(balance) < 0.01:
        return "Settled", "gray"
    if balance < 0:
        return "Amount Payable", "red"
    return "Agent Advance", "green"


def _money(value: float, *, whole: bool = False) -> str:
    if whole:
        return f"₹{float(value or 0):,.0f}"
    return f"₹{float(value or 0):,.2f}"


def _format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %Y")
    return str(value)


def _summary_metric_cols(width: int) -> int:
    if width >= 1100:
        return 4
    if width >= 700:
        return 2
    return 1


def _inject_page_css() -> None:
    st.markdown(
        """
        <style>
          div[class*="st-key-agent_view_shell"] {
            max-width: 1480px;
            margin-left: auto;
            margin-right: auto;
            padding-left: 28px;
            padding-right: 28px;
          }
          @media (max-width: 1100px) {
            div[class*="st-key-agent_view_shell"] {
              padding-left: 22px;
              padding-right: 22px;
            }
          }
          @media (max-width: 700px) {
            div[class*="st-key-agent_view_shell"] {
              padding-left: 16px;
              padding-right: 16px;
            }
          }
          div[class*="st-key-agent_view_shell"] div[data-testid="stMetric"] {
            height: 100%;
          }
          div[class*="st-key-agent_bal_card"]
            div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.85rem 1rem 0.75rem;
            height: 100%;
          }
          div[class*="st-key-agent_bal_card"] .agent-bal-label {
            font-size: 0.875rem;
            color: var(--color-text-faint);
            margin-bottom: 0.15rem;
          }
          div[class*="st-key-agent_bal_card"] .agent-bal-value {
            font-size: 1.75rem;
            font-weight: 600;
            line-height: 1.25;
            margin: 0 0 0.4rem 0;
          }
          div[class*="st-key-agent_qa"]
            div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.4rem 0.75rem;
          }
          div[class*="st-key-agent_qa"] div.stButton > button,
          div[class*="st-key-agent_hdr"] div.stButton > button,
          div[class*="st-key-agent_pay_sec"] div.stButton > button {
            height: 36px;
            min-height: 36px;
            padding: 0.2rem 0.7rem;
            white-space: nowrap;
            width: auto !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _payable_balance_card(
    amount_label: str,
    amount_value: str,
    status_label: str,
    status_color: str,
) -> None:
    with st.container(key="agent_bal_card", border=True):
        st.markdown(
            f'<div class="agent-bal-label">{amount_label}</div>'
            f'<p class="agent-bal-value">{amount_value}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            status_badge(status_label, status_color, compact=True),
            unsafe_allow_html=True,
        )


def _info_card(agent, account) -> None:
    with panel(f"agent_head_{agent.id}"):
        with st.container(border=True):
            row1 = st.columns(3)
            row1[0].write(f"**Phone:** {agent.phone_number}")
            row1[1].write(f"**Contact:** {agent.contact_person or '—'}")
            row1[2].write(
                f"**Ledger:** {account.account_name if account else '—'}"
            )
            row2 = st.columns(3)
            profile = agent.commission_profile
            sales_n = len(getattr(profile, "sales_rules", None) or [])
            coll_n = len(getattr(profile, "collection_rules", None) or [])
            row2[0].write(f"**Sales rules:** {sales_n}")
            row2[1].write(f"**Collection rules:** {coll_n}")
            row2[2].write(f"**Email:** {agent.email or '—'}")
            if agent.formatted_address:
                st.caption(f"Address: {agent.formatted_address}")
            bits = []
            if agent.gstin:
                bits.append(f"GSTIN: {agent.gstin}")
            if agent.source_customer_id:
                bits.append(f"Linked customer: `{agent.source_customer_id}`")
            if bits:
                st.caption(" · ".join(bits))


def _quick_actions_section(agent, *, can_pay: bool) -> None:
    width = viewport_width()
    desktop = width >= 700

    with st.container(key="agent_qa", border=True):
        if desktop:
            label_col, actions_col = st.columns(
                [1.4, 3.6], vertical_alignment="center"
            )
            with label_col:
                st.markdown("**Quick Actions**")
            with actions_col:
                b1, b2 = st.columns(2, gap="small")
                _render_quick_action_buttons(agent, can_pay=can_pay, cols=(b1, b2))
        else:
            st.markdown("**Quick Actions**")
            b1, b2 = st.columns(2, gap="small")
            _render_quick_action_buttons(agent, can_pay=can_pay, cols=(b1, b2))


def _render_quick_action_buttons(agent, *, can_pay: bool, cols) -> None:
    b1, b2 = cols
    if b1.button(
        ":material/edit: Edit Agent",
        key="agent_qa_edit",
        help="Edit this commission agent",
    ):
        clear_all_dialog_flags()
        open_dialog(
            agent_list.A_EDIT,
            submit_key=agent_list.SUBMIT_EDIT,
            value=agent.id,
            clear_others=False,
        )
        st.rerun()
    if can_pay and b2.button(
        ":material/payments: Record Commission",
        key="agent_qa_pay",
        type="primary",
        help="Record a commission payment for this agent",
    ):
        agent_list.arm_pay_agent_dialog(agent.id)
        st.rerun()


def _invoice_payment_badge(row: dict) -> tuple[str, str]:
    status_label = (row.get("payment_status_label") or "").strip() or "Unpaid"
    outstanding = float(row.get("outstanding") or 0)
    collected = float(row.get("collected") or 0)
    if outstanding <= 0.01:
        return (status_label, "green")
    if collected > 0.01:
        return (status_label, "orange")
    return (status_label, "red")


def _customer_name(party_name: str) -> str:
    rest = (party_name or "").strip()
    if rest.startswith("Customer - "):
        rest = rest[len("Customer - ") :].strip()
    if " - " in rest:
        name, _phone = rest.rsplit(" - ", 1)
        return name.strip() or "Customer"
    return rest or ""


def _unpaid_commission_card(row: dict, *, agent_id: str, can_pay: bool, suffix: str) -> None:
    invoice_id = row.get("invoice_id") or ""
    inv_label = (
        row.get("store_invoice_number")
        or row.get("voucher_number")
        or invoice_id
        or "—"
    )
    unpaid = float(row.get("unpaid_amount") or 0)
    accrued = float(row.get("commission_amount") or 0)
    settled = float(row.get("commission_settled") or 0)
    reversed_amt = float(row.get("commission_reversed") or 0)
    sales_amount = float(row.get("sales_amount") or 0)
    collected = float(row.get("collected") or 0)
    outstanding = float(row.get("outstanding") or 0)

    rate = row.get("commission_rate")
    ctype = (row.get("commission_type") or "").lower()
    rate_label = (
        f"{float(rate):g}%"
        if ctype == "percentage" and rate is not None
        else (_money(rate) if rate is not None else "—")
    )
    customer = _customer_name(row.get("party_name") or "")

    def _on_view() -> None:
        if invoice_id:
            navigation.go_to_detail("sales_detail", invoice_id)

    def _on_pay() -> None:
        agent_list.arm_pay_agent_dialog(
            agent_id,
            invoice_id=invoice_id,
            amount=unpaid,
        )
        st.rerun()

    actions = [
        CardAction(
            "View",
            key=f"{suffix}_view_{invoice_id}",
            kind="secondary",
            on_click=_on_view,
        )
    ]
    if can_pay:
        actions.append(
            CardAction(
                "Pay",
                key=f"{suffix}_pay_{invoice_id}",
                kind="primary",
                on_click=_on_pay,
            )
        )

    with st.container(border=True):
        card(
            inv_label,
            amount=_money(unpaid),
            amount_style=f"color:{_COMMISSION_AMOUNT_COLOR}",
            badges=[
                _invoice_payment_badge(row),
                ("Commission pending", "orange") if unpaid > 0.009 else ("Settled", "green"),
            ],
            caption_lines=[
                customer,
                _format_date(row.get("sale_date")),
                (
                    f"Sale {_money(sales_amount, whole=True)} · "
                    f"Collected {_money(collected, whole=True)} · "
                    f"Outstanding {_money(outstanding, whole=True)}"
                ),
                (
                    f"Commission {_money(accrued)} ({rate_label}) · "
                    f"Settled {_money(settled)} · "
                    f"Pending {_money(unpaid)}"
                ),
                (
                    f"Return clawback {_money(reversed_amt)}"
                    if reversed_amt > 0.009
                    else ""
                ),
            ],
            actions=actions,
        )


def _render_unpaid_section(
    unpaid_invoices: list[dict],
    *,
    agent_id: str,
    can_pay: bool,
    unpaid_total: float,
) -> None:
    with st.container(key="agent_unpaid_sec", border=True):
        st.subheader("Accrued unpaid commission")
        if not unpaid_invoices:
            st.markdown(
                "<div style='text-align:center;padding:1.25rem 0.5rem;"
                "color:var(--color-text-muted);'>"
                "No unpaid commission invoices for this agent.</div>",
                unsafe_allow_html=True,
            )
            return
        st.caption(
            f"{len(unpaid_invoices)} invoice(s) · total unpaid {_money(unpaid_total)}"
        )

        def _render(row, _i):
            _unpaid_commission_card(
                row,
                agent_id=agent_id,
                can_pay=can_pay,
                suffix=f"agent_unpaid_{agent_id}",
            )

        render_card_grid(unpaid_invoices, _render, suffix=f"agent_unpaid_{agent_id}")


def _payment_card(row: dict, *, suffix: str) -> None:
    voucher_id = row.get("id") or ""
    ref = (row.get("reference_invoice_id") or "").strip()

    actions = []
    if ref:
        actions.append(
            CardAction(
                "View invoice",
                key=f"{suffix}_inv_{voucher_id}",
                kind="secondary",
                on_click=lambda invoice_id=ref: navigation.go_to_detail(
                    "sales_detail", invoice_id
                ),
            )
        )

    with st.container(border=True):
        card(
            row.get("voucher_number") or "Payment",
            amount=_money(row.get("amount") or 0),
            amount_style=f"color:{_COMMISSION_AMOUNT_COLOR}",
            badges=[("Paid", "green")],
            caption_lines=[
                _format_date(row.get("voucher_date")),
                row.get("description") or "Commission payment",
                f"Invoice: {ref}" if ref else "",
            ],
            actions=actions,
        )


def _render_recent_payments(accounting, account) -> None:
    payments = [
        v
        for v in accounting.list_vouchers_by_type(VoucherType.COMMISSION_PAYMENT)
        if any(line.account_id == account.id for line in (v.lines or []))
    ]
    payments = sorted(payments, key=lambda v: v.voucher_date, reverse=True)[
        :RECENT_PAYMENT_LIMIT
    ]
    rows = []
    for voucher in payments:
        amt = next(
            (
                line.debit_amount
                for line in voucher.lines
                if line.account_id == account.id and line.debit_amount > 0
            ),
            0.0,
        )
        rows.append(
            {
                "id": voucher.id,
                "voucher_number": voucher.voucher_number,
                "voucher_date": voucher.voucher_date,
                "amount": amt,
                "description": voucher.description or "Commission payment",
                "reference_invoice_id": getattr(voucher, "reference_invoice_id", None)
                or "",
            }
        )

    with st.container(key="agent_pay_sec", border=True):
        st.subheader("Recent commission payments")
        if not rows:
            st.markdown(
                "<div style='text-align:center;padding:1.25rem 0.5rem;"
                "color:var(--color-text-muted);'>"
                "No commission payments recorded for this agent yet.</div>",
                unsafe_allow_html=True,
            )
            return

        def _render(row, _i):
            _payment_card(row, suffix=f"agent_pay_{account.id}")

        render_card_grid(rows, _render, suffix=f"agent_pay_{account.id}")


def render(services: dict):
    agent_id = navigation.current_detail_id("commission_agent_detail")
    agent_service = services["commission_agents"]
    accounting = services["accounting"]
    sales = services.get("sales")

    _inject_page_css()
    with st.container(key="agent_view_shell"):
        if st.button("← Commission Agents", key="agent_back"):
            navigation.go_to_list("commission_agents_list")
            return

        agent = agent_service.get_agent_detail(agent_id) if agent_id else None
        if not agent:
            st.error("Commission agent not found")
            return

        account = accounting.get_agent_account(agent.id)
        balance = account.current_balance if account else 0.0
        status_label, status_color = _balance_status(balance)

        metrics = {}
        unpaid_invoices: list[dict] = []
        if sales is not None:
            try:
                metrics = sales.get_commission_agent_metrics(agent.id) or {}
            except Exception:
                metrics = {}
            try:
                unpaid_invoices = (
                    sales.list_agent_commission_invoices(agent.id, unpaid_only=True)
                    or []
                )
            except Exception:
                unpaid_invoices = []

        unpaid_total = round(
            sum(float(row.get("unpaid_amount") or 0) for row in unpaid_invoices), 2
        )
        if unpaid_invoices:
            metrics["commission_unpaid"] = unpaid_total
            metrics["unpaid_invoice_count"] = len(unpaid_invoices)

        title_col, edit_col = st.columns([5, 1], vertical_alignment="center")
        with title_col:
            st.title(agent.agent_name)
            st.markdown(
                status_badge(status_label, status_color, compact=True),
                unsafe_allow_html=True,
            )
            st.caption(agent.phone_number)
        with edit_col:
            with st.container(key="agent_hdr"):
                if st.button(":material/edit: Edit Agent", key="agent_hdr_edit"):
                    clear_all_dialog_flags()
                    open_dialog(
                        agent_list.A_EDIT,
                        submit_key=agent_list.SUBMIT_EDIT,
                        value=agent.id,
                        clear_others=False,
                    )
                    st.rerun()

        _info_card(agent, account)

        width = viewport_width()
        n_metric_cols = _summary_metric_cols(width)
        summary_metrics = [
            (
                "Sales volume",
                _money(metrics.get("sales_volume", 0), whole=True),
                False,
            ),
            (
                "Return volume",
                _money(metrics.get("return_volume", 0), whole=True),
                False,
            ),
            (
                "Commission accrued",
                _money(metrics.get("commission_accrued", 0)),
                False,
            ),
            (
                "Unpaid commission",
                _money(metrics.get("commission_unpaid", unpaid_total)),
                False,
            ),
            (
                "Commission paid",
                _money(metrics.get("commission_paid", 0)),
                False,
            ),
            (
                "Payable balance",
                _money(abs(balance)),
                True,
            ),
        ]
        for row_start in range(0, len(summary_metrics), n_metric_cols):
            row = summary_metrics[row_start : row_start + n_metric_cols]
            cols = st.columns(len(row))
            for offset, (label, value, is_balance) in enumerate(row):
                with cols[offset]:
                    if is_balance:
                        _payable_balance_card(
                            label, value, status_label, status_color
                        )
                    else:
                        st.metric(label, value, border=True)

        if float(metrics.get("commission_reversed", 0) or 0) > 0.009:
            st.caption(
                f"Commission clawed back on returns: "
                f"{_money(metrics.get('commission_reversed', 0))} · "
                f"Net sales {_money(metrics.get('net_sales_volume', 0), whole=True)} · "
                f"{int(metrics.get('invoice_count', 0))} invoices · "
                f"{int(metrics.get('unpaid_invoice_count', len(unpaid_invoices)))} unpaid"
            )

        _quick_actions_section(agent, can_pay=bool(account))

        _render_unpaid_section(
            unpaid_invoices,
            agent_id=agent.id,
            can_pay=bool(account),
            unpaid_total=unpaid_total,
        )

        if account:
            _render_recent_payments(accounting, account)

    if st.session_state.get(agent_list.A_EDIT):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(agent_list.A_EDIT, agent_list.SUBMIT_EDIT)
        register_armed_dialog(agent_list.A_EDIT)
        agent_list._edit_agent_dialog(agent_service)
    if st.session_state.get(agent_list.A_PAY):
        register_armed_dialog(agent_list.A_PAY)
        pay_agent_id = st.session_state.get(agent_list.A_PAY_AGENT_ID) or agent.id
        agent_list._pay_agent_dialog(services, pay_agent_id)
