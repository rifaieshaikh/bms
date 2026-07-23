"""Vendor detail route (`?id=<vendor_id>`): profile, dashboard, purchases."""

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.voucher_card import (
    voucher_display_amount,
)
from vaybooks.bms.ui.components.purchases.purchase_bill_dialog import (
    arm_purchase_bill_dialog,
    open_purchase_bill_dialog_if_armed,
)
from vaybooks.bms.ui.components.purchases.purchase_order_card import (
    _po_row,
    purchase_order_cards,
)
from vaybooks.bms.ui.components.purchases.purchase_order_dialog import (
    arm_po_dialog,
    open_po_dialog_if_armed,
)
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import open_dialog
from vaybooks.bms.ui.purchase_list_schemas import (
    GOODS_RECEIPTS,
    PURCHASE_ORDERS,
    PURCHASE_RETURNS,
    STORE_PURCHASES,
)
from vaybooks.bms.ui.responsive import viewport_width
from vaybooks.bms.ui.session_keys import filters_key
from vaybooks.bms.ui.styles import panel, status_badge

RECENT_PO_LIMIT = 5
RECENT_PAYMENT_LIMIT = 5


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _balance_status(balance: float) -> tuple[str, str]:
    """Return (status label, badge color) from vendor ledger balance."""
    if abs(balance) < 0.01:
        return "Settled", "gray"
    if balance > 0:
        return "Amount Payable", "red"
    return "Vendor Advance", "green"


def _format_balance_amount(balance: float) -> str:
    return f"\u20b9{balance:,.2f}"


