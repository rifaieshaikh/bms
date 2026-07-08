from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.ui.components.voucher_form import voucher_form
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    clear_dialog_flags,
    make_dismiss_handler,
)
from vaybooks.bms.ui.pagination import (
    CARD_PAGE_SIZE,
    TRIAL_BALANCE_PAGE_SIZE,
    VOUCHER_PAGE_SIZE,
    paginate_list,
    render_page_controls,
)

CREATE_ACC = "acc_create_dialog"
EDIT_ACC = "acc_edit_dialog"
LEDGER_ACC = "acc_ledger_dialog"

ACCOUNTS_PAGE_SIZE = CARD_PAGE_SIZE
RCPT = "acc_receipt_dialog"
PAY = "acc_payment_dialog"
SAL = "acc_salary_dialog"
INV_CUST = "acc_cust_inv_dialog"
INV_SALES = "acc_sales_inv_dialog"
JOURNAL = "acc_journal_dialog"


def _clear_other_invoice_dialog_flags(keep: str) -> None:
    """Only one invoice dialog may be armed; drop the sibling flag."""
    clear_dialog_flags(*(k for k in (INV_CUST, INV_SALES) if k != keep))


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


def _invoice_gross_amount(voucher) -> float:
    return max((line.credit_amount for line in voucher.lines), default=0.0)


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


