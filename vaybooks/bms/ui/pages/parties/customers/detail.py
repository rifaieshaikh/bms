"""Customer detail route (`?id=<customer_id>`): profile, dashboard, orders."""

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.boutique.order_card import order_cards
from vaybooks.bms.ui.components.sales.sales_invoice_dialog import (
    arm_sales_record_dialog,
    open_sales_record_dialog_if_armed,
)
from vaybooks.bms.ui.components.sales.sales_order_dialog import (
    arm_so_dialog,
    open_so_dialog_if_armed,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.list_schemas import MEASUREMENTS, ORDERS, RECEIPTS
from vaybooks.bms.ui.responsive import viewport_width
from vaybooks.bms.ui.sales_list_schemas import (
    DELIVERY_NOTES,
    ESTIMATES,
    QUOTATIONS,
    SALES_ORDERS,
    SALES_RETURNS,
    STORE_SALES,
)
from vaybooks.bms.ui.session_keys import filters_key
from vaybooks.bms.ui.styles import panel, status_badge

RECENT_ORDER_LIMIT = 5
C_BLACKLIST = "customer_blacklist_dialog"


REFUND = "customer_refund_dialog"
MOVE_ADVANCE = "customer_move_advance_dialog"
SETTLE = "customer_settle_dialog"


@st.dialog("Settle customer balance", on_dismiss=make_dismiss_handler(SETTLE))
def _customer_settle_dialog(accounting_service, customer_account_id: str):
    receivable = accounting_service.customer_receivable_balance(customer_account_id)
    parked = accounting_service.get_customer_parked_settlement(customer_account_id)
    if receivable <= 0.01:
        if parked > 0.01:
            st.info(
                f"₹{parked:,.2f} is parked pending Accounts approval. "
                "Approve or reject under Finance → Accounts."
            )
        else:
            st.info("Nothing to settle — no receivable.")
        if st.button("Close", key="cd_settle_close"):
            st.session_state.pop(SETTLE, None)
            st.rerun()
        return

    st.caption(
        "Parks receivable into **Settlement** (asset) and FIFO-clears open "
        "sales invoices. Expense / write-off requires approval in "
        "**Finance → Accounts**."
    )
    st.write(f"Receivable: **₹{receivable:,.2f}**")
    if parked > 0.01:
        st.write(f"Pending approval: **₹{parked:,.2f}**")

    amount = st.number_input(
        "Amount to park",
        min_value=0.01,
        max_value=float(receivable),
        value=float(receivable),
        key="cd_settle_amt",
    )
    reason = st.text_input(
        "Reason",
        value="Uncollectible balance",
        key="cd_settle_reason",
    )
    v_date = st.date_input("Date", value=date.today(), key="cd_settle_date")
    cols = st.columns(2)
    if cols[0].button("Park for approval", type="primary", key="cd_settle_save"):
        try:
            accounting_service.settle_customer_balance(
                customer_account_id,
                amount,
                mode="park",
                reason=reason,
                voucher_date=v_date,
            )
            st.session_state.pop(SETTLE, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", key="cd_settle_cancel"):
        st.session_state.pop(SETTLE, None)
        st.rerun()


@st.dialog("Record Refund", on_dismiss=make_dismiss_handler(REFUND))
def _customer_refund_dialog(accounting_service, customer_account_id: str):
    credit = accounting_service.customer_credit_balance(customer_account_id)
    stores = accounting_service.get_store_accounts()
    if credit <= 0:
        st.info("No customer credit available to refund.")
        if st.button("Close", key="cd_refund_close"):
            st.session_state.pop(REFUND, None)
            st.rerun()
        return
    if not stores:
        st.error("Need a cash/bank store account to refund.")
        if st.button("Close", key="cd_refund_close2"):
            st.session_state.pop(REFUND, None)
            st.rerun()
        return
    store_opts = {a.account_name: a.id for a in stores}
    store_name = st.selectbox("Cash / Bank account", list(store_opts.keys()), key="cd_refund_store")
    amount = st.number_input(
        "Refund amount",
        min_value=0.01,
        max_value=float(credit),
        value=float(credit),
        key="cd_refund_amt",
    )
    desc = st.text_input("Description", value="Customer refund", key="cd_refund_desc")
    v_date = st.date_input("Date", value=date.today(), key="cd_refund_date")
    cols = st.columns(2)
    if cols[0].button("Save", type="primary", key="cd_refund_save"):
        try:
            accounting_service.create_refund(
                customer_account_id=customer_account_id,
                store_account_id=store_opts[store_name],
                amount=amount,
                description=desc,
                voucher_date=v_date,
                refund_type="payment",
            )
            st.session_state.pop(REFUND, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", key="cd_refund_cancel"):
        st.session_state.pop(REFUND, None)
        st.rerun()


@st.dialog("Move Credit to Advance", on_dismiss=make_dismiss_handler(MOVE_ADVANCE))
def _customer_move_advance_dialog(services, customer_id: str, customer_account_id: str):
    accounting = services["accounting"]
    orders_svc = services.get("orders")
    credit = accounting.customer_credit_balance(customer_account_id)
    if credit <= 0:
        st.info("No customer credit available.")
        if st.button("Close", key="cd_adv_close"):
            st.session_state.pop(MOVE_ADVANCE, None)
            st.rerun()
        return
    order_opts = {"(general advance — no order)": None}
    if orders_svc:
        try:
            for order in orders_svc.list_recent_by_customer(customer_id, 50):
                label = f"{order.order_number} · ₹{float(order.advance_amount or 0):,.0f} adv"
                order_opts[label] = order.id
        except Exception:
            pass
    order_label = st.selectbox("Boutique order", list(order_opts.keys()), key="cd_adv_order")
    order_id = order_opts[order_label]
    amount = st.number_input(
        "Amount",
        min_value=0.01,
        max_value=float(credit),
        value=float(credit),
        key="cd_adv_amt",
    )
    cols = st.columns(2)
    if cols[0].button("Save", type="primary", key="cd_adv_save"):
        try:
            if order_id and orders_svc:
                orders_svc.apply_customer_credit_as_order_advance(order_id, amount)
            else:
                accounting.allocate_customer_credit_to_advance(
                    customer_account_id=customer_account_id,
                    amount=amount,
                    reference_order_id=order_id,
                    description="Allocate customer credit to advance",
                )
            st.session_state.pop(MOVE_ADVANCE, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", key="cd_adv_cancel"):
        st.session_state.pop(MOVE_ADVANCE, None)
        st.rerun()


def _credit_actions_section(
    services,
    customer,
    *,
    customer_account_id: str,
    balance: float,
) -> None:
    accounting = services.get("accounting")
    if not accounting or not customer_account_id:
        return
    credit = accounting.customer_credit_balance(customer_account_id)
    if credit <= 0.01:
        return
    with st.container(border=True):
        st.subheader("Customer credit")
        st.caption(f"Available credit: ₹{credit:,.2f}")
        c1, c2 = st.columns(2)
        if c1.button("Move to advance", key="cd_move_adv_btn"):
            st.session_state[MOVE_ADVANCE] = customer.id
            st.rerun()
        if c2.button("Record Refund", key="cd_refund_btn"):
            st.session_state[REFUND] = customer_account_id
            st.rerun()


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _balance_status(balance: float) -> tuple[str, str]:
    """Return (status label, badge color) from ledger balance."""
    if abs(balance) < 0.01:
        return "Settled", "gray"
    if balance > 0:
        return "Receivable", "red"
    return "Credit", "green"


def _format_balance_amount(balance: float) -> str:
    return f"\u20b9{balance:,.2f}"


def _inject_page_css() -> None:
    st.markdown(
        """
        <style>
          div[class*="st-key-cust_view_shell"] {
            max-width: 1480px;
            margin-left: auto;
            margin-right: auto;
            padding-left: 28px;
            padding-right: 28px;
          }
          @media (max-width: 1100px) {
            div[class*="st-key-cust_view_shell"] {
              padding-left: 22px;
              padding-right: 22px;
            }
          }
          @media (max-width: 700px) {
            div[class*="st-key-cust_view_shell"] {
              padding-left: 16px;
              padding-right: 16px;
            }
          }
          div[class*="st-key-cust_rel_tx"]
            div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.35rem 0.55rem;
          }
          div[class*="st-key-cust_rel_tx"] div.stButton > button {
            min-width: 72px;
            max-width: 100px;
            height: 34px;
            padding: 0.2rem 0.55rem;
          }
          div[class*="st-key-cust_view_shell"] div[data-testid="stMetric"] {
            height: 100%;
          }
          div[class*="st-key-cust_qa"]
            div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.55rem 0.85rem 0.7rem;
          }
          div[class*="st-key-cust_qa"] div.stButton > button {
            width: 100%;
            height: 40px;
            min-height: 40px;
            padding: 0.35rem 0.75rem;
            white-space: nowrap;
            justify-content: center;
          }
          div[class*="st-key-cust_metrics"]
            div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.65rem 0.85rem 0.85rem;
          }
          div[class*="st-key-cust_metrics"] h3,
          div[class*="st-key-cust_metrics"] .stMarkdown p {
            margin-bottom: 0.35rem;
          }
          div[class*="st-key-cust_metric_card"]
            div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.55rem 0.7rem 0.75rem;
            height: 100%;
          }
          div[class*="st-key-cust_metric_card"] [data-testid="stMetric"] {
            background: transparent;
            border: none;
            padding-left: 0;
            padding-right: 0;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _seed_filters_and_go(
    page_key: str,
    schema,
    updates: dict,
    **list_params,
) -> None:
    """Seed committed list filters, clear matching widgets, then navigate.

    Optional ``list_params`` are deep-link query/session params (e.g.
    ``customer=<id>``) so the filter survives the first load and stays in
    committed session filters for pagination, search, and sort.
    """
    key = filters_key(schema.entity_key)
    committed = st.session_state.setdefault(key, F.default_filters(schema))
    for field_key, value in updates.items():
        committed[field_key] = value
        st.session_state.pop(f"{schema.entity_key}_flt_{field_key}", None)
    navigation.go_to_list(page_key, **list_params)


def _related_tx_cols(width: int) -> int:
    if width >= 900:
        return 2
    return 1


def _label_with_count(label: str, count) -> str:
    if count is None:
        return label
    return f"{label} ({count})"


@st.dialog("Blacklist Customer", on_dismiss=make_dismiss_handler(C_BLACKLIST))
def _blacklist_customer_dialog(customer_service, customer_id: str):
    customer = customer_service.get_customer_detail(customer_id)
    if not customer:
        st.error("Customer not found")
        return
    st.warning(
        f"Blacklist **{customer.customer_name}**? "
        "New sales orders, invoices, and receipts will be blocked."
    )
    reason = st.text_area(
        "Reason",
        key="cd_blacklist_reason",
        placeholder="Optional reason for blacklisting",
    )
    cols = st.columns(2)
    if cols[0].button("Confirm Blacklist", type="primary", width="stretch"):
        from vaybooks.bms.domain.shared.exceptions import ValidationError

        try:
            customer_service.set_blacklisted(customer_id, True, reason)
            st.session_state.pop(C_BLACKLIST, None)
            st.success("Customer blacklisted")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(C_BLACKLIST, None)
        st.rerun()


def _quick_actions_section(
    customer,
    *,
    customer_account_id: str = "",
    can_create_sales_order: bool = False,
    can_create_invoice: bool = False,
    can_create_receipt: bool = False,
    can_create_customization_order: bool = False,
    can_create_project: bool = False,
    can_settle: bool = False,
) -> None:
    """Equal-width create toolbar under the profile header."""
    blacklisted = bool(getattr(customer, "is_blacklisted", False))
    # Settlement remains available while blacklisted (clearing receivable).
    any_action = any(
        (
            (not blacklisted)
            and (
                can_create_sales_order
                or can_create_invoice
                or can_create_receipt
                or can_create_customization_order
                or can_create_project
            ),
            can_settle,
        )
    )
    if not any_action:
        if blacklisted:
            with st.container(key="cust_qa", border=True):
                st.markdown("**Quick Actions**")
                st.caption(
                    "Creates are blocked while this customer is blacklisted."
                )
        return

    buttons: list[tuple] = []
    # Stable visual order: boutique → projects → sales → finance
    if not blacklisted and can_create_customization_order:
        buttons.append(
            (
                "order",
                ":material/checkroom: Customization Order",
                "cd_qa_co",
                "Create Customization Order for this customer",
            )
        )
    if not blacklisted and can_create_project:
        buttons.append(
            (
                "project",
                ":material/engineering: Project",
                "cd_qa_prj",
                "Create Project for this customer",
            )
        )
    if not blacklisted and can_create_sales_order:
        buttons.append(
            (
                "so",
                ":material/shopping_cart: Sales Order",
                "cd_qa_so",
                "Create Sales Order for this customer",
            )
        )
    if not blacklisted and can_create_invoice:
        buttons.append(
            (
                "inv",
                ":material/description: Sales Invoice",
                "cd_qa_inv",
                "Create Sales Invoice for this customer",
            )
        )
    if not blacklisted and can_create_receipt:
        buttons.append(
            (
                "rcpt",
                ":material/payments: Receipt",
                "cd_qa_rcpt",
                "Record Receipt for this customer",
            )
        )
    if can_settle:
        buttons.append(
            (
                "settle",
                ":material/account_balance: Settle",
                "cd_qa_settle",
                "Park receivable for Accounts approval (FIFO-clears open invoices)",
            )
        )

    width = viewport_width()
    if width >= 1100:
        per_row = min(5, max(len(buttons), 1))
    elif width >= 700:
        per_row = min(3, max(len(buttons), 1))
    else:
        per_row = min(2, max(len(buttons), 1))

    with st.container(key="cust_qa", border=True):
        st.markdown("**Quick Actions**")
        if blacklisted and can_settle:
            st.caption(
                "Creates are blocked while blacklisted — Settle remains available."
            )
        for row_start in range(0, len(buttons), per_row):
            row = buttons[row_start : row_start + per_row]
            # Pad to per_row so remaining buttons stay left-aligned at equal width
            cols = st.columns(per_row, gap="small")
            for idx in range(per_row):
                with cols[idx]:
                    if idx >= len(row):
                        continue
                    action, label, key, help_text = row[idx]
                    disabled = False
                    help_msg = help_text
                    if action == "rcpt" and not customer_account_id:
                        disabled = True
                        help_msg = (
                            "Customer ledger account required to record a receipt"
                        )
                    primary = row_start == 0 and idx == 0
                    if st.button(
                        label,
                        key=key,
                        type="primary" if primary else "secondary",
                        disabled=disabled,
                        help=help_msg,
                        width="stretch",
                    ):
                        _run_quick_action(
                            action,
                            customer,
                            customer_account_id=customer_account_id,
                        )


def _run_quick_action(
    action: str,
    customer,
    *,
    customer_account_id: str,
) -> None:
    if action == "so":
        arm_so_dialog(customer.id)
        st.rerun()
    elif action == "inv":
        arm_sales_record_dialog(customer.id)
        st.rerun()
    elif action == "rcpt":
        from vaybooks.bms.ui.pages.finance.accounts import list as acc

        st.session_state[acc.RCPT] = "new"
        st.session_state[acc.RCPT_PRESELECT_ACCOUNT] = customer_account_id
        st.rerun()
    elif action == "order":
        st.session_state.pop("order_workspace_order_id", None)
        st.session_state["order_workspace_step"] = "Customer"
        st.session_state["order_workspace_preselect_customer_id"] = customer.id
        navigation.go_to_list("order_workspace")
    elif action == "project":
        from vaybooks.bms.ui.pages.projects.wizard import (
            CREATE_DIALOG,
            WIZARD_DATA,
            WIZARD_STEP,
            _wizard_data,
        )

        st.session_state[CREATE_DIALOG] = True
        st.session_state[WIZARD_STEP] = 0
        data = _wizard_data()
        data["customer_label"] = (customer.customer_name or "").strip()
        st.session_state[WIZARD_DATA] = data
        navigation.go_to_list("projects_list")
    elif action == "settle":
        st.session_state[SETTLE] = customer_account_id
        st.rerun()


def _related_transactions_section(
    customer,
    *,
    customer_account_id: str = "",
    counts: dict | None = None,
    show_boutique: bool = False,
    show_sales: bool = False,
    show_finance: bool = False,
    show_projects: bool = False,
) -> None:
    """Related Transactions in a bordered two-column compact list."""
    counts = counts or {}
    rows: list[tuple] = []
    if show_boutique:
        rows.extend(
            [
                (
                    "Customization Orders",
                    counts.get("orders"),
                    "cd_rel_orders",
                    lambda: _seed_filters_and_go(
                        "orders_list",
                        ORDERS,
                        {"customer_id": customer.id},
                        customer=customer.id,
                    ),
                    True,
                ),
                (
                    "Measurements",
                    counts.get("measurements"),
                    "cd_rel_measurements",
                    lambda: _seed_filters_and_go(
                        "measurements_list",
                        MEASUREMENTS,
                        {"customer_id": customer.id},
                    ),
                    True,
                ),
            ]
        )
    if show_sales:
        rows.extend(
            [
                (
                    "Estimates",
                    counts.get("estimates"),
                    "cd_rel_estimates",
                    lambda: _seed_filters_and_go(
                        "estimates_list", ESTIMATES, {"customer_id": customer.id}
                    ),
                    True,
                ),
                (
                    "Quotations",
                    counts.get("quotations"),
                    "cd_rel_quotations",
                    lambda: _seed_filters_and_go(
                        "quotations_list", QUOTATIONS, {"customer_id": customer.id}
                    ),
                    True,
                ),
                (
                    "Sales Orders",
                    counts.get("sales_orders"),
                    "cd_rel_sales_orders",
                    lambda: _seed_filters_and_go(
                        "sales_orders_list",
                        SALES_ORDERS,
                        {"customer_id": customer.id},
                    ),
                    True,
                ),
                (
                    "Delivery Notes",
                    counts.get("delivery_notes"),
                    "cd_rel_delivery_notes",
                    lambda: _seed_filters_and_go(
                        "delivery_notes_list",
                        DELIVERY_NOTES,
                        {"customer_id": customer.id},
                    ),
                    True,
                ),
                (
                    "Sales Invoices",
                    counts.get("sales_invoices"),
                    "cd_rel_invoices",
                    (
                        (
                            lambda: _seed_filters_and_go(
                                "sales_invoices_list",
                                STORE_SALES,
                                {"customer_account_id": customer_account_id},
                            )
                        )
                        if customer_account_id
                        else None
                    ),
                    bool(customer_account_id),
                ),
                (
                    "Sales Returns",
                    counts.get("sales_returns"),
                    "cd_rel_returns",
                    lambda: _seed_filters_and_go(
                        "sales_returns_list",
                        SALES_RETURNS,
                        {"customer_id": customer.id},
                    ),
                    True,
                ),
            ]
        )
    if show_projects:
        from vaybooks.bms.ui.pages.projects.projects_list import PROJECTS

        rows.append(
            (
                "Projects",
                counts.get("projects"),
                "cd_rel_projects",
                lambda: _seed_filters_and_go(
                    "projects_list",
                    PROJECTS,
                    {"customer_id": customer.id},
                    customer=customer.id,
                ),
                True,
            )
        )
    if show_finance:
        rows.extend(
            [
                (
                    "Receipts",
                    counts.get("receipts"),
                    "cd_rel_receipts",
                    (
                        (
                            lambda: _seed_filters_and_go(
                                "receipts_list",
                                RECEIPTS,
                                {"customer_account_id": customer_account_id},
                            )
                        )
                        if customer_account_id
                        else None
                    ),
                    bool(customer_account_id),
                ),
                (
                    "Customer Ledger",
                    None,
                    "cd_rel_ledger",
                    (
                        (
                            lambda: navigation.go_to_detail(
                                "account_detail", customer_account_id
                            )
                        )
                        if customer_account_id
                        else None
                    ),
                    bool(customer_account_id),
                ),
            ]
        )

    if not rows:
        return

    width = viewport_width()
    n_cols = _related_tx_cols(width)
    mid = (len(rows) + 1) // 2 if n_cols == 2 else len(rows)
    columns = [rows[:mid], rows[mid:]] if n_cols == 2 else [rows]

    with st.container(key="cust_rel_tx", border=True):
        st.subheader("Related Transactions")
        grid = st.columns(n_cols)
        for col_idx, col_rows in enumerate(columns):
            with grid[col_idx]:
                for label, count, btn_key, on_click, enabled in col_rows:
                    left, right = st.columns([4, 1], vertical_alignment="center")
                    left.markdown(_label_with_count(label, count))
                    if enabled and on_click:
                        if right.button("View", key=btn_key):
                            on_click()
                            st.rerun()
                    else:
                        right.button("View", key=btn_key, disabled=True)


def _render_metric_section(
    title: str,
    metrics: list[tuple],
    *,
    key: str,
) -> None:
    """One module card: title + equal-width metrics for that section only."""
    if not metrics:
        return
    with st.container(key=key, border=True):
        st.markdown(f"**{title}**")
        cols = st.columns(len(metrics), gap="small")
        for offset, metric in enumerate(metrics):
            label, value = metric[0], metric[1]
            badge = metric[2] if len(metric) > 2 else None
            with cols[offset]:
                st.metric(label, value)
                if badge:
                    st.markdown(badge, unsafe_allow_html=True)


def _render_overview_metrics(
    sections: list[tuple[str, list[tuple], str]],
    *,
    width: int,
) -> None:
    """Render module metric cards in a responsive 1–2 column grid."""
    if not sections:
        return
    n_cols = 2 if width >= 900 and len(sections) > 1 else 1
    with st.container(key="cust_metrics"):
        for row_start in range(0, len(sections), n_cols):
            row = sections[row_start : row_start + n_cols]
            cols = st.columns(n_cols, gap="medium")
            for idx in range(n_cols):
                with cols[idx]:
                    if idx >= len(row):
                        continue
                    title, metrics, key = row[idx]
                    _render_metric_section(title, metrics, key=key)


def _render_crm_section(services: dict, customer) -> None:
    """Render the CRM panel, skipping it when the CRM module is absent."""
    try:
        from vaybooks.bms.ui.components.crm.customer_section import (
            render_customer_crm_section,
        )
    except Exception:
        return
    try:
        render_customer_crm_section(services, customer)
    except Exception as exc:  # noqa: BLE001 - CRM must never break this page
        st.caption(f"CRM section unavailable: {exc}")


def render(services: dict):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import get_submit_map, set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired
    from vaybooks.bms.ui.pages.parties.customers.list import (
        C_EDIT,
        SUBMIT_EDIT,
        _edit_customer_dialog,
        _open_edit_customer,
    )

    set_current_page("customer_detail")
    mark_wired("nav.back", "customers.back", "customers.save", "dialog.save")

    customer_service = services["customers"]
    order_service = services.get("orders")
    accounting = services.get("accounting")
    sales = services.get("sales")
    measurements = services.get("measurements")
    projects = services.get("projects")

    # Gate on org-enabled modules (not can_permission("module.*")).
    # Roles grant concrete permissions only — module.* keys are never in the
    # user∩entitlement effective set, so can_permission("module.X") is always false.
    auth = services.get("authorization")
    if auth is None:
        enabled_modules = {
            "finance",
            "boutique",
            "sales",
            "projects",
        }
    else:
        try:
            enabled_modules = {
                (m or "").strip()
                for m in (auth.get_org_entitlement().enabled_modules or [])
                if (m or "").strip()
            }
        except Exception:
            enabled_modules = set()

    show_finance = "finance" in enabled_modules and accounting is not None
    show_boutique = "boutique" in enabled_modules and order_service is not None
    show_sales = "sales" in enabled_modules and sales is not None
    show_projects = "projects" in enabled_modules and projects is not None

    customer_id = navigation.current_detail_id("customer_detail")

    _inject_page_css()
    with st.container(key="cust_view_shell"):
        if st.button(
            "← Back to customers", key="customer_back"
        ) or consume_action("nav.back"):
            navigation.go_back_to_list("customers", "customers_list")
            return

        customer = (
            customer_service.get_customer_detail(customer_id) if customer_id else None
        )
        if not customer:
            st.error("Customer not found.")
            return

        title_col, edit_col, bl_col = st.columns(
            [4, 1.2, 1.2], vertical_alignment="center"
        )
        with title_col:
            display_name = (customer.customer_name or "").strip() or (
                (customer.phone_number or "").strip() or "Unnamed customer"
            )
            st.title(display_name)
            if customer.is_blacklisted:
                reason = customer.blacklist_reason or "no reason recorded"
                st.error(f":material/block: Blacklisted — {reason}")
        with edit_col:
            if st.button(
                ":material/edit: Edit Customer",
                key="cd_edit_customer",
            ):
                _open_edit_customer(customer.id)
                st.rerun()
        with bl_col:
            if customer.is_blacklisted:
                if st.button(
                    ":material/check_circle: Remove Blacklist",
                    key="cd_unblacklist",
                ):
                    customer_service.set_blacklisted(customer.id, False)
                    st.success("Blacklist removed")
                    st.rerun()
            else:
                if st.button(
                    ":material/block: Blacklist",
                    key="cd_blacklist",
                ):
                    st.session_state[C_BLACKLIST] = customer.id
                    st.rerun()

        with panel(f"cust_head_{customer.id}"):
            with st.container(border=True):
                info = st.columns(3)
                info[0].write(f"**Phone:** {customer.phone_number}")
                info[1].write(
                    f"**Alt:** {customer.alternate_phone_number or '—'}"
                )
                info[2].write(f"**Since:** {_fmt_date(customer.created_at)}")
                if customer.contact_person:
                    st.caption(f"Contact: {customer.contact_person}")
                if customer.email:
                    st.caption(f"Email: {customer.email}")
                if customer.formatted_address:
                    st.caption(f"Address: {customer.formatted_address}")
                tax_bits = []
                if customer.registration_type:
                    tax_bits.append(
                        f"Registration: {customer.registration_type.value}"
                    )
                if customer.gstin:
                    tax_bits.append(f"GSTIN: {customer.gstin}")
                if customer.pan:
                    tax_bits.append(f"PAN: {customer.pan}")
                if customer.msme_number:
                    tax_bits.append(f"MSME: {customer.msme_number}")
                if tax_bits:
                    st.caption(" · ".join(tax_bits))
                if customer.notes:
                    st.caption(f"Notes: {customer.notes}")

        boutique_summary = {
            "order_count": 0,
            "active_count": 0,
            "total_invoiced": 0.0,
        }
        if show_boutique and order_service:
            try:
                boutique_summary = order_service.get_customer_summary(customer.id)
            except Exception:
                pass

        try:
            account = (
                accounting.get_customer_account(customer.id) if accounting else None
            )
            balance = account.current_balance if account else 0.0
            customer_account_id = account.id if account else ""
        except Exception:
            balance = 0.0
            customer_account_id = ""

        credit_available = 0.0
        advance_available = 0.0
        parked_settlement = 0.0
        receivable_balance = 0.0
        if show_finance and accounting and customer_account_id:
            try:
                credit_available = accounting.customer_credit_balance(
                    customer_account_id
                )
            except Exception:
                pass
            try:
                advance_available = accounting.get_customer_unapplied_advance(
                    customer_account_id
                )
            except Exception:
                pass
            try:
                parked_settlement = accounting.get_customer_parked_settlement(
                    customer_account_id
                )
            except Exception:
                pass
            try:
                receivable_balance = accounting.customer_receivable_balance(
                    customer_account_id
                )
            except Exception:
                pass

        sales_counts: dict = {}
        sales_outstanding = 0.0
        if show_sales and sales:
            try:
                sales_counts = sales.related_document_counts(
                    customer.id, customer_account_id=customer_account_id
                )
            except Exception:
                pass
            if accounting and customer_account_id:
                try:
                    open_rows = accounting.list_open_sales_invoices_for_customer(
                        customer_account_id
                    )
                    sales_outstanding = round(
                        sum(float(r.get("outstanding") or 0) for r in open_rows), 2
                    )
                except Exception:
                    pass

        project_summary = {
            "project_count": 0,
            "active_count": 0,
            "contract_value": 0.0,
        }
        if show_projects and projects:
            try:
                project_summary = projects.get_customer_summary(customer.id)
            except Exception:
                pass

        total_orders = int(boutique_summary.get("order_count") or 0)
        status_label, status_color = _balance_status(balance)
        width = viewport_width()

        not_blacklisted = not customer.is_blacklisted
        can_settle = (
            show_finance
            and bool(customer_account_id)
            and (receivable_balance > 0.01 or parked_settlement > 0.01)
        )
        _quick_actions_section(
            customer,
            customer_account_id=customer_account_id,
            can_create_sales_order=show_sales and not_blacklisted,
            can_create_invoice=show_sales
            and show_finance
            and not_blacklisted,
            can_create_receipt=show_finance and not_blacklisted,
            can_create_customization_order=show_boutique and not_blacklisted,
            can_create_project=show_projects and not_blacklisted,
            can_settle=can_settle,
        )

        overview_sections: list[tuple[str, list[tuple], str]] = []
        if show_finance:
            account_metrics: list[tuple] = [
                (
                    "Balance",
                    _format_balance_amount(balance),
                    status_badge(status_label, status_color, compact=True),
                ),
                ("Credit", f"\u20b9{credit_available:,.2f}"),
                ("Advance", f"\u20b9{advance_available:,.2f}"),
            ]
            if parked_settlement > 0.01:
                account_metrics.append(
                    ("Settlement", f"\u20b9{parked_settlement:,.2f}")
                )
            overview_sections.append(
                (
                    "Account",
                    account_metrics,
                    "cust_metric_card_account",
                )
            )
        if show_boutique:
            overview_sections.append(
                (
                    "Customization",
                    [
                        ("Orders", str(total_orders)),
                        (
                            "Active",
                            str(boutique_summary.get("active_count", 0)),
                        ),
                        (
                            "Invoiced",
                            f"\u20b9{boutique_summary.get('total_invoiced', 0.0):,.0f}",
                        ),
                    ],
                    "cust_metric_card_boutique",
                )
            )
        if show_sales:
            overview_sections.append(
                (
                    "Sales",
                    [
                        (
                            "Orders",
                            str(sales_counts.get("sales_orders", 0)),
                        ),
                        (
                            "Invoices",
                            str(sales_counts.get("sales_invoices", 0)),
                        ),
                        ("Outstanding", f"\u20b9{sales_outstanding:,.0f}"),
                    ],
                    "cust_metric_card_sales",
                )
            )
        if show_projects:
            overview_sections.append(
                (
                    "Projects",
                    [
                        (
                            "Projects",
                            str(project_summary.get("project_count", 0)),
                        ),
                        (
                            "Active",
                            str(project_summary.get("active_count", 0)),
                        ),
                        (
                            "Contract",
                            f"\u20b9{project_summary.get('contract_value', 0.0):,.0f}",
                        ),
                    ],
                    "cust_metric_card_projects",
                )
            )
        _render_overview_metrics(overview_sections, width=width)

        if show_finance:
            _credit_actions_section(
                services,
                customer,
                customer_account_id=customer_account_id,
                balance=balance,
            )

        counts: dict = dict(sales_counts)
        counts["orders"] = total_orders
        counts["projects"] = int(project_summary.get("project_count") or 0)
        if show_boutique and measurements is not None:
            try:
                counts["measurements"] = len(
                    measurements.list_by_customer(customer.id)
                )
            except Exception:
                pass

        _related_transactions_section(
            customer,
            customer_account_id=customer_account_id,
            counts=counts,
            show_boutique=show_boutique,
            show_sales=show_sales,
            show_finance=show_finance,
            show_projects=show_projects,
        )

        _render_crm_section(services, customer)

        if show_boutique and order_service:
            with st.container(border=True):
                st.subheader("Recent Customization Orders")

                try:
                    recent = order_service.list_recent_by_customer(
                        customer.id, RECENT_ORDER_LIMIT
                    )
                except Exception:
                    recent = []

                if not recent:
                    st.markdown(
                        "<div style='text-align:center;padding:1.25rem 0.5rem;"
                        "color:#5B5560;'>No customization orders yet.</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    order_cards(
                        recent,
                        key_prefix=f"cd_ord_{customer.id}",
                        view_label="View Details",
                        view_full_width=False,
                    )
                    if total_orders > RECENT_ORDER_LIMIT:
                        st.caption(
                            f"Showing latest {RECENT_ORDER_LIMIT} of "
                            f"{total_orders} orders."
                        )

        if st.session_state.get(C_EDIT):
            get_submit_map().setdefault(C_EDIT, SUBMIT_EDIT)
            register_armed_dialog(C_EDIT)
            _edit_customer_dialog(
                customer_service, st.session_state[C_EDIT], services
            )

        if st.session_state.get(C_BLACKLIST):
            register_armed_dialog(C_BLACKLIST)
            _blacklist_customer_dialog(
                customer_service, st.session_state[C_BLACKLIST]
            )

        open_so_dialog_if_armed(services)
        open_sales_record_dialog_if_armed(services)
        if services.get("accounting"):
            from vaybooks.bms.ui.pages.finance.accounts import list as acc

            if st.session_state.get(acc.RCPT):
                acc._receipt_dialog(services["accounting"])
            if st.session_state.get(REFUND):
                register_armed_dialog(REFUND)
                _customer_refund_dialog(
                    services["accounting"], st.session_state[REFUND]
                )
            if st.session_state.get(MOVE_ADVANCE):
                register_armed_dialog(MOVE_ADVANCE)
                _customer_move_advance_dialog(
                    services,
                    customer.id,
                    customer_account_id,
                )
            if st.session_state.get(SETTLE):
                register_armed_dialog(SETTLE)
                _customer_settle_dialog(
                    services["accounting"], st.session_state[SETTLE]
                )
