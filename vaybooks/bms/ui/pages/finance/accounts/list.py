from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.common.voucher_card import invoice_gross_amount
from vaybooks.bms.ui.components.finance.voucher_form import voucher_form
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
from vaybooks.bms.ui.theme.icons import icon_caption

CREATE_ACC = "acc_create_dialog"
EDIT_ACC = "acc_edit_dialog"
LEDGER_ACC = "acc_ledger_dialog"

ACCOUNTS_PAGE_SIZE = CARD_PAGE_SIZE
RCPT = "acc_receipt_dialog"
RCPT_PRESELECT_ACCOUNT = "acc_receipt_preselect_customer_account_id"
RCPT_PRESELECT_INVOICE = "acc_receipt_preselect_invoice_id"
PAY = "acc_payment_dialog"
SAL = "acc_salary_dialog"
COMM = "acc_commission_dialog"
INV_CUST = "acc_cust_inv_dialog"
JOURNAL = "acc_journal_dialog"
CREDIT_NOTE = "acc_credit_note_dialog"
DEBIT_NOTE = "acc_debit_note_dialog"


def _clear_other_invoice_dialog_flags(keep: str) -> None:
    """Only one invoice dialog may be armed; drop the sibling flag."""
    clear_dialog_flags(*(k for k in (INV_CUST,) if k != keep))


def _clear_other_payment_dialog_flags(keep: str) -> None:
    clear_dialog_flags(*(k for k in (PAY, SAL, COMM) if k != keep))


