from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.voucher_card import invoice_gross_amount
from vaybooks.bms.ui.components.voucher_form import voucher_form
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    clear_dialog_flags,
    make_dismiss_handler,
)
from vaybooks.bms.ui.list_schemas import ACCOUNTS
from vaybooks.bms.ui.pagination import (
    CARD_PAGE_SIZE,
    TRIAL_BALANCE_PAGE_SIZE,
    paginate_list,
    render_page_controls,
)
from vaybooks.bms.ui.styles import render_card_grid

CREATE_ACC = "acc_create_dialog"
EDIT_ACC = "acc_edit_dialog"
LEDGER_ACC = "acc_ledger_dialog"

ACCOUNTS_PAGE_SIZE = CARD_PAGE_SIZE
RCPT = "acc_receipt_dialog"
PAY = "acc_payment_dialog"
SAL = "acc_salary_dialog"
INV_CUST = "acc_cust_inv_dialog"
JOURNAL = "acc_journal_dialog"


def _clear_other_invoice_dialog_flags(keep: str) -> None:
    """Only one invoice dialog may be armed; drop the sibling flag."""
    clear_dialog_flags(*(k for k in (INV_CUST,) if k != keep))


def _clear_other_payment_dialog_flags(keep: str) -> None:
    clear_dialog_flags(*(k for k in (PAY, SAL) if k != keep))


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


def _invoice_gross_amount(voucher) -> float:
    return invoice_gross_amount(voucher)


# --- dialogs -----------------------------------------------------------------
@st.dialog("Create Account", on_dismiss=make_dismiss_handler(CREATE_ACC))
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