def _inject_page_css() -> None:
    st.markdown(
        """
        <style>
          div[class*="st-key-vend_view_shell"] {
            max-width: 1480px;
            margin-left: auto;
            margin-right: auto;
            padding-left: 28px;
            padding-right: 28px;
          }
          @media (max-width: 1100px) {
            div[class*="st-key-vend_view_shell"] {
              padding-left: 22px;
              padding-right: 22px;
            }
          }
          @media (max-width: 700px) {
            div[class*="st-key-vend_view_shell"] {
              padding-left: 16px;
              padding-right: 16px;
            }
          }
          div[class*="st-key-vend_rel_tx"]
            div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.5rem 0.75rem;
          }
          div[class*="st-key-vend_rel_row"] {
            border-bottom: 1px solid rgba(49, 51, 63, 0.12);
            padding: 0.45rem 0.15rem;
            min-height: 44px;
            transition: background-color 0.15s ease;
          }
          div[class*="st-key-vend_rel_row"]:last-of-type {
            border-bottom: none;
          }
          div[class*="st-key-vend_rel_row"]:hover {
            background-color: rgba(49, 51, 63, 0.04);
            border-radius: 0.35rem;
          }
          div[class*="st-key-vend_rel_tx"] div.stButton > button {
            min-width: 76px;
            max-width: 96px;
            height: 34px;
            padding: 0.2rem 0.55rem;
            width: auto !important;
          }
          div[class*="st-key-vend_view_shell"] div[data-testid="stMetric"] {
            height: 100%;
          }
          div[class*="st-key-vend_bal_card"]
            div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.85rem 1rem 0.75rem;
            height: 100%;
          }
          div[class*="st-key-vend_bal_card"] .vend-bal-label {
            font-size: 0.875rem;
            color: rgba(49, 51, 63, 0.6);
            margin-bottom: 0.15rem;
          }
          div[class*="st-key-vend_bal_card"] .vend-bal-value {
            font-size: 1.75rem;
            font-weight: 600;
            line-height: 1.25;
            margin: 0 0 0.4rem 0;
          }
          div[class*="st-key-vend_qa"]
            div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.4rem 0.75rem;
          }
          div[class*="st-key-vend_qa"] div.stButton > button,
          div[class*="st-key-vend_hdr"] div.stButton > button,
          div[class*="st-key-vend_pay_sec"] div.stButton > button {
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


def _seed_filters_and_go(
    page_key: str,
    schema,
    updates: dict,
    **list_params,
) -> None:
    """Seed committed list filters, clear matching widgets, then navigate."""
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


def _label_with_count(label: str, count) -> str:
    if count is None:
        return label
    return f"{label} ({count})"


def _quick_actions_section(
    vendor,
    *,
    can_create_po: bool = True,
    can_create_bill: bool = True,
    can_record_payment: bool = True,
) -> None:
    """Compact create toolbar — separate from Related Transactions (view-only)."""
    width = viewport_width()
    desktop = width >= 700

    with st.container(key="vend_qa", border=True):
        if desktop:
            label_col, actions_col = st.columns(
                [1.4, 3.6], vertical_alignment="center"
            )
            with label_col:
                st.markdown("**Quick Actions**")
            with actions_col:
                b1, b2, b3 = st.columns([1, 1, 1.15], gap="small")
                _render_quick_action_buttons(
                    vendor,
                    can_create_po=can_create_po,
                    can_create_bill=can_create_bill,
                    can_record_payment=can_record_payment,
                    cols=(b1, b2, b3),
                )
        else:
            st.markdown("**Quick Actions**")
            b1, b2, b3 = st.columns(3, gap="small")
            _render_quick_action_buttons(
                vendor,
                can_create_po=can_create_po,
                can_create_bill=can_create_bill,
                can_record_payment=can_record_payment,
                cols=(b1, b2, b3),
            )


def _render_quick_action_buttons(
    vendor,
    *,
    can_create_po: bool,
    can_create_bill: bool,
    can_record_payment: bool,
    cols,
) -> None:
    from vaybooks.bms.ui.pages.parties.vendors.list import V_PAY

    b1, b2, b3 = cols
    if can_create_po:
        if b1.button(
            ":material/shopping_cart: + Purchase Order",
            key="vd_qa_po",
            type="primary",
            help="Create Purchase Order for this vendor",
        ):
            arm_po_dialog(vendor_id=vendor.id)
            st.rerun()
    if can_create_bill:
        if b2.button(
            ":material/description: + Purchase Bill",
            key="vd_qa_bill",
            help="Record Purchase Bill for this vendor",
        ):
            arm_purchase_bill_dialog(vendor_id=vendor.id)
            st.rerun()
    if can_record_payment:
        if b3.button(
            ":material/payments: Record Payment",
            key="vd_qa_pay",
            help="Record a payment for this vendor",
        ):
            clear_all_dialog_flags()
            st.session_state[V_PAY] = "new"
            st.rerun()


def _related_transactions_section(
    vendor,
    *,
    counts: dict | None = None,
) -> None:
    """Related Transactions as a single vertical purchasing workflow list."""
    counts = counts or {}
    rows = [
        (
            "Purchase Orders",
            counts.get("purchase_orders"),
            "vd_rel_po",
            lambda: _seed_filters_and_go(
                "purchase_orders_list",
                PURCHASE_ORDERS,
                {"vendor_id": vendor.id},
                vendor=vendor.id,
            ),
        ),
        (
            "Goods Receipts",
            counts.get("goods_receipts"),
            "vd_rel_grn",
            lambda: _seed_filters_and_go(
                "goods_receipt_list",
                GOODS_RECEIPTS,
                {"vendor_id": vendor.id},
                vendor=vendor.id,
            ),
        ),
        (
            "Purchase Bills",
            counts.get("purchase_bills"),
            "vd_rel_bills",
            lambda: _seed_filters_and_go(
                "purchases_list",
                STORE_PURCHASES,
                {"vendor_id": vendor.id},
                vendor=vendor.id,
            ),
        ),
        (
            "Purchase Returns",
            counts.get("purchase_returns"),
            "vd_rel_returns",
            lambda: _seed_filters_and_go(
                "purchase_returns_list",
                PURCHASE_RETURNS,
                {"vendor_id": vendor.id},
                vendor=vendor.id,
            ),
        ),
    ]

    with st.container(key="vend_rel_tx", border=True):
        st.subheader("Related Transactions")
        for index, (label, count, btn_key, on_click) in enumerate(rows):
            with st.container(key=f"vend_rel_row_{index}"):
                left, right = st.columns([5, 1], vertical_alignment="center")
                left.markdown(_label_with_count(label, count))
                if right.button("View All", key=btn_key):
                    on_click()
                    st.rerun()


def _open_edit_vendor(vendor_id: str) -> None:
    from vaybooks.bms.ui.pages.parties.vendors.list import SUBMIT_EDIT, V_EDIT

    clear_all_dialog_flags()
    open_dialog(V_EDIT, submit_key=SUBMIT_EDIT, value=vendor_id, clear_others=False)


def _info_card(vendor, vendor_account) -> None:
    """Compact vendor profile — only core fields; payable lives in summary cards."""
    with panel(f"vend_head_{vendor.id}"):
        with st.container(border=True):
            row1 = st.columns(3)
            row1[0].write(f"**Phone:** {vendor.phone_number}")
            row1[1].write(f"**Alt:** {vendor.alternate_phone_number or '—'}")
            row1[2].write(
                f"**System Account:** "
                f"{vendor_account.account_name if vendor_account else '—'}"
            )
            if vendor.formatted_address:
                st.caption(f"Address: {vendor.formatted_address}")
            tax_bits = []
            if vendor.registration_type:
                tax_bits.append(f"Registration: {vendor.registration_type.value}")
            if vendor.gstin:
                tax_bits.append(f"GSTIN: {vendor.gstin}")
            if vendor.pan:
                tax_bits.append(f"PAN: {vendor.pan}")
            if tax_bits:
                st.caption(" · ".join(tax_bits))


def _payable_balance_card(
    amount_label: str,
    amount_value: str,
    status_label: str,
    status_color: str,
) -> None:
    """Payable Balance metric with status badge inside the same card."""
    with st.container(key="vend_bal_card", border=True):
        st.markdown(
            f'<div class="vend-bal-label">{amount_label}</div>'
            f'<p class="vend-bal-value">{amount_value}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            status_badge(status_label, status_color, compact=True),
            unsafe_allow_html=True,
        )


def _payment_method(voucher) -> str:
    if voucher.voucher_type == VoucherType.VENDOR_PAYMENT and len(voucher.lines) > 3:
        name = (voucher.lines[3].account_name or "").strip()
        if name:
            return name
    for line in voucher.lines:
        desc = (line.description or "").strip()
        if desc == "Payment made" and line.credit_amount > 0:
            return (line.account_name or "").strip() or "—"
    return "—"


def _payment_reference(voucher, service_names: dict) -> str:
    bits = []
    service_id = getattr(voucher, "reference_service_id", None)
    if service_id and service_id in service_names:
        bits.append(service_names[service_id])
    order_id = getattr(voucher, "reference_order_id", None)
    if order_id:
        bits.append(f"Order {order_id[:8]}")
    desc = (voucher.description or "").strip()
    if desc and not bits:
        bits.append(desc[:60])
    elif desc and desc not in bits:
        bits.append(desc[:40])
    return " · ".join(bits) if bits else "—"


def _collect_recent_payments(services, vendor, vendor_account, limit: int = 5):
    """Latest payment vouchers for this vendor (legacy + purchase-bill payments)."""
    accounting = services.get("accounting")
    purchases = services.get("purchases")
    by_id = {}
    if not accounting or not vendor_account:
        return []

    try:
        for voucher in accounting.list_vendor_payments(vendor_account.id):
            by_id[voucher.id] = voucher
    except Exception:
        pass

    if purchases is not None:
        try:
            for row in purchases.list_purchase_bills():
                if (
                    row.get("vendor_id") != vendor.id
                    and row.get("vendor_account_id") != vendor_account.id
                ):
                    continue
                paid = float(row.get("paid") or 0)
                vtype = str(row.get("voucher_type") or "")
                if paid < 0.01 and "Payment" not in vtype:
                    continue
                voucher = accounting.get_voucher(row.get("id"))
                if voucher:
                    by_id[voucher.id] = voucher
        except Exception:
            pass

    ordered = sorted(
        by_id.values(),
        key=lambda v: (v.voucher_date or date.min, v.voucher_number or ""),
        reverse=True,
    )
    return ordered[:limit]


def _render_recent_payments(services, vendor, vendor_account) -> None:
    payments = _collect_recent_payments(
        services, vendor, vendor_account, RECENT_PAYMENT_LIMIT
    )
    vendor_services = services.get("vendor_services")
    service_names = {}
    if vendor_services is not None:
        try:
            service_names = {
                s.id: s.service_name
                for s in vendor_services.list_services(active_only=False)
            }
        except Exception:
            service_names = {}

    with st.container(key="vend_pay_sec", border=True):
        head_l, head_r = st.columns([4, 1], vertical_alignment="center")
        with head_l:
            st.subheader("Recent Payments")
        with head_r:
            if vendor_account and st.button(
                "View All Payments",
                key="vd_view_all_payments",
                help="Purchase bills and vendor payments for this vendor",
            ):
                _seed_filters_and_go(
                    "purchases_list",
                    STORE_PURCHASES,
                    {"vendor_id": vendor.id},
                    vendor=vendor.id,
                )
                st.rerun()

        if not payments:
            st.markdown(
                "<div style='text-align:center;padding:1.25rem 0.5rem;"
                "color:#5B5560;'>No payments recorded yet.</div>",
                unsafe_allow_html=True,
            )
        else:
            for voucher in payments:
                with st.container(border=True):
                    st.markdown(f"**{voucher.voucher_number}**")
                    st.caption(_fmt_date(voucher.voucher_date))
                    st.caption(f"Method: {_payment_method(voucher)}")
                    st.markdown(f"₹{voucher_display_amount(voucher):,.0f}")
                    ref = _payment_reference(voucher, service_names)
                    if ref and ref != "—":
                        st.caption(f"Ref: {ref}")
                    if st.button(
                        "View Details",
                        key=f"vd_pay_view_{voucher.id}",
                    ):
                        navigation.go_to_detail("purchase_detail", voucher.id)
                        st.rerun()


def render(services: dict):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import get_submit_map, set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired
    from vaybooks.bms.ui.pages.parties.vendors.list import (
        SUBMIT_EDIT,
        V_EDIT,
        V_PAY,
        _edit_vendor_dialog,
        _pay_vendor_dialog,
    )

    set_current_page("vendor_detail")
    mark_wired("nav.back", "vendors.back", "vendors.save", "dialog.save")

    vendor_service = services["vendors"]
    accounting = services.get("accounting")
    purchases = services.get("purchases")
    vendor_id = navigation.current_detail_id("vendor_detail")

    _inject_page_css()
    with st.container(key="vend_view_shell"):
        if st.button(
            "← Back to vendors", key="vendor_back"
        ) or consume_action("nav.back"):
            navigation.go_back_to_list("vendors", "vendors_list")
            return

        if not vendor_id:
            st.error("No vendor selected.")
            return

        vendor = vendor_service.get_vendor_detail(vendor_id)
        if not vendor:
            st.error("Vendor not found.")
            return

        title_col, edit_col = st.columns([5, 1], vertical_alignment="center")
        with title_col:
            st.title(vendor.vendor_name)
        with edit_col:
            with st.container(key="vend_hdr"):
                if st.button(
                    ":material/edit: Edit Vendor",
                    key="vd_edit_vendor",
                ):
                    _open_edit_vendor(vendor.id)
                    st.rerun()

        try:
            vendor_account = (
                accounting.get_vendor_account(vendor.id) if accounting else None
            )
            balance = vendor_account.current_balance if vendor_account else 0.0
            vendor_account_id = vendor_account.id if vendor_account else ""
        except Exception:
            vendor_account = None
            balance = 0.0
            vendor_account_id = ""

        _info_card(vendor, vendor_account)

        try:
            summary = (
                purchases.get_vendor_summary(vendor.id) if purchases else {}
            )
        except Exception:
            summary = {
                "po_count": 0,
                "open_count": 0,
                "total_billed": 0.0,
            }

        total_pos = summary.get("po_count", 0)
        status_label, status_color = _balance_status(balance)

        width = viewport_width()
        n_metric_cols = _summary_metric_cols(width)
        metrics = [
            ("Total Purchase Orders", str(total_pos), False),
            ("Open Purchase Orders", str(summary.get("open_count", 0)), False),
            (
                "Total Billed Amount",
                f"\u20b9{summary.get('total_billed', 0.0):,.0f}",
                False,
            ),
            ("Payable Balance", _format_balance_amount(balance), True),
        ]
        for row_start in range(0, len(metrics), n_metric_cols):
            row = metrics[row_start : row_start + n_metric_cols]
            cols = st.columns(len(row))
            for offset, (label, value, is_balance) in enumerate(row):
                with cols[offset]:
                    if is_balance:
                        _payable_balance_card(
                            label, value, status_label, status_color
                        )
                    else:
                        st.metric(label, value, border=True)

        _quick_actions_section(
            vendor,
            can_create_po=purchases is not None,
            can_create_bill=purchases is not None and accounting is not None,
            can_record_payment=accounting is not None and purchases is not None,
        )

        counts: dict = {}
        if purchases is not None:
            try:
                counts.update(
                    purchases.related_document_counts(
                        vendor.id, vendor_account_id=vendor_account_id
                    )
                )
            except Exception:
                pass
        counts.setdefault("purchase_orders", total_pos)

        _related_transactions_section(vendor, counts=counts)

        with st.container(border=True):
            st.subheader("Recent Purchase Orders")
            try:
                recent = (
                    purchases.list_recent_purchase_orders_by_vendor(
                        vendor.id, RECENT_PO_LIMIT
                    )
                    if purchases
                    else []
                )
            except Exception:
                recent = []

            if not recent:
                st.markdown(
                    "<div style='text-align:center;padding:1.25rem 0.5rem;"
                    "color:#5B5560;'>No purchase orders yet.</div>",
                    unsafe_allow_html=True,
                )
            else:
                purchase_order_cards(
                    [_po_row(po) for po in recent],
                    suffix=f"vd_po_{vendor.id}",
                    view_label="View Details",
                    view_full_width=False,
                    show_expected_date=True,
                )
                if total_pos > RECENT_PO_LIMIT:
                    st.caption(
                        f"Showing latest {RECENT_PO_LIMIT} of "
                        f"{total_pos} purchase orders."
                    )

        if accounting is not None:
            _render_recent_payments(services, vendor, vendor_account)

        if st.session_state.get(V_EDIT):
            get_submit_map().setdefault(V_EDIT, SUBMIT_EDIT)
            register_armed_dialog(V_EDIT)
            _edit_vendor_dialog(vendor_service)

        if st.session_state.get(V_PAY) and accounting is not None:
            _pay_vendor_dialog(services, vendor.id)

        open_po_dialog_if_armed(services)
        open_purchase_bill_dialog_if_armed(services)


def render_vendor_detail(services: dict):
    """Backward-compatible entry used by older imports."""
    render(services)
