from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.ui.components.voucher_form import voucher_form

CREATE_ACC = "acc_create_dialog"
EDIT_ACC = "acc_edit_dialog"
LEDGER_ACC = "acc_ledger_dialog"

ACCOUNTS_PAGE_SIZE = 12  # 4 rows of 3 cards
RCPT = "acc_receipt_dialog"
PAY = "acc_payment_dialog"
SAL = "acc_salary_dialog"
JOURNAL = "acc_journal_dialog"


def _format_balance(balance: float) -> str:
    """Show a balance as an absolute value tagged with its nature (Dr/Cr)."""
    if abs(balance) < 0.01:
        return "₹0.00"
    nature = "Dr" if balance > 0 else "Cr"
    return f"₹{abs(balance):,.2f} {nature}"


def _index_of(options: dict, target_id, default: int = 0) -> int:
    ids = list(options.values())
    return ids.index(target_id) if target_id in ids else default


def _fmt_date(value) -> str:
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)


def _voucher_matches(voucher, query: str) -> bool:
    """Match a voucher against a free-text query on account name, number or notes."""
    if not query:
        return True
    if query in (voucher.voucher_number or "").lower():
        return True
    if query in (voucher.description or "").lower():
        return True
    return any(query in (ln.account_name or "").lower() for ln in voucher.lines)


# --- dialogs -----------------------------------------------------------------
@st.dialog("Create Account")
def _create_account_dialog(accounting_service):
    name = st.text_input("Account Name")
    acc_type = st.selectbox("Account Type", [t.value for t in AccountType])
    is_store = st.checkbox(
        "Store account (available for receipts, payments & order advances)",
        value=False,
    )
    is_salary = st.checkbox(
        "Salary account (available for salary payments)",
        value=False,
    )
    opening = st.number_input("Opening Balance", value=0.0)
    cols = st.columns(2)
    if cols[0].button("Create", type="primary", use_container_width=True):
        if not name.strip():
            st.error("Account name is required")
        else:
            try:
                accounting_service.create_account(
                    name, acc_type, opening, is_store, is_salary
                )
                st.session_state.pop(CREATE_ACC, None)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(CREATE_ACC, None)
        st.rerun()