@st.dialog("Edit Account", on_dismiss=make_dismiss_handler(EDIT_ACC))
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
        if account.is_store_account:
            st.warning(
                f'System blocks renaming or deleting "{account.account_name}" — '
                "it is a protected store account (cash drawer, bank, etc.)."
            )
        else:
            st.warning(
                f'System blocks renaming or retyping "{account.account_name}" — '
                "it is used by invoice/discount posting."
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


@st.dialog("Account Ledger", width="large", on_dismiss=make_dismiss_handler(LEDGER_ACC))
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


@st.dialog("Record Receipt", on_dismiss=make_dismiss_handler(RCPT))
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


@st.dialog("Record Vendor Payment", on_dismiss=make_dismiss_handler(PAY))
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


@st.dialog("Record Salary", on_dismiss=make_dismiss_handler(SAL))
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


def _invoice_discount_amount(voucher, discount_account_id: str | None) -> float:
    if not discount_account_id:
        return 0.0
    for line in voucher.lines:
        if line.account_id == discount_account_id and line.debit_amount > 0:
            return line.debit_amount
    return 0.0


@st.dialog(
    "Record Customization Invoice",
    width="large",
    on_dismiss=make_dismiss_handler(INV_CUST),
)
def _customization_invoice_dialog(accounting_service):
    _standalone_invoice_dialog(
        accounting_service,
        INV_CUST,
        VoucherType.CUSTOMIZATION_INVOICE,
        accounting_service.get_customization_account,
        "Customization",
    )


def _standalone_invoice_dialog(
    accounting_service,
    flag_key: str,
    voucher_type: VoucherType,
    income_account_getter,
    income_label: str,
):
    target = st.session_state.get(flag_key)
    voucher = None if target in (None, "new") else accounting_service.get_voucher(target)
    if voucher and voucher.voucher_type != voucher_type:
        st.error("This entry is not the expected invoice type.")
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return

    income_account = income_account_getter()
    customers = [a for a in accounting_service.list_accounts() if a.linked_customer_id]
    discount_account = accounting_service.get_discount_account()
    if not income_account:
        st.error(f'No "{income_label}" revenue account found.')
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return
    if not customers:
        st.error("Need at least one customer account.")
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return

    cust_opts = {a.account_name: a.id for a in customers}
    existing_cust = voucher.lines[0].account_id if voucher else None
    existing_gross = _invoice_gross_amount(voucher) if voucher else 0.0
    existing_discount = (
        _invoice_discount_amount(voucher, discount_account.id if discount_account else None)
        if voucher
        else 0.0
    )

    cust = st.selectbox(
        "Customer Account", list(cust_opts.keys()),
        index=_index_of(cust_opts, existing_cust),
    )
    amount = st.number_input("Invoice Amount (gross)", min_value=0.0, value=float(existing_gross))
    dcols = st.columns(2)
    discount_pct = dcols[0].number_input(
        "Discount %", min_value=0.0, max_value=100.0, value=0.0, step=1.0,
        key=f"{flag_key}_disc_pct",
    )
    manual_discount = dcols[1].number_input(
        "Discount Amount", min_value=0.0, value=float(existing_discount),
        key=f"{flag_key}_disc_amt",
    )
    if discount_pct > 0:
        discount_amount = round(amount * discount_pct / 100, 2)
    else:
        discount_amount = round(manual_discount, 2)
    discount_amount = min(discount_amount, amount)
    if discount_amount > 0:
        st.caption(
            f"Gross ₹{amount:,.0f} − Discount ₹{discount_amount:,.0f} = "
            f"**Net ₹{amount - discount_amount:,.0f}**"
        )

    v_date = st.date_input("Date", value=date.today())
    desc = st.text_input("Description", value=voucher.description if voucher else "")
    st.caption(f"Revenue credited to: **{income_account.account_name}**")
    if discount_amount > 0 and not discount_account:
        st.warning('No "Discount Allowed" account found for the discount debit.')

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            discount_id = discount_account.id if discount_amount > 0 and discount_account else None
            if voucher:
                accounting_service.update_sales_invoice(
                    voucher.id, cust_opts[cust], income_account.id, amount, desc, v_date,
                    discount_amount=discount_amount, discount_account_id=discount_id,
                )
            else:
                accounting_service.create_sales_invoice(
                    cust_opts[cust], income_account.id, amount, desc, v_date,
                    discount_amount=discount_amount, discount_account_id=discount_id,
                    voucher_type=voucher_type,
                )
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


@st.dialog("New Journal Entry", width="large", on_dismiss=make_dismiss_handler(JOURNAL))
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
        clear_all_dialog_flags()
        _create_account_dialog(accounting_service)

    query = st.text_input(
        "Search accounts", key="acc_search_accounts",
        placeholder="Account name or type",
    ).strip().lower()

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

    accounts = sorted(
        accounts,
        key=lambda a: (
            0 if a.account_name.strip().lower() == "cash drawer" else 1,
            a.account_name.lower(),
        ),
    )

    page_accounts, page, total_pages = paginate_list(
        accounts,
        page_key="acc_page",
        page_size=ACCOUNTS_PAGE_SIZE,
        filter_key="acc_search_accounts",
        filter_value=query,
    )

    cols = st.columns(3)
    for i, acc in enumerate(page_accounts):
        with cols[i % 3].container(border=True):
            store_tag = " · Store" if acc.is_store_account else ""
            st.markdown(f"**{acc.account_name}**")
            st.caption(f"{acc.account_type.value}{store_tag}")
            st.metric("Balance", _format_balance(acc.current_balance))

            protected = accounting_service.is_protected_account(acc)
            if protected:
                if acc.is_store_account:
                    st.markdown(
                        "Protected · DeleteDeactivate control — "
                        "Delete hidden for store accounts."
                    )
                else:
                    st.markdown(
                        "Protected · DeleteDeactivate control — "
                        "name and type locked."
                    )

            btns = st.columns(4 if not protected else 3)
            if btns[0].button("View Ledger", key=f"ledger_{acc.id}", use_container_width=True):
                st.session_state[LEDGER_ACC] = acc.id
                st.rerun()
            if btns[1].button("Edit", key=f"edit_acc_{acc.id}", use_container_width=True):
                st.session_state[EDIT_ACC] = acc.id
                st.rerun()
            action_col = 2
            if not protected:
                if btns[action_col].button(
                    "Delete", key=f"delete_acc_{acc.id}", use_container_width=True
                ):
                    try:
                        accounting_service.delete_account(acc.id)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                action_col = 3
            if btns[action_col].button(
                "Deactivate",
                key=f"deactivate_acc_{acc.id}",
                use_container_width=True,
                disabled=protected and acc.is_store_account,
            ):
                try:
                    accounting_service.deactivate_account(acc.id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    render_page_controls(
        page, total_pages, len(accounts),
        page_key="acc_page", prev_key="acc_prev", next_key="acc_next",
        label="accounts",
    )


def _render_ledger_tab(accounting_service):
    st.subheader("Ledger")
    accounts = accounting_service.list_accounts(active_only=False)
    if not accounts:
        st.caption("No accounts yet.")
        return

    accounts = sorted(
        accounts,
        key=lambda a: (
            0 if a.account_name.strip().lower() == "cash drawer" else 1,
            a.account_name.lower(),
        ),
    )
    acc_opts = {a.account_name: a.id for a in accounts}
    default_idx = next(
        (
            i
            for i, a in enumerate(accounts)
            if a.account_name.strip().lower() == "cash drawer"
        ),
        0,
    )
    selected_name = st.selectbox(
        "Account",
        list(acc_opts.keys()),
        index=default_idx,
        key="acc_ledger_select",
    )
    account_id = acc_opts[selected_name]
    account = accounting_service.get_account(account_id)
    if not account:
        st.error("Account not found")
        return

    st.caption(f"Current balance: {_format_balance(account.current_balance)}")

    trial = accounting_service.get_trial_balance()
    if trial:
        total_debit = round(sum(r["debit"] for r in trial), 2)
        total_credit = round(sum(r["credit"] for r in trial), 2)
        balanced = abs(total_debit - total_credit) < 0.01
        st.caption(
            f"Trial balance: ₹{total_debit:,.2f} Dr / ₹{total_credit:,.2f} Cr"
            + (" — Balanced ✓" if balanced else " — Unbalanced ✗")
        )

    ledger = sorted(
        accounting_service.get_account_ledger(account_id),
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

    page_trial, page, total_pages = paginate_list(
        trial,
        page_key="acc_tb_page",
        page_size=TRIAL_BALANCE_PAGE_SIZE,
        filter_key="tb_search",
        filter_value=query,
    )
    rows = [
        {
            "Account": r["account_name"],
            "Type": r["account_type"],
            "Debit": f"{r['debit']:,.2f}" if r["debit"] else "",
            "Credit": f"{r['credit']:,.2f}" if r["credit"] else "",
        }
        for r in page_trial
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    render_page_controls(
        page, total_pages, len(trial),
        page_key="acc_tb_page", prev_key="acc_tb_prev", next_key="acc_tb_next",
        label="accounts",
    )


def open_pending_dialogs(services: dict) -> None:
    """Shared dialog-opener for all Finance routes (single dialog per run)."""
    accounting_service = services["accounting"]
    if st.session_state.get(EDIT_ACC):
        _edit_account_dialog(accounting_service)
    elif st.session_state.get(RCPT):
        _receipt_dialog(accounting_service)
    elif st.session_state.get(PAY):
        _payment_dialog(services)
    elif st.session_state.get(SAL):
        _salary_dialog(accounting_service)
    elif st.session_state.get(INV_CUST):
        _customization_invoice_dialog(accounting_service)
    elif st.session_state.get(JOURNAL):
        _journal_dialog(accounting_service)


def _load_accounts(services, filters, sort):
    try:
        return services["accounting"].list_accounts(active_only=False)
    except Exception:
        return []


def _render_account_cards(page_accounts, services):
    accounting_service = services["accounting"]

    def _render(acc, _i):
        with st.container(border=True):
            store_tag = " · Store" if acc.is_store_account else ""
            st.markdown(f"**{acc.account_name}**")
            st.caption(f"{acc.account_type.value}{store_tag}")
            st.metric("Balance", _format_balance(acc.current_balance))

            protected = accounting_service.is_protected_account(acc)
            if protected:
                st.caption("Protected account")

            row1 = st.columns(2)
            if row1[0].button("Ledger", key=f"ledger_{acc.id}",
                              use_container_width=True):
                navigation.go_to_detail("account_detail", acc.id)
            if row1[1].button("Edit", key=f"edit_acc_{acc.id}",
                              use_container_width=True):
                st.session_state[EDIT_ACC] = acc.id
                st.rerun()

            row2 = st.columns(2)
            if not protected:
                if row2[0].button("Delete", key=f"delete_acc_{acc.id}",
                                  use_container_width=True):
                    try:
                        accounting_service.delete_account(acc.id)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            if row2[1].button(
                "Disable", key=f"deactivate_acc_{acc.id}",
                use_container_width=True,
                disabled=protected and acc.is_store_account,
            ):
                try:
                    accounting_service.deactivate_account(acc.id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    render_card_grid(page_accounts, _render, suffix="accounts")


def render(services: dict):
    accounting_service = services["accounting"]
    bar = render_list(
        ACCOUNTS,
        services=services,
        load_fn=_load_accounts,
        card_renderer=_render_account_cards,
        primary_label="+ Create Account",
        primary_key="accounts_create_btn",
        count_label="accounts",
        empty_text="No accounts yet.",
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        _create_account_dialog(accounting_service)
    open_pending_dialogs(services)


def render_account_detail(services: dict):
    accounting_service = services["accounting"]
    account_id = navigation.current_detail_id("account_detail")

    if st.button("← Back to accounts", key="account_detail_back"):
        navigation.go_back_to_list("accounts", "accounts_list")
        return

    account = accounting_service.get_account(account_id) if account_id else None
    if not account:
        st.error("Account not found.")
        return

    st.title(account.account_name)
    st.caption(
        f"{account.account_type.value} · Balance: "
        f"{_format_balance(account.current_balance)}"
    )

    ledger = sorted(
        accounting_service.get_account_ledger(account_id),
        key=lambda e: e["voucher_date"],
    )
    if not ledger:
        st.info("No transactions for this account yet.")
        return
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