@st.dialog(
    "Record Sales Invoice",
    width="large",
    on_dismiss=make_dismiss_handler(INV_SALES),
)
def _sales_invoice_dialog(accounting_service):
    _standalone_invoice_dialog(
        accounting_service,
        INV_SALES,
        VoucherType.SALES_INVOICE,
        accounting_service.get_sales_account,
        "Sales",
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
def _account_names(accounts) -> str:
    return ", ".join(a.account_name for a in accounts) if accounts else "—"


def _render_system_accounts_section(accounting_service) -> None:
    """Show default posting accounts used by receipts, payments, and invoices."""
    st.subheader("System Accounts")
    st.caption(
        "Default accounts for receipts, payments, invoices, payroll, and discounts."
    )

    store_accounts = accounting_service.get_store_accounts()
    salary_accounts = accounting_service.get_salary_accounts()
    expense_accounts = accounting_service.get_expense_accounts()
    income_accounts = accounting_service.get_income_accounts()
    customization = accounting_service.get_customization_account()
    sales = accounting_service.get_sales_account()
    discount = accounting_service.get_discount_account()

    cols = st.columns(2)
    cols[0].markdown(f"**Store:** {_account_names(store_accounts)}")
    cols[1].markdown(f"**Salary:** {_account_names(salary_accounts)}")
    cols[0].markdown(f"**Expense:** {_account_names(expense_accounts)}")
    cols[1].markdown(f"**Income:** {_account_names(income_accounts)}")

    posting = [
        a.account_name
        for a in (customization, sales, discount)
        if a is not None
    ]
    st.caption(f"Invoice posting: {', '.join(posting) if posting else '—'}")


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


def _render_voucher_list(vouchers, flag_key, edit_prefix, query="", page_key="acc_voucher_page"):
    vouchers = [v for v in vouchers if _voucher_matches(v, query)]
    if not vouchers:
        st.caption("No matching entries." if query else "Nothing recorded yet.")
        return
    sorted_vouchers = sorted(vouchers, key=lambda x: x.voucher_date, reverse=True)
    page_vouchers, page, total_pages = paginate_list(
        sorted_vouchers,
        page_key=page_key,
        page_size=VOUCHER_PAGE_SIZE,
        filter_key=f"{page_key}_filter",
        filter_value=query,
    )
    for v in page_vouchers:
        amount = v.total_debit
        with st.container(border=True):
            st.markdown(f"**{v.voucher_number}** — ₹{amount:,.0f}")
            st.caption(f"{_fmt_date(v.voucher_date)} | {v.description or '—'}")
            if st.button("Edit", key=f"{edit_prefix}_{v.id}"):
                st.session_state[flag_key] = v.id
                st.rerun()
    render_page_controls(
        page, total_pages, len(sorted_vouchers),
        page_key=page_key,
        prev_key=f"{page_key}_prev",
        next_key=f"{page_key}_next",
        label="entries",
    )


def _render_invoices_tab(accounting_service):
    btns = st.columns(2)
    if btns[0].button(
        "+ Record Customization Invoice", type="primary", key="btn_rec_cust_inv"
    ):
        _clear_other_invoice_dialog_flags(INV_CUST)
        _customization_invoice_dialog(accounting_service)
    if btns[1].button("+ Record Sales Invoice", type="primary", key="btn_rec_sales_inv"):
        _clear_other_invoice_dialog_flags(INV_SALES)
        _sales_invoice_dialog(accounting_service)

    query = st.text_input(
        "Search invoices",
        key="inv_search",
        placeholder="Customer, voucher no. or notes",
    ).strip().lower()

    customization = accounting_service.list_vouchers_by_type(
        VoucherType.CUSTOMIZATION_INVOICE
    )
    sales = accounting_service.list_vouchers_by_type(VoucherType.SALES_INVOICE)
    combined = [v for v in customization + sales if _voucher_matches(v, query)]
    if not combined:
        st.caption("No matching invoices." if query else "No invoices recorded yet.")
        return

    sorted_combined = sorted(combined, key=lambda x: x.voucher_date, reverse=True)
    page_vouchers, page, total_pages = paginate_list(
        sorted_combined,
        page_key="acc_inv_page",
        page_size=VOUCHER_PAGE_SIZE,
        filter_key="inv_search",
        filter_value=query,
    )
    for v in page_vouchers:
        gross = _invoice_gross_amount(v)
        customer_name = v.lines[0].account_name if v.lines else "—"
        is_customization = v.voucher_type == VoucherType.CUSTOMIZATION_INVOICE
        tag = "Customization" if is_customization else "Sales"
        flag_key = INV_CUST if is_customization else INV_SALES
        edit_prefix = "edit_cust_inv" if is_customization else "edit_sales_inv"
        order_ref = f" · Order linked" if v.reference_order_id else ""
        with st.container(border=True):
            st.markdown(f"**{v.voucher_number}** — ₹{gross:,.0f}  ·  _{tag}_")
            st.caption(
                f"{_fmt_date(v.voucher_date)} | Customer: {customer_name}{order_ref}"
            )
            if v.description:
                st.caption(v.description)
            if st.button("Edit", key=f"{edit_prefix}_{v.id}"):
                _clear_other_invoice_dialog_flags(flag_key)
                st.session_state[flag_key] = v.id
                st.rerun()

    render_page_controls(
        page, total_pages, len(sorted_combined),
        page_key="acc_inv_page", prev_key="acc_inv_prev", next_key="acc_inv_next",
        label="invoices",
    )


def _render_receipts_tab(accounting_service):
    if st.button("+ Record Receipt", type="primary", key="btn_rec_rcpt"):
        clear_all_dialog_flags()
        _receipt_dialog(accounting_service)
    query = st.text_input(
        "Search by account", key="rcpt_search",
        placeholder="Account name, voucher no. or notes",
    ).strip().lower()
    _render_voucher_list(
        accounting_service.list_vouchers_by_type(VoucherType.RECEIPT),
        RCPT, "edit_rcpt", query=query, page_key="acc_rcpt_page",
    )


def _render_payments_tab(services):
    accounting_service = services["accounting"]
    service_config = services["vendor_services"]
    btns = st.columns(2)
    if btns[0].button("+ Record Vendor Payment", type="primary", key="btn_rec_pay"):
        _clear_other_payment_dialog_flags(PAY)
        _payment_dialog(services)
    if btns[1].button("+ Record Salary", type="primary", key="btn_rec_sal"):
        _clear_other_payment_dialog_flags(SAL)
        _salary_dialog(accounting_service)
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
    sorted_combined = sorted(combined, key=lambda x: x.voucher_date, reverse=True)
    page_vouchers, page, total_pages = paginate_list(
        sorted_combined,
        page_key="acc_pay_page",
        page_size=VOUCHER_PAGE_SIZE,
        filter_key="pay_search",
        filter_value=query,
    )
    for v in page_vouchers:
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

    render_page_controls(
        page, total_pages, len(sorted_combined),
        page_key="acc_pay_page", prev_key="acc_pay_prev", next_key="acc_pay_next",
        label="payments",
    )


def _render_voucher_tab(accounting_service):
    st.subheader("Voucher List")
    if st.button("+ Create Voucher", type="primary", key="btn_create_voucher"):
        clear_all_dialog_flags()
        _journal_dialog(accounting_service)

    query = st.text_input(
        "Search vouchers",
        key="vch_search",
        placeholder="Voucher number, type or description",
    ).strip().lower()

    vouchers = accounting_service.list_vouchers()
    if query:
        vouchers = [v for v in vouchers if _voucher_matches(v, query)]
    if not vouchers:
        st.caption("No matching vouchers." if query else "No vouchers recorded yet.")
        return

    sorted_vouchers = sorted(vouchers, key=lambda x: x.voucher_date, reverse=True)
    page_vouchers, page, total_pages = paginate_list(
        sorted_vouchers,
        page_key="acc_vch_page",
        page_size=VOUCHER_PAGE_SIZE,
        filter_key="vch_search",
        filter_value=query,
    )
    for v in page_vouchers:
        amount = v.total_debit
        vtype = v.voucher_type.value if hasattr(v.voucher_type, "value") else str(v.voucher_type)
        order_ref = " · Order linked" if v.reference_order_id else ""
        with st.container(border=True):
            st.markdown(f"**{v.voucher_number}** — ₹{amount:,.0f}  ·  _{vtype}_")
            st.caption(f"{_fmt_date(v.voucher_date)} | {v.description or '—'}{order_ref}")
            if v.voucher_type == VoucherType.JOURNAL:
                for line in v.lines:
                    side = (
                        f"Dr ₹{line.debit_amount:,.0f}"
                        if line.debit_amount
                        else f"Cr ₹{line.credit_amount:,.0f}"
                    )
                    st.caption(f"• {line.account_name}: {side}")

    render_page_controls(
        page, total_pages, len(sorted_vouchers),
        page_key="acc_vch_page", prev_key="acc_vch_prev", next_key="acc_vch_next",
        label="vouchers",
    )


def _render_journal_tab(accounting_service):
    if st.button("+ New Journal Entry", type="primary", key="btn_new_jrnl"):
        clear_all_dialog_flags()
        _journal_dialog(accounting_service)
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
    sorted_journals = sorted(journals, key=lambda x: x.voucher_date, reverse=True)
    page_journals, page, total_pages = paginate_list(
        sorted_journals,
        page_key="acc_jrnl_page",
        page_size=VOUCHER_PAGE_SIZE,
        filter_key="jrnl_search",
        filter_value=query,
    )
    for v in page_journals:
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

    render_page_controls(
        page, total_pages, len(sorted_journals),
        page_key="acc_jrnl_page", prev_key="acc_jrnl_prev", next_key="acc_jrnl_next",
        label="entries",
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


def render(services: dict):
    st.title("Accounts")
    accounting_service = services["accounting"]
    _render_system_accounts_section(accounting_service)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        [
            "Accounts",
            "Ledger",
            "Voucher",
            "Receipts",
            "Payments",
            "Invoices",
            "Journal",
            "Trial Balance",
        ]
    )
    with tab1:
        _render_accounts_tab(accounting_service)
    with tab2:
        _render_ledger_tab(accounting_service)
    with tab3:
        _render_voucher_tab(accounting_service)
    with tab4:
        _render_receipts_tab(accounting_service)
    with tab5:
        _render_payments_tab(services)
    with tab6:
        _render_invoices_tab(accounting_service)
    with tab7:
        _render_journal_tab(accounting_service)
    with tab8:
        _render_trial_balance_tab(accounting_service)

    # Popups opened at page top level (page is not itself a dialog).
    # Only one dialog may open per run, so this is a strict if/elif chain.
    # "New" dialogs are called directly from buttons; only edit flows use flags here.
    if st.session_state.get(EDIT_ACC):
        _edit_account_dialog(accounting_service)
    elif st.session_state.get(LEDGER_ACC):
        _ledger_dialog(accounting_service)
    elif st.session_state.get(RCPT):
        _receipt_dialog(accounting_service)
    elif st.session_state.get(PAY):
        _payment_dialog(services)
    elif st.session_state.get(SAL):
        _salary_dialog(accounting_service)
    elif st.session_state.get(INV_CUST):
        _customization_invoice_dialog(accounting_service)
    elif st.session_state.get(INV_SALES):
        _sales_invoice_dialog(accounting_service)
    elif st.session_state.get(JOURNAL):
        _journal_dialog(accounting_service)