@st.dialog("Edit Account")
def _edit_account_dialog(accounting_service):
    account = accounting_service.get_account(st.session_state.get(EDIT_ACC))
    if not account:
        st.error("Account not found")
        if st.button("Close"):
            st.session_state.pop(EDIT_ACC, None)
            st.rerun()
        return

    protected = accounting_service.is_protected_account(account)
    if protected:
        st.caption(
            f"“{account.account_name}” is used by invoice/discount posting — "
            "its name and type are locked."
        )

    types = [t.value for t in AccountType]
    name = st.text_input("Account Name", value=account.account_name, disabled=protected)
    acc_type = st.selectbox(
        "Account Type", types,
        index=types.index(account.account_type.value),
        disabled=protected,
    )
    is_store = st.checkbox(
        "Store account (available for receipts, payments & order advances)",
        value=account.is_store_account,
    )
    is_salary = st.checkbox(
        "Salary account (available for salary payments)",
        value=account.is_salary_account,
    )

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            accounting_service.update_account(
                account.id, name, acc_type, is_store, is_salary
            )
            st.session_state.pop(EDIT_ACC, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(EDIT_ACC, None)
        st.rerun()


@st.dialog("Account Ledger", width="large")
def _ledger_dialog(accounting_service):
    account = accounting_service.get_account(st.session_state.get(LEDGER_ACC))
    if not account:
        st.error("Account not found")
        return
    st.markdown(f"**{account.account_name}** ({account.account_type.value})")
    st.caption(f"Current balance: {_format_balance(account.current_balance)}")

    ledger = sorted(
        accounting_service.get_account_ledger(account.id),
        key=lambda e: e["voucher_date"],
    )
    if not ledger:
        st.info("No transactions for this account yet.")
    else:
        running = round(account.opening_balance, 2)
        rows = []
        for e in ledger:
            running = round(running + e["debit"] - e["credit"], 2)
            rows.append(
                {
                    "Date": _fmt_date(e["voucher_date"]),
                    "Voucher": e["voucher_number"],
                    "Debit": e["debit"],
                    "Credit": e["credit"],
                    "Balance": _format_balance(running),
                    "Description": e["description"],
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if st.button("Close"):
        st.session_state.pop(LEDGER_ACC, None)
        st.rerun()


@st.dialog("Record Receipt")
def _receipt_dialog(accounting_service):
    target = st.session_state.get(RCPT)
    voucher = None if target in (None, "new") else accounting_service.get_voucher(target)

    store_accounts = accounting_service.get_store_accounts()
    customers = [a for a in accounting_service.list_accounts() if a.linked_customer_id]
    if not store_accounts or not customers:
        st.error("Need at least one store account and one customer account.")
        if st.button("Close"):
            st.session_state.pop(RCPT, None)
            st.rerun()
        return

    recv_opts = {a.account_name: a.id for a in store_accounts}
    cust_opts = {a.account_name: a.id for a in customers}
    existing_recv = voucher.lines[0].account_id if voucher else None
    existing_cust = voucher.lines[1].account_id if voucher else None
    existing_amt = voucher.lines[0].debit_amount if voucher else 0.0

    recv = st.selectbox(
        "Receiving Account (Store)", list(recv_opts.keys()),
        index=_index_of(recv_opts, existing_recv),
    )
    cust = st.selectbox(
        "Customer Account", list(cust_opts.keys()),
        index=_index_of(cust_opts, existing_cust),
    )
    amount = st.number_input("Amount", min_value=0.0, value=float(existing_amt))
    v_date = st.date_input("Date", value=date.today())
    desc = st.text_input("Description", value=voucher.description if voucher else "")

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if voucher:
                accounting_service.update_receipt(
                    voucher.id, recv_opts[recv], cust_opts[cust], amount, desc, v_date
                )
            else:
                accounting_service.create_receipt(
                    recv_opts[recv], cust_opts[cust], amount, desc, v_date
                )
            st.session_state.pop(RCPT, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(RCPT, None)
        st.rerun()


@st.dialog("Record Vendor Payment")
def _payment_dialog(services):
    accounting_service = services["accounting"]
    vendor_service = services["vendors"]
    service_config = services["vendor_services"]

    target = st.session_state.get(PAY)
    voucher = None if target in (None, "new") else accounting_service.get_voucher(target)

    store_accounts = accounting_service.get_store_accounts()
    service_list = service_config.list_services(active_only=True)
    vendors = vendor_service.list_all_vendors()
    if not store_accounts or not service_list or not vendors:
        st.error(
            "Need at least one vendor, one store account and one configured "
            "service (see Vendors and Service Configuration)."
        )
        if st.button("Close"):
            st.session_state.pop(PAY, None)
            st.rerun()
        return

    # Map each vendor to its liability account so payments post correctly.
    vendor_by_account = {}
    vendor_opts = {}
    for v in vendors:
        acc = accounting_service.get_vendor_account(v.id)
        if acc:
            vendor_opts[v.vendor_name] = acc.id
            vendor_by_account[acc.id] = v

    pay_opts = {a.account_name: a.id for a in store_accounts}
    svc_opts = {s.service_name: s for s in service_list}

    # Vendor payment lines: [expense Dr, vendor Cr, vendor Dr, paying Cr].
    existing_vendor = voucher.lines[1].account_id if voucher else None
    existing_pay = voucher.lines[3].account_id if voucher else None
    existing_amt = voucher.lines[0].debit_amount if voucher else 0.0
    existing_service = voucher.reference_service_id if voucher else None
    svc_default = 0
    if existing_service and existing_service in {s.id for s in service_list}:
        svc_default = next(
            i for i, s in enumerate(service_list) if s.id == existing_service
        )

    vendor_name = st.selectbox(
        "Vendor", list(vendor_opts.keys()),
        index=_index_of(vendor_opts, existing_vendor),
    )
    service_name = st.selectbox(
        "Service / Material", list(svc_opts.keys()), index=svc_default
    )
    pay = st.selectbox(
        "Paying Account (Store)", list(pay_opts.keys()),
        index=_index_of(pay_opts, existing_pay),
    )
    amount = st.number_input("Amount", min_value=0.0, value=float(existing_amt))
    v_date = st.date_input("Date", value=date.today())
    desc = st.text_input("Description", value=voucher.description if voucher else "")

    selected_service = svc_opts[service_name]

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if voucher:
                accounting_service.update_vendor_payment(
                    voucher.id, vendor_opts[vendor_name],
                    selected_service.expense_account_id, pay_opts[pay], amount,
                    desc, v_date, service_id=selected_service.id,
                )
            else:
                accounting_service.create_vendor_payment(
                    vendor_opts[vendor_name], selected_service.expense_account_id,
                    pay_opts[pay], amount, desc, v_date,
                    service_id=selected_service.id,
                )
            st.session_state.pop(PAY, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(PAY, None)
        st.rerun()


@st.dialog("Record Salary")
def _salary_dialog(accounting_service):
    target = st.session_state.get(SAL)
    voucher = None if target in (None, "new") else accounting_service.get_voucher(target)

    store_accounts = accounting_service.get_store_accounts()
    salary_accounts = accounting_service.get_salary_accounts()
    expense = accounting_service.get_salary_expense_account()
    if not store_accounts or not salary_accounts or not expense:
        st.error(
            "Need a store account, at least one salary account, and a "
            "'Salary Expense' account. Flag an account as a salary account first."
        )
        if st.button("Close"):
            st.session_state.pop(SAL, None)
            st.rerun()
        return

    sal_opts = {a.account_name: a.id for a in salary_accounts}
    pay_opts = {a.account_name: a.id for a in store_accounts}
    # Salary payment lines: [expense Dr, salary Cr, salary Dr, paying Cr].
    existing_sal = voucher.lines[1].account_id if voucher else None
    existing_pay = voucher.lines[3].account_id if voucher else None
    existing_amt = voucher.lines[0].debit_amount if voucher else 0.0

    salary_name = st.selectbox(
        "Salary Account", list(sal_opts.keys()),
        index=_index_of(sal_opts, existing_sal),
    )
    pay = st.selectbox(
        "Paying Account (Store)", list(pay_opts.keys()),
        index=_index_of(pay_opts, existing_pay),
    )
    st.caption(f"Expense posts to **{expense.account_name}**")
    amount = st.number_input("Amount", min_value=0.0, value=float(existing_amt))
    v_date = st.date_input("Date", value=date.today())
    desc = st.text_input("Description", value=voucher.description if voucher else "")

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if voucher:
                accounting_service.update_salary_payment(
                    voucher.id, sal_opts[salary_name], pay_opts[pay],
                    amount, desc, v_date,
                )
            else:
                accounting_service.create_salary_payment(
                    sal_opts[salary_name], pay_opts[pay], amount, desc, v_date,
                )
            st.session_state.pop(SAL, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(SAL, None)
        st.rerun()


@st.dialog("New Journal Entry", width="large")
def _journal_dialog(accounting_service):
    accounts = accounting_service.list_accounts()
    desc = st.text_input("Journal Description", key="acc_jrnl_desc")
    lines, balanced = voucher_form(accounts, key_prefix="acc_jrnl")

    cols = st.columns(2)
    if cols[0].button(
        "Save", type="primary", use_container_width=True, disabled=not balanced
    ):
        try:
            accounting_service.create_journal_entry(desc, lines)
            st.session_state.pop("acc_jrnl_lines", None)
            st.session_state.pop(JOURNAL, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop("acc_jrnl_lines", None)
        st.session_state.pop(JOURNAL, None)
        st.rerun()


# --- tabs --------------------------------------------------------------------
def _render_accounts_tab(accounting_service):
    if st.button("+ Create Account", type="primary", key="btn_create_acc"):
        st.session_state[CREATE_ACC] = True
        st.rerun()

    query = st.text_input(
        "Search accounts", key="acc_search_accounts",
        placeholder="Account name or type",
    ).strip().lower()

    # Reset to the first page whenever the filter changes.
    if st.session_state.get("acc_last_query") != query:
        st.session_state["acc_page"] = 0
        st.session_state["acc_last_query"] = query

    accounts = accounting_service.list_accounts(active_only=False)
    if not accounts:
        st.caption("No accounts yet.")
        return
    if query:
        accounts = [
            a for a in accounts
            if query in a.account_name.lower() or query in a.account_type.value.lower()
        ]
    if not accounts:
        st.caption("No matching accounts.")
        return

    total_pages = (len(accounts) + ACCOUNTS_PAGE_SIZE - 1) // ACCOUNTS_PAGE_SIZE
    page = min(st.session_state.get("acc_page", 0), total_pages - 1)
    st.session_state["acc_page"] = page
    page_accounts = accounts[page * ACCOUNTS_PAGE_SIZE : (page + 1) * ACCOUNTS_PAGE_SIZE]

    cols = st.columns(3)
    for i, acc in enumerate(page_accounts):
        with cols[i % 3].container(border=True):
            store_tag = " · Store" if acc.is_store_account else ""
            st.markdown(f"**{acc.account_name}**")
            st.caption(f"{acc.account_type.value}{store_tag}")
            st.metric("Balance", _format_balance(acc.current_balance))
            btns = st.columns(2)
            if btns[0].button("View Ledger", key=f"ledger_{acc.id}", use_container_width=True):
                st.session_state[LEDGER_ACC] = acc.id
                st.rerun()
            if btns[1].button("Edit", key=f"edit_acc_{acc.id}", use_container_width=True):
                st.session_state[EDIT_ACC] = acc.id
                st.rerun()

    if total_pages > 1:
        prev_c, mid_c, next_c = st.columns([1, 2, 1])
        if prev_c.button("← Prev", disabled=page == 0, use_container_width=True, key="acc_prev"):
            st.session_state["acc_page"] = page - 1
            st.rerun()
        mid_c.markdown(
            f"<div style='text-align:center'>Page {page + 1} of {total_pages} "
            f"· {len(accounts)} accounts</div>",
            unsafe_allow_html=True,
        )
        if next_c.button(
            "Next →", disabled=page == total_pages - 1, use_container_width=True, key="acc_next"
        ):
            st.session_state["acc_page"] = page + 1
            st.rerun()


def _render_voucher_list(vouchers, flag_key, edit_prefix, query=""):
    vouchers = [v for v in vouchers if _voucher_matches(v, query)]
    if not vouchers:
        st.caption("No matching entries." if query else "Nothing recorded yet.")
        return
    for v in sorted(vouchers, key=lambda x: x.voucher_date, reverse=True):
        amount = v.total_debit
        with st.container(border=True):
            st.markdown(f"**{v.voucher_number}** — ₹{amount:,.0f}")
            st.caption(f"{_fmt_date(v.voucher_date)} | {v.description or '—'}")
            if st.button("Edit", key=f"{edit_prefix}_{v.id}"):
                st.session_state[flag_key] = v.id
                st.rerun()


def _render_receipts_tab(accounting_service):
    if st.button("+ Record Receipt", type="primary", key="btn_rec_rcpt"):
        st.session_state[RCPT] = "new"
        st.rerun()
    query = st.text_input(
        "Search by account", key="rcpt_search",
        placeholder="Account name, voucher no. or notes",
    ).strip().lower()
    _render_voucher_list(
        accounting_service.list_vouchers_by_type(VoucherType.RECEIPT),
        RCPT, "edit_rcpt", query=query,
    )


def _render_payments_tab(services):
    accounting_service = services["accounting"]
    service_config = services["vendor_services"]
    btns = st.columns(2)
    if btns[0].button("+ Record Vendor Payment", type="primary", key="btn_rec_pay"):
        st.session_state[PAY] = "new"
        st.rerun()
    if btns[1].button("+ Record Salary", type="primary", key="btn_rec_sal"):
        st.session_state[SAL] = "new"
        st.rerun()
    query = st.text_input(
        "Search by vendor, service or account", key="pay_search",
        placeholder="Vendor, service, voucher no. or notes",
    ).strip().lower()

    service_names = {
        s.id: s.service_name for s in service_config.list_services(active_only=False)
    }
    payments = accounting_service.list_vouchers_by_type(VoucherType.VENDOR_PAYMENT)
    salaries = accounting_service.list_vouchers_by_type(VoucherType.SALARY_PAYMENT)
    combined = [
        v
        for v in payments + salaries
        if _voucher_matches(v, query)
        or query in (service_names.get(v.reference_service_id, "")).lower()
    ]
    if not combined:
        st.caption("No matching payments." if query else "No payments recorded yet.")
        return
    for v in sorted(combined, key=lambda x: x.voucher_date, reverse=True):
        # Both types share line order: [expense Dr, party Cr, party Dr, paying Cr].
        amount = v.lines[0].debit_amount if v.lines else 0.0
        party_name = v.lines[1].account_name if len(v.lines) > 1 else "—"
        is_salary = v.voucher_type == VoucherType.SALARY_PAYMENT
        flag_key = SAL if is_salary else PAY
        edit_prefix = "edit_sal" if is_salary else "edit_pay"
        tag = "Salary" if is_salary else "Vendor Payment"
        service_label = None if is_salary else service_names.get(v.reference_service_id)
        with st.container(border=True):
            st.markdown(f"**{v.voucher_number}** — ₹{amount:,.0f}  ·  _{tag}_")
            st.caption(f"{'Account' if is_salary else 'Vendor'}: {party_name}")
            if service_label:
                st.caption(f"Service: {service_label}")
            st.caption(f"{_fmt_date(v.voucher_date)} | {v.description or '—'}")
            if st.button("Edit", key=f"{edit_prefix}_{v.id}"):
                st.session_state[flag_key] = v.id
                st.rerun()


def _render_journal_tab(accounting_service):
    if st.button("+ New Journal Entry", type="primary", key="btn_new_jrnl"):
        st.session_state[JOURNAL] = True
        st.rerun()
    query = st.text_input(
        "Search by account", key="jrnl_search",
        placeholder="Account name, voucher no. or notes",
    ).strip().lower()
    journals = [
        v
        for v in accounting_service.list_vouchers_by_type(VoucherType.JOURNAL)
        if _voucher_matches(v, query)
    ]
    if not journals:
        st.caption("No matching entries." if query else "No journal entries yet.")
        return
    for v in sorted(journals, key=lambda x: x.voucher_date, reverse=True):
        with st.container(border=True):
            st.markdown(f"**{v.voucher_number}** — ₹{v.total_debit:,.0f}")
            st.caption(f"{_fmt_date(v.voucher_date)} | {v.description or '—'}")
            for line in v.lines:
                side = (
                    f"Dr ₹{line.debit_amount:,.0f}"
                    if line.debit_amount
                    else f"Cr ₹{line.credit_amount:,.0f}"
                )
                st.caption(f"• {line.account_name}: {side}")


def _render_trial_balance_tab(accounting_service):
    trial = accounting_service.get_trial_balance()
    if not trial:
        st.caption("No balances to show.")
        return

    query = st.text_input(
        "Search by account", key="tb_search", placeholder="Account name",
    ).strip().lower()
    if query:
        trial = [r for r in trial if query in r["account_name"].lower()]
    if not trial:
        st.caption("No matching accounts.")
        return

    total_debit = round(sum(r["debit"] for r in trial), 2)
    total_credit = round(sum(r["credit"] for r in trial), 2)
    balanced = abs(total_debit - total_credit) < 0.01

    cols = st.columns(3)
    cols[0].metric("Total Debit", f"₹{total_debit:,.2f}")
    cols[1].metric("Total Credit", f"₹{total_credit:,.2f}")
    cols[2].metric("Status", "Balanced ✓" if balanced else "Unbalanced ✗")

    category_order = [t.value for t in AccountType]
    rows = []
    for category in category_order:
        group = [r for r in trial if r["account_type"] == category]
        if not group:
            continue
        rows.append({"Account": f"— {category} —", "Debit": "", "Credit": ""})
        sub_debit = sub_credit = 0.0
        for r in group:
            sub_debit += r["debit"]
            sub_credit += r["credit"]
            rows.append(
                {
                    "Account": f"   {r['account_name']}",
                    "Debit": f"{r['debit']:,.2f}" if r["debit"] else "",
                    "Credit": f"{r['credit']:,.2f}" if r["credit"] else "",
                }
            )
        rows.append(
            {
                "Account": f"Subtotal — {category}",
                "Debit": f"{round(sub_debit, 2):,.2f}",
                "Credit": f"{round(sub_credit, 2):,.2f}",
            }
        )
    rows.append(
        {
            "Account": "TOTAL",
            "Debit": f"{total_debit:,.2f}",
            "Credit": f"{total_credit:,.2f}",
        }
    )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render(services: dict):
    st.title("Accounts")
    accounting_service = services["accounting"]

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Accounts", "Receipts", "Payments", "Journal", "Trial Balance"]
    )
    with tab1:
        _render_accounts_tab(accounting_service)
    with tab2:
        _render_receipts_tab(accounting_service)
    with tab3:
        _render_payments_tab(services)
    with tab4:
        _render_journal_tab(accounting_service)
    with tab5:
        _render_trial_balance_tab(accounting_service)

    # Popups opened at page top level (page is not itself a dialog).
    # Only one dialog may open per run, so this is a strict if/elif chain.
    if st.session_state.get(CREATE_ACC):
        _create_account_dialog(accounting_service)
    elif st.session_state.get(EDIT_ACC):
        _edit_account_dialog(accounting_service)
    elif st.session_state.get(LEDGER_ACC):
        _ledger_dialog(accounting_service)
    elif st.session_state.get(RCPT):
        _receipt_dialog(accounting_service)
    elif st.session_state.get(PAY):
        _payment_dialog(services)
    elif st.session_state.get(SAL):
        _salary_dialog(accounting_service)
    elif st.session_state.get(JOURNAL):
        _journal_dialog(accounting_service)