def _voucher_location_filter(services: dict) -> dict:
    from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
    from vaybooks.bms.ui.auth.session import working_location_list_context

    working, accessible = working_location_list_context(services)
    return location_id_mongo_filter(working, accessible)


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
    if cols[0].button("Create", type="primary", width="stretch"):
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
    if cols[1].button("Cancel", width="stretch"):
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
    if cols[0].button("Save", type="primary", width="stretch"):
        try:
            accounting_service.update_account(
                account.id, name, acc_type, is_store, is_salary
            )
            st.session_state.pop(EDIT_ACC, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(EDIT_ACC, None)
        st.rerun()


@st.dialog("Account Ledger", width="large", on_dismiss=make_dismiss_handler(LEDGER_ACC))
def _ledger_dialog(services):
    accounting_service = services["accounting"]
    account = accounting_service.get_account(st.session_state.get(LEDGER_ACC))
    if not account:
        st.error("Account not found")
        return
    st.markdown(f"**{account.account_name}** ({account.account_type.value})")
    st.caption(f"Current balance: {_format_balance(account.current_balance)}")

    filt = _voucher_location_filter(services)
    ledger = sorted(
        accounting_service.get_account_ledger(account.id, location_filter=filt),
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
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    if st.button("Close"):
        st.session_state.pop(LEDGER_ACC, None)
        st.rerun()


@st.dialog(
    "Record Receipt",
    on_dismiss=make_dismiss_handler(
        RCPT, RCPT_PRESELECT_ACCOUNT, RCPT_PRESELECT_INVOICE
    ),
)
def _receipt_dialog(services):
    from vaybooks.bms.domain.finance.accounting.settlement import (
        ALLOC_INVOICE_TAG,
        allocation_rows_from_meta,
        allocated_total,
        resolve_receipt_allocations,
        strip_meta,
    )
    from vaybooks.bms.ui.components.common.location_fields import (
        require_location_name,
    )

    accounting_service = services["accounting"]
    target = st.session_state.get(RCPT)
    voucher = None if target in (None, "new") else accounting_service.get_voucher(target)

    store_accounts = accounting_service.get_store_accounts()
    customers = [a for a in accounting_service.list_accounts() if a.linked_customer_id]
    def _clear_receipt_session() -> None:
        st.session_state.pop(RCPT, None)
        st.session_state.pop(RCPT_PRESELECT_ACCOUNT, None)
        st.session_state.pop(RCPT_PRESELECT_INVOICE, None)

    if not store_accounts or not customers:
        st.error("Need at least one store account and one customer account.")
        if st.button("Close"):
            _clear_receipt_session()
            st.rerun()
        return

    recv_opts = {a.account_name: a.id for a in store_accounts}
    cust_opts = {a.account_name: a.id for a in customers}
    preselect_invoice_id = st.session_state.get(RCPT_PRESELECT_INVOICE)
    existing_recv = voucher.lines[0].account_id if voucher else None
    existing_cust = (
        voucher.lines[1].account_id
        if voucher
        else st.session_state.get(RCPT_PRESELECT_ACCOUNT)
    )
    existing_amt = voucher.lines[0].debit_amount if voucher else 0.0
    existing_alloc_rows = (
        allocation_rows_from_meta(voucher.description or "") if voucher else []
    )
    existing_invoice_id = (
        existing_alloc_rows[0]["invoice_id"]
        if len(existing_alloc_rows) == 1
        else None
    )
    if not existing_invoice_id and preselect_invoice_id:
        existing_invoice_id = preselect_invoice_id
    existing_desc = ""
    if voucher:
        existing_desc = strip_meta(voucher.description or "", ALLOC_INVOICE_TAG)

    recv = st.selectbox(
        "Receiving Account (Store)", list(recv_opts.keys()),
        index=_index_of(recv_opts, existing_recv),
    )
    cust = st.selectbox(
        "Customer Account", list(cust_opts.keys()),
        index=_index_of(cust_opts, existing_cust),
    )

    customer_account_id = cust_opts[cust]
    open_invoices = accounting_service.list_open_sales_invoices_for_customer(
        customer_account_id,
        exclude_receipt_id=voucher.id if voucher else None,
    )
    if not voucher and existing_invoice_id and existing_amt <= 0:
        for inv in open_invoices:
            if inv.get("id") == existing_invoice_id:
                existing_amt = float(inv.get("outstanding") or 0)
                break

    amount = st.number_input("Amount", min_value=0.0, value=float(existing_amt))
    v_date = st.date_input("Date", value=date.today())
    desc = st.text_input("Description", value=existing_desc)

    invoice_opts = {"(none — FIFO)": None}
    for inv in open_invoices:
        label = (
            f"{inv.get('store_invoice_number') or inv.get('id')} — "
            f"₹{float(inv.get('outstanding') or 0):,.2f} due "
            f"({inv.get('sale_date') or '—'})"
        )
        invoice_opts[label] = inv.get("id")

    default_inv_index = 0
    if existing_invoice_id:
        for i, inv_id in enumerate(invoice_opts.values()):
            if inv_id == existing_invoice_id:
                default_inv_index = i
                break

    alloc_label = st.selectbox(
        "Allocate to invoice",
        list(invoice_opts.keys()),
        index=default_inv_index,
        help="Pick an invoice to settle that bill only. Leave as FIFO to apply "
        "oldest open invoices first.",
    )
    allocation_invoice_id = invoice_opts[alloc_label]

    preview_rows, preview_unalloc = resolve_receipt_allocations(
        amount,
        allocation_invoice_id=allocation_invoice_id,
        open_invoices=open_invoices,
    )
    applied = allocated_total(preview_rows)
    st.caption(
        f"Applied to invoices: ₹{applied:,.2f} · "
        f"Unallocated credit: ₹{preview_unalloc:,.2f}"
    )

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", width="stretch"):
        try:
            if voucher:
                accounting_service.update_receipt(
                    voucher.id,
                    recv_opts[recv],
                    cust_opts[cust],
                    amount,
                    desc,
                    v_date,
                    allocation_invoice_id=allocation_invoice_id,
                )
            else:
                location_id, location_name = require_location_name(services)
                accounting_service.create_receipt(
                    recv_opts[recv],
                    cust_opts[cust],
                    amount,
                    desc,
                    v_date,
                    allocation_invoice_id=allocation_invoice_id,
                    location_id=location_id,
                    location_name=location_name,
                )
            _clear_receipt_session()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        _clear_receipt_session()
        st.rerun()


@st.dialog("Record Vendor Payment", on_dismiss=make_dismiss_handler(PAY))
def _payment_dialog(services):
    accounting_service = services["accounting"]
    vendor_service = services["vendors"]
    service_config = services["vendor_services"]
    from vaybooks.bms.ui.components.common.location_fields import (
        require_location_name,
    )

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
    if cols[0].button("Save", type="primary", width="stretch"):
        try:
            if voucher:
                accounting_service.update_vendor_payment(
                    voucher.id, vendor_opts[vendor_name],
                    selected_service.expense_account_id, pay_opts[pay], amount,
                    desc, v_date, service_id=selected_service.id,
                )
            else:
                location_id, location_name = require_location_name(services)
                accounting_service.create_vendor_payment(
                    vendor_opts[vendor_name], selected_service.expense_account_id,
                    pay_opts[pay], amount, desc, v_date,
                    service_id=selected_service.id,
                    location_id=location_id,
                    location_name=location_name,
                )
            st.session_state.pop(PAY, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
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
    if cols[0].button("Save", type="primary", width="stretch"):
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
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(SAL, None)
        st.rerun()


@st.dialog(
    "Record Commission",
    on_dismiss=make_dismiss_handler(COMM),
)
def _commission_dialog(services):
    accounting_service = services["accounting"]
    agent_service = services.get("commission_agents")
    target = st.session_state.get(COMM)
    voucher = None if target in (None, "new") else accounting_service.get_voucher(target)

    store_accounts = accounting_service.get_store_accounts()
    agents = agent_service.list_all_agents() if agent_service else []
    if not store_accounts or not agents:
        st.error(
            "Need at least one commission agent and one store (cash/bank) account."
        )
        if st.button("Close"):
            st.session_state.pop(COMM, None)
            st.rerun()
        return

    agent_opts = {}
    for a in agents:
        acc = accounting_service.get_agent_account(a.id)
        if acc:
            agent_opts[a.agent_name] = acc.id
    if not agent_opts:
        st.error("No commission agent ledger accounts found.")
        if st.button("Close"):
            st.session_state.pop(COMM, None)
            st.rerun()
        return

    pay_opts = {a.account_name: a.id for a in store_accounts}
    existing_agent = voucher.lines[0].account_id if voucher else None
    existing_pay = voucher.lines[1].account_id if voucher and len(voucher.lines) > 1 else None
    existing_amt = voucher.lines[0].debit_amount if voucher else 0.0
    existing_invoice = getattr(voucher, "reference_invoice_id", None) if voucher else None

    agent_name = st.selectbox(
        "Commission Agent",
        list(agent_opts.keys()),
        index=_index_of(agent_opts, existing_agent),
    )
    pay = st.selectbox(
        "Paying Account (Store)",
        list(pay_opts.keys()),
        index=_index_of(pay_opts, existing_pay),
    )
    amount = st.number_input("Amount", min_value=0.0, value=float(existing_amt))
    v_date = st.date_input("Date", value=date.today())
    desc = st.text_input(
        "Description",
        value=voucher.description if voucher else "Commission payment",
    )
    invoice_ref = st.text_input(
        "Sales invoice voucher id (optional)",
        value=existing_invoice or "",
        help="Link this settlement to a sales invoice voucher id.",
    )

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", width="stretch"):
        try:
            ref = (invoice_ref or "").strip() or None
            if voucher:
                accounting_service.update_commission_payment(
                    voucher.id,
                    agent_opts[agent_name],
                    pay_opts[pay],
                    amount,
                    desc,
                    v_date,
                    reference_invoice_id=ref,
                )
            else:
                accounting_service.create_commission_payment(
                    agent_opts[agent_name],
                    pay_opts[pay],
                    amount,
                    desc,
                    v_date,
                    reference_invoice_id=ref,
                )
            st.session_state.pop(COMM, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(COMM, None)
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
    if cols[0].button("Save", type="primary", width="stretch"):
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
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(flag_key, None)
        st.rerun()


@st.dialog("New Journal Entry", width="large", on_dismiss=make_dismiss_handler(JOURNAL))
def _journal_dialog(services):
    from vaybooks.bms.ui.components.common.location_fields import (
        require_location_name,
    )

    accounting_service = services["accounting"]
    accounts = accounting_service.list_accounts()
    desc = st.text_input("Journal Description", key="acc_jrnl_desc")
    lines, balanced = voucher_form(accounts, key_prefix="acc_jrnl")

    cols = st.columns(2)
    if cols[0].button(
        "Save", type="primary", width="stretch", disabled=not balanced
    ):
        try:
            location_id, location_name = require_location_name(services)
            accounting_service.create_journal_entry(
                desc,
                lines,
                location_id=location_id,
                location_name=location_name,
            )
            st.session_state.pop("acc_jrnl_lines", None)
            st.session_state.pop(JOURNAL, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop("acc_jrnl_lines", None)
        st.session_state.pop(JOURNAL, None)
        st.rerun()


def _party_accounts_for_kind(accounting_service, party_kind: str):
    accounts = accounting_service.list_accounts()
    if party_kind == "Customer":
        return [a for a in accounts if a.linked_customer_id]
    return [a for a in accounts if a.linked_vendor_id]


def _contra_accounts_for_kind(accounting_service, party_kind: str):
    if party_kind == "Customer":
        income = accounting_service.get_income_accounts()
        sales = accounting_service.get_sales_account()
        if sales and sales.id not in {a.id for a in income}:
            return [sales] + income
        return income or ([sales] if sales else [])
    return accounting_service.get_expense_accounts()


def _source_docs_for_party(accounting_service, party_kind: str, party_account_id: str):
    """Optional invoice/bill vouchers that touch the party account."""
    if party_kind == "Customer":
        types = (VoucherType.SALES_INVOICE, VoucherType.CUSTOMIZATION_INVOICE)
    else:
        types = (VoucherType.PURCHASE_BILL,)
    docs = []
    for vtype in types:
        for v in accounting_service.list_vouchers_by_type(vtype):
            if any(line.account_id == party_account_id for line in v.lines):
                docs.append(v)
    docs.sort(key=lambda v: v.voucher_date or date.today(), reverse=True)
    return docs


def _note_dialog_body(accounting_service, *, note_kind: str, flag_key: str, key_prefix: str):
    """Shared create form for credit/debit notes."""
    party_kind = st.radio(
        "Party type",
        ["Customer", "Vendor"],
        horizontal=True,
        key=f"{key_prefix}_party_kind",
    )
    parties = _party_accounts_for_kind(accounting_service, party_kind)
    contras = _contra_accounts_for_kind(accounting_service, party_kind)
    stores = accounting_service.get_store_accounts()
    if not parties:
        st.error(f"Need at least one {party_kind.lower()} account.")
        if st.button("Close", key=f"{key_prefix}_close_party"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return
    if not contras:
        label = "income" if party_kind == "Customer" else "expense"
        st.error(f"Need at least one {label} account for the contra entry.")
        if st.button("Close", key=f"{key_prefix}_close_contra"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return

    party_opts = {a.account_name: a.id for a in parties}
    contra_opts = {a.account_name: a.id for a in contras}
    default_contra = None
    if party_kind == "Customer":
        sales = accounting_service.get_sales_account()
        if sales and sales.account_name in contra_opts:
            default_contra = sales.id

    party = st.selectbox(
        f"{party_kind} Account",
        list(party_opts.keys()),
        key=f"{key_prefix}_party",
    )
    contra = st.selectbox(
        "Contra Account",
        list(contra_opts.keys()),
        index=_index_of(contra_opts, default_contra),
        key=f"{key_prefix}_contra",
    )
    amount = st.number_input(
        "Amount", min_value=0.0, value=0.0, key=f"{key_prefix}_amount"
    )
    v_date = st.date_input("Date", value=date.today(), key=f"{key_prefix}_date")
    desc = st.text_input("Description", value="", key=f"{key_prefix}_desc")

    source_docs = _source_docs_for_party(
        accounting_service, party_kind, party_opts[party]
    )
    source_opts = {"(none)": None}
    for v in source_docs:
        label = f"{v.voucher_number} — {v.description or v.voucher_type.value}"
        source_opts[label] = v.id
    source_label = st.selectbox(
        "Source invoice/bill (optional)",
        list(source_opts.keys()),
        key=f"{key_prefix}_source",
    )

    settle_amount = 0.0
    settle_account_id = None
    if note_kind == "credit":
        st.caption(
            "Credit notes create customer credit only. To pay cash/bank, use "
            "Record Refund on the customer after issuing the note."
        )
    else:
        settle_amount = st.number_input(
            "Settle amount (optional)",
            min_value=0.0,
            value=0.0,
            key=f"{key_prefix}_settle_amt",
        )
        if settle_amount > 0:
            if not stores:
                st.error("Need a store/cash account to settle.")
            else:
                store_opts = {a.account_name: a.id for a in stores}
                settle_name = st.selectbox(
                    "Settlement Account (Cash/Bank)",
                    list(store_opts.keys()),
                    key=f"{key_prefix}_settle_acct",
                )
                settle_account_id = store_opts[settle_name]

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", width="stretch", key=f"{key_prefix}_save"):
        try:
            create_fn = (
                accounting_service.create_credit_note
                if note_kind == "credit"
                else accounting_service.create_debit_note
            )
            create_fn(
                party_kind=party_kind.lower(),
                party_account_id=party_opts[party],
                amount=amount,
                description=desc,
                contra_account_id=contra_opts[contra],
                voucher_date=v_date,
                amount_settled=settle_amount,
                settle_account_id=settle_account_id,
                reference_invoice_id=source_opts[source_label],
            )
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch", key=f"{key_prefix}_cancel"):
        st.session_state.pop(flag_key, None)
        st.rerun()


@st.dialog("Create Credit Note", on_dismiss=make_dismiss_handler(CREDIT_NOTE))
def _credit_note_dialog(accounting_service):
    _note_dialog_body(
        accounting_service,
        note_kind="credit",
        flag_key=CREDIT_NOTE,
        key_prefix="acc_cn",
    )


@st.dialog("Create Debit Note", on_dismiss=make_dismiss_handler(DEBIT_NOTE))
def _debit_note_dialog(accounting_service):
    _note_dialog_body(
        accounting_service,
        note_kind="debit",
        flag_key=DEBIT_NOTE,
        key_prefix="acc_dn",
    )


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
            if btns[0].button("View Ledger", key=f"ledger_{acc.id}", width="stretch"):
                st.session_state[LEDGER_ACC] = acc.id
                st.rerun()
            if btns[1].button("Edit", key=f"edit_acc_{acc.id}", width="stretch"):
                st.session_state[EDIT_ACC] = acc.id
                st.rerun()
            action_col = 2
            if not protected:
                if btns[action_col].button(
                    "Delete", key=f"delete_acc_{acc.id}", width="stretch"
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
                width="stretch",
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


def _render_ledger_tab(services):
    accounting_service = services["accounting"]
    filt = _voucher_location_filter(services)
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

    trial = accounting_service.get_trial_balance(location_filter=filt)
    if trial:
        total_debit = round(sum(r["debit"] for r in trial), 2)
        total_credit = round(sum(r["credit"] for r in trial), 2)
        balanced = abs(total_debit - total_credit) < 0.01
        icon_caption(
            f"Trial balance: ₹{total_debit:,.2f} Dr / ₹{total_credit:,.2f} Cr"
            + (" — Balanced" if balanced else " — Unbalanced"),
            icon="check" if balanced else "x",
        )

    ledger = sorted(
        accounting_service.get_account_ledger(account_id, location_filter=filt),
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
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_trial_balance_tab(services):
    accounting_service = services["accounting"]
    filt = _voucher_location_filter(services)
    trial = accounting_service.get_trial_balance(location_filter=filt)
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
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
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
        _receipt_dialog(services)
    elif st.session_state.get(PAY):
        _payment_dialog(services)
    elif st.session_state.get(SAL):
        _salary_dialog(accounting_service)
    elif st.session_state.get(COMM):
        _commission_dialog(services)
    elif st.session_state.get(INV_CUST):
        _customization_invoice_dialog(accounting_service)
    elif st.session_state.get(JOURNAL):
        _journal_dialog(services)
    elif st.session_state.get(CREDIT_NOTE):
        _credit_note_dialog(accounting_service)
    elif st.session_state.get(DEBIT_NOTE):
        _debit_note_dialog(accounting_service)
    elif st.session_state.get(LEDGER_ACC):
        _ledger_dialog(services)


def _render_customer_settlements_inbox(accounting_service) -> None:
    """Pending parks awaiting Approve (expense) or Reject (reverse)."""
    try:
        pending = accounting_service.list_customer_settlements(status="pending")
    except Exception:
        pending = []
    with st.container(border=True):
        st.subheader("Customer Settlements")
        if not pending:
            st.caption("No pending customer settlements.")
            return
        st.caption(
            f"{len(pending)} pending — Approve posts Settlement Expense; "
            "Reject reverses the park and reopens allocated invoices."
        )
        for row in pending:
            park_id = row["id"]
            with st.container(border=True):
                left, mid, right = st.columns([3, 2, 2], vertical_alignment="center")
                with left:
                    st.markdown(f"**{row.get('customer_name') or 'Customer'}**")
                    st.caption(
                        f"{row.get('voucher_number') or park_id} · "
                        f"{_fmt_date(row.get('voucher_date'))} · "
                        f"{row.get('reason') or '—'}"
                    )
                with mid:
                    st.metric("Pending", f"₹{float(row.get('remaining') or 0):,.2f}")
                with right:
                    a1, a2 = st.columns(2)
                    if a1.button(
                        "Approve",
                        key=f"acc_settle_approve_{park_id}",
                        type="primary",
                        width="stretch",
                    ):
                        try:
                            accounting_service.approve_customer_settlement(park_id)
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
                    if a2.button(
                        "Reject",
                        key=f"acc_settle_reject_{park_id}",
                        width="stretch",
                    ):
                        try:
                            accounting_service.reject_customer_settlement(park_id)
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))


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
                              width="stretch"):
                navigation.go_to_detail("account_detail", acc.id)
            if row1[1].button("Edit", key=f"edit_acc_{acc.id}",
                              width="stretch"):
                st.session_state[EDIT_ACC] = acc.id
                st.rerun()

            row2 = st.columns(2)
            if not protected:
                if row2[0].button("Delete", key=f"delete_acc_{acc.id}",
                                  width="stretch"):
                    try:
                        accounting_service.delete_account(acc.id)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            if row2[1].button(
                "Disable", key=f"deactivate_acc_{acc.id}",
                width="stretch",
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
    _render_customer_settlements_inbox(accounting_service)
    bar = render_list(
        ACCOUNTS,
        services=services,
        load_fn=_load_accounts,
        card_renderer=_render_account_cards,
        primary_label="+ Create Account",
        primary_key="accounts_create_btn",
        count_label="accounts",
        empty_text="No accounts yet.",
        page_key_nav="accounts_list",
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        _create_account_dialog(accounting_service)
    open_pending_dialogs(services)


def render_account_detail(services: dict):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("account_detail")
    mark_wired("nav.back")
    accounting_service = services["accounting"]
    account_id = navigation.current_detail_id("account_detail")

    if st.button("← Back to accounts", key="account_detail_back") or consume_action("nav.back"):
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

    filt = _voucher_location_filter(services)
    ledger = sorted(
        accounting_service.get_account_ledger(account_id, location_filter=filt),
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
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
