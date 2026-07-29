from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCommissionAgentError,
    ValidationError,
)
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.parties.commission_agent_form import (
    render_commission_agent_form,
)
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.list_schemas import COMMISSION_AGENTS
from vaybooks.bms.ui.styles import render_card_grid

A_ADD = "agent_add_dialog"
A_EDIT = "agent_edit_dialog"
A_PAY = "agent_pay_dialog"
A_PAY_AGENT_ID = "agent_pay_agent_id"
A_PAY_INVOICE_ID = "agent_pay_invoice_id"
A_PAY_AMOUNT = "agent_pay_amount"
A_DUP_ID = "agent_duplicate_existing_id"
SUBMIT_ADD = "submit_agent_add"
SUBMIT_EDIT = "submit_agent_edit"


def _open_add_agent() -> None:
    clear_all_dialog_flags()
    st.session_state.pop(A_DUP_ID, None)
    open_dialog(A_ADD, submit_key=SUBMIT_ADD, clear_others=False)
    mark_wired("agents.add", "list.primary", "dialog.save")


def _render_duplicate_warning(existing_agent_id: str, agent_service) -> None:
    existing = agent_service.get_agent_detail(existing_agent_id)
    label = existing.agent_name if existing else "existing agent"
    st.warning(f"A commission agent with this phone or GSTIN already exists: **{label}**")
    if st.button("Open existing agent", key="agent_open_existing", type="primary"):
        st.session_state.pop(A_ADD, None)
        st.session_state.pop(A_DUP_ID, None)
        navigation.go_to_detail("commission_agent_detail", existing_agent_id)
        st.rerun()


@st.dialog("Add Commission Agent", width="large", on_dismiss=make_dismiss_handler(A_ADD))
def _add_agent_dialog(agent_service):
    dup_id = st.session_state.get(A_DUP_ID)
    if dup_id:
        _render_duplicate_warning(dup_id, agent_service)

    agent_input = render_commission_agent_form("a_add")

    cols = st.columns(2)
    do_create = cols[0].button(
        "Create Agent", type="primary", width="stretch"
    ) or consume_submit(SUBMIT_ADD)
    if do_create:
        try:
            agent = agent_service.create_agent(agent_input)
            st.session_state.pop(A_ADD, None)
            st.session_state.pop(A_DUP_ID, None)
            st.success(f"Created commission agent: {agent.agent_name}")
            st.rerun()
        except DuplicateCommissionAgentError as exc:
            st.session_state[A_DUP_ID] = exc.existing_agent_id
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(A_ADD, None)
        st.session_state.pop(A_DUP_ID, None)
        st.rerun()


@st.dialog("Edit Commission Agent", width="large", on_dismiss=make_dismiss_handler(A_EDIT))
def _edit_agent_dialog(agent_service):
    agent = agent_service.get_agent_detail(st.session_state.get(A_EDIT))
    if not agent:
        st.error("Commission agent not found")
        return

    agent_input = render_commission_agent_form("a_edit", agent=agent)

    cols = st.columns(2)
    do_save = cols[0].button(
        "Save Changes", type="primary", width="stretch"
    ) or consume_submit(SUBMIT_EDIT)
    if do_save:
        try:
            agent_service.update_agent(agent.id, agent_input)
            st.session_state.pop(A_EDIT, None)
            st.success("Commission agent updated")
            st.rerun()
        except DuplicateCommissionAgentError as exc:
            st.warning(str(exc))
            if st.button("Open existing agent", key="agent_edit_open_existing"):
                st.session_state.pop(A_EDIT, None)
                navigation.go_to_detail("commission_agent_detail", exc.existing_agent_id)
                st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(A_EDIT, None)
        st.rerun()


def arm_pay_agent_dialog(
    agent_id: str,
    *,
    invoice_id: str | None = None,
    amount: float | None = None,
) -> None:
    clear_all_dialog_flags()
    st.session_state[A_PAY] = "new"
    st.session_state[A_PAY_AGENT_ID] = agent_id
    if invoice_id:
        st.session_state[A_PAY_INVOICE_ID] = invoice_id
    else:
        st.session_state.pop(A_PAY_INVOICE_ID, None)
    if amount is not None:
        st.session_state[A_PAY_AMOUNT] = float(amount)
    else:
        st.session_state.pop(A_PAY_AMOUNT, None)


