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
from vaybooks.bms.ui.dialog_utils import register_armed_dialog
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
    return "Customer Advance/Credit", "green"


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
            padding: 0.4rem 0.75rem;
          }
          div[class*="st-key-cust_qa"] div.stButton > button {
            height: 36px;
            min-height: 36px;
            padding: 0.2rem 0.7rem;
            white-space: nowrap;
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


def _summary_metric_cols(width: int) -> int:
    if width >= 1100:
        return 4
    if width >= 700:
        return 2
    return 1


def _related_tx_cols(width: int) -> int:
    if width >= 900:
        return 2
    return 1


def _label_with_count(label: str, count) -> str:
    if count is None:
        return label
    return f"{label} ({count})"


def _quick_actions_section(
    customer,
    *,
    customer_account_id: str = "",
    can_create_sales_order: bool = True,
    can_create_invoice: bool = True,
    can_create_receipt: bool = True,
) -> None:
    """Compact create toolbar — separate from Related Transactions (view-only)."""
    width = viewport_width()
    desktop = width >= 700

    with st.container(key="cust_qa", border=True):
        if desktop:
            label_col, actions_col = st.columns(
                [1.4, 3.6], vertical_alignment="center"
            )
            with label_col:
                st.markdown("**Quick Actions**")
            with actions_col:
                b1, b2, b3 = st.columns([1, 1, 1.15], gap="small")
                _render_quick_action_buttons(
                    customer,
                    customer_account_id=customer_account_id,
                    can_create_sales_order=can_create_sales_order,
                    can_create_invoice=can_create_invoice,
                    can_create_receipt=can_create_receipt,
                    cols=(b1, b2, b3),
                )
        else:
            st.markdown("**Quick Actions**")
            b1, b2, b3 = st.columns(3, gap="small")
            _render_quick_action_buttons(
                customer,
                customer_account_id=customer_account_id,
                can_create_sales_order=can_create_sales_order,
                can_create_invoice=can_create_invoice,
                can_create_receipt=can_create_receipt,
                cols=(b1, b2, b3),
            )


def _render_quick_action_buttons(
    customer,
    *,
    customer_account_id: str,
    can_create_sales_order: bool,
    can_create_invoice: bool,
    can_create_receipt: bool,
    cols,
) -> None:
    b1, b2, b3 = cols
    if can_create_sales_order:
        if b1.button(
            ":material/shopping_cart: + Sales Order",
            key="cd_qa_so",
            type="primary",
            help="Create Sales Order for this customer",
        ):
            arm_so_dialog(customer.id)
            st.rerun()
    if can_create_invoice:
        if b2.button(
            ":material/description: + Invoice",
            key="cd_qa_inv",
            help="Create Sales Invoice for this customer",
        ):
            arm_sales_record_dialog(customer.id)
            st.rerun()
    if can_create_receipt:
        receipt_ok = bool(customer_account_id)
        if b3.button(
            ":material/payments: Record Receipt",
            key="cd_qa_rcpt",
            disabled=not receipt_ok,
            help=(
                "Record Receipt for this customer"
                if receipt_ok
                else "Customer ledger account required to record a receipt"
            ),
        ):
            from vaybooks.bms.ui.pages.finance.accounts import list as acc

            st.session_state[acc.RCPT] = "new"
            st.session_state[acc.RCPT_PRESELECT_ACCOUNT] = customer_account_id
            st.rerun()


def _related_transactions_section(
    customer,
    *,
    customer_account_id: str = "",
    counts: dict | None = None,
) -> None:
    """Related Transactions in a bordered two-column compact list."""
    counts = counts or {}
    rows = [
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
                "measurements_list", MEASUREMENTS, {"customer_id": customer.id}
            ),
            True,
        ),
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
                "sales_orders_list", SALES_ORDERS, {"customer_id": customer.id}
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
    order_service = services["orders"]
    accounting = services.get("accounting")
    sales = services.get("sales")
    measurements = services.get("measurements")

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

        title_col, edit_col = st.columns([5, 1], vertical_alignment="center")
        with title_col:
            st.title(customer.customer_name)
        with edit_col:
            if st.button(
                ":material/edit: Edit Customer",
                key="cd_edit_customer",
            ):
                _open_edit_customer(customer.id)
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

        try:
            summary = order_service.get_customer_summary(customer.id)
        except Exception:
            summary = {
                "order_count": 0,
                "active_count": 0,
                "total_invoiced": 0.0,
            }

        try:
            account = (
                accounting.get_customer_account(customer.id) if accounting else None
            )
            balance = account.current_balance if account else 0.0
            customer_account_id = account.id if account else ""
        except Exception:
            balance = 0.0
            customer_account_id = ""

        total_orders = summary.get("order_count", 0)
        status_label, status_color = _balance_status(balance)

        width = viewport_width()
        n_metric_cols = _summary_metric_cols(width)
        metrics = [
            ("Total Orders", str(total_orders)),
            ("Active Orders", str(summary.get("active_count", 0))),
            (
                "Total Invoiced",
                f"\u20b9{summary.get('total_invoiced', 0.0):,.0f}",
            ),
            ("Balance", _format_balance_amount(balance)),
        ]
        for row_start in range(0, len(metrics), n_metric_cols):
            row = metrics[row_start : row_start + n_metric_cols]
            cols = st.columns(n_metric_cols)
            for offset, metric in enumerate(row):
                label, value = metric[0], metric[1]
                with cols[offset]:
                    st.metric(label, value, border=True)
                    if label == "Balance":
                        st.markdown(
                            status_badge(status_label, status_color, compact=True),
                            unsafe_allow_html=True,
                        )

        # No module-level create RBAC for sales/receipts yet — show when
        # the matching services exist (same gate as the list-page create buttons).
        _quick_actions_section(
            customer,
            customer_account_id=customer_account_id,
            can_create_sales_order=sales is not None,
            can_create_invoice=sales is not None and accounting is not None,
            can_create_receipt=accounting is not None,
        )

        counts: dict = {}
        if sales is not None:
            try:
                counts.update(
                    sales.related_document_counts(
                        customer.id, customer_account_id=customer_account_id
                    )
                )
            except Exception:
                pass
        counts["orders"] = total_orders
        if measurements is not None:
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
        )

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
            _edit_customer_dialog(customer_service, st.session_state[C_EDIT])

        open_so_dialog_if_armed(services)
        open_sales_record_dialog_if_armed(services)
        if services.get("accounting"):
            from vaybooks.bms.ui.pages.finance.accounts import list as acc

            if st.session_state.get(acc.RCPT):
                acc._receipt_dialog(services["accounting"])