@st.dialog(
    "Record Commission Payment",
    width="medium",
    on_dismiss=make_dismiss_handler(
        A_PAY, A_PAY_AGENT_ID, A_PAY_INVOICE_ID, A_PAY_AMOUNT
    ),
)
def _pay_agent_dialog(services, agent_id: str):
    accounting = services["accounting"]
    agent_service = services["commission_agents"]
    agent = agent_service.get_agent_detail(agent_id)
    agent_account = accounting.get_agent_account(agent_id) if agent else None
    if not agent or not agent_account:
        st.error("Commission agent account not found.")
        if st.button("Close"):
            st.session_state.pop(A_PAY, None)
            st.session_state.pop(A_PAY_AGENT_ID, None)
            st.session_state.pop(A_PAY_INVOICE_ID, None)
            st.session_state.pop(A_PAY_AMOUNT, None)
            st.rerun()
        return

    store_accounts = accounting.get_store_accounts()
    if not store_accounts:
        st.error("Need at least one cash/bank store account.")
        if st.button("Close"):
            st.session_state.pop(A_PAY, None)
            st.session_state.pop(A_PAY_AGENT_ID, None)
            st.session_state.pop(A_PAY_INVOICE_ID, None)
            st.session_state.pop(A_PAY_AMOUNT, None)
            st.rerun()
        return

    payable = abs(float(agent_account.current_balance or 0))
    preset_invoice = (st.session_state.get(A_PAY_INVOICE_ID) or "").strip()
    preset_amount = st.session_state.get(A_PAY_AMOUNT)
    default_amount = (
        float(preset_amount)
        if preset_amount is not None
        else (float(payable) if payable > 0 else 0.0)
    )
    st.caption(f"Agent: **{agent.agent_name}**")
    st.caption(f"Ledger: **{agent_account.account_name}** · Payable ₹{payable:,.2f}")

    store_accounts = accounting.get_store_accounts()
    pay_opts = {a.account_name: a.id for a in store_accounts}
    paying_name = st.selectbox("Paying Account (Store)", list(pay_opts.keys()))
    amount = st.number_input(
        "Amount",
        min_value=0.0,
        value=default_amount,
    )
    v_date = st.date_input("Date", value=date.today())
    desc = st.text_input(
        "Description",
        value=f"Commission payment — {agent.agent_name}",
    )
    invoice_ref = st.text_input(
        "Sales invoice voucher id (optional)",
        value=preset_invoice,
        help="Link this settlement to a sales invoice voucher id.",
    )

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", width="stretch"):
        try:
            accounting.create_commission_payment(
                agent_account.id,
                pay_opts[paying_name],
                amount,
                desc,
                v_date,
                reference_invoice_id=(invoice_ref or "").strip() or None,
            )
            st.session_state.pop(A_PAY, None)
            st.session_state.pop(A_PAY_AGENT_ID, None)
            st.session_state.pop(A_PAY_INVOICE_ID, None)
            st.session_state.pop(A_PAY_AMOUNT, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(A_PAY, None)
        st.session_state.pop(A_PAY_AGENT_ID, None)
        st.session_state.pop(A_PAY_INVOICE_ID, None)
        st.session_state.pop(A_PAY_AMOUNT, None)
        st.rerun()


def _load_agents(services, filters, sort):
    agents = services["commission_agents"].list_all_agents()
    accounting = services["accounting"]
    sales = services.get("sales")
    all_metrics = {}
    if sales is not None:
        try:
            all_metrics = sales.list_commission_agent_metrics() or {}
        except Exception:
            all_metrics = {}
    for agent in agents:
        try:
            account = accounting.get_agent_account(agent.id)
        except Exception:
            account = None
        setattr(agent, "current_balance", account.current_balance if account else 0.0)
        metrics = all_metrics.get(agent.id) or {}
        setattr(agent, "sales_volume", float(metrics.get("sales_volume") or 0))
        setattr(
            agent, "commission_accrued", float(metrics.get("commission_accrued") or 0)
        )
        setattr(agent, "commission_paid", float(metrics.get("commission_paid") or 0))
        setattr(agent, "return_volume", float(metrics.get("return_volume") or 0))
    return agents



def _render_cards(page_agents, services):
    def _render(agent, _i):
        with st.container(border=True):
            st.markdown(f"**{agent.agent_name}**")
            st.write(agent.phone_number)
            if agent.gstin:
                st.caption(f"GSTIN: {agent.gstin}")
            balance = getattr(agent, "current_balance", 0.0)
            sales_vol = getattr(agent, "sales_volume", 0.0)
            accrued = getattr(agent, "commission_accrued", 0.0)
            paid = getattr(agent, "commission_paid", 0.0)
            returns = getattr(agent, "return_volume", 0.0)
            st.caption(
                f"Sales: ₹{sales_vol:,.0f} · Returns: ₹{returns:,.0f} · "
                f"Accrued: ₹{accrued:,.0f} · Paid: ₹{paid:,.0f} · "
                f"Payable: ₹{abs(balance):,.0f}"
            )
            btns = st.columns(3)
            if btns[0].button("Edit", key=f"a_edit_{agent.id}", width="stretch"):
                clear_all_dialog_flags()
                open_dialog(
                    A_EDIT, submit_key=SUBMIT_EDIT, value=agent.id, clear_others=False
                )
                st.rerun()
            if btns[1].button("Pay", key=f"a_pay_{agent.id}", width="stretch"):
                arm_pay_agent_dialog(agent.id)
                st.rerun()
            if btns[2].button("View", key=f"a_view_{agent.id}", width="stretch"):
                navigation.go_to_detail("commission_agent_detail", agent.id)

    render_card_grid(page_agents, _render, suffix="agents")


def render(services: dict):
    mark_wired("agents.add", "list.primary", "list.filters.open", "list.sort.open")
    bar = render_list(
        COMMISSION_AGENTS,
        services=services,
        load_fn=_load_agents,
        card_renderer=_render_cards,
        primary_label="Add Commission Agent",
        primary_key="agents_add_btn",
        count_label="commission agents",
        empty_text="No commission agents found.",
        page_key_nav="commission_agents_list",
    )
    if bar["primary_clicked"]:
        _open_add_agent()
    if bar.get("view_nth"):
        navigation.go_to_detail("commission_agent_detail", bar["view_nth"])
    if bar.get("edit_nth"):
        clear_all_dialog_flags()
        open_dialog(
            A_EDIT, submit_key=SUBMIT_EDIT, value=bar["edit_nth"], clear_others=False
        )
        st.rerun()
    if st.session_state.get(A_ADD):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(A_ADD, SUBMIT_ADD)
        register_armed_dialog(A_ADD)
        _add_agent_dialog(services["commission_agents"])
    if st.session_state.get(A_EDIT):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(A_EDIT, SUBMIT_EDIT)
        register_armed_dialog(A_EDIT)
        _edit_agent_dialog(services["commission_agents"])
    if st.session_state.get(A_PAY):
        register_armed_dialog(A_PAY)
        agent_id = st.session_state.get(A_PAY_AGENT_ID) or ""
        if agent_id:
            _pay_agent_dialog(services, agent_id)
