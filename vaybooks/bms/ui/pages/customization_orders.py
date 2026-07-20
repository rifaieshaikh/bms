from datetime import date, timedelta

import streamlit as st

from vaybooks.bms.application.dtos import CreateOrderRequest
from vaybooks.bms.domain.invoices.entities import (
    DEFAULT_CUSTOMIZATION_GST_RATE,
    DEFAULT_CUSTOMIZATION_SAC,
)
from vaybooks.bms.domain.invoices.services import InvoiceDomainService
from vaybooks.bms.domain.orders.order_refs import compact_order_ref
from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import OrderStatus, VoucherType
from vaybooks.bms.domain.shared.india import state_name_for_code
from vaybooks.bms.ui.components.delivery_card import DeliveryEditAction, delivery_cards
from vaybooks.bms.ui.components.invoice_card import InvoiceEditAction, invoice_cards
from vaybooks.bms.ui.components.item_detail_panel import customization_item_detail_panel
from vaybooks.bms.ui.components.voucher_card import VoucherEditAction, voucher_cards
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    dismiss_armed_dialogs,
    register_armed_dialog,
)
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.session_keys import ACTIVITY_SKIP_NOTICE
from vaybooks.bms.ui.styles import metric_grid, panel, status_badge


def _inv_flag(order_id: str) -> str:
    return f"inv_dialog_{order_id}"


def _del_flag(order_id: str) -> str:
    return f"del_dialog_{order_id}"


def _rcpt_flag(order_id: str) -> str:
    return f"rcpt_dialog_{order_id}"


def _pay_flag(order_id: str) -> str:
    return f"pay_dialog_{order_id}"


def _refund_flag(order_id: str) -> str:
    return f"refund_dialog_{order_id}"


def _cancel_flag(order_id: str) -> str:
    return f"cancel_dialog_{order_id}"


def _index_of(options: dict, target_id, default: int = 0) -> int:
    ids = list(options.values())
    return ids.index(target_id) if target_id in ids else default


def _completed_item_options(order, extra_ids=None) -> dict:
    extra = set(extra_ids or [])
    labels: dict[str, str] = {}
    for idx, item in enumerate(order.customization_items):
        if item.is_cancellation_charge:
            continue
        if not (order.item_activities_complete(item.item_id) or item.item_id in extra):
            continue
        label = f"{item.bill_number} — {item.description or 'No description'}"
        if label in labels:
            label = f"{label} (#{idx + 1})"
        labels[label] = item.item_id
    return labels


def _invoice_item_options(order, extra_ids=None) -> dict:
    """Items available to invoice."""
    if order.order_status == OrderStatus.CANCELLED:
        item = order.get_cancellation_charge_item()
        if not item:
            return {}
        label = f"{item.bill_number} — {item.description or 'Cancellation charge'}"
        return {label: item.item_id}
    return _completed_item_options(order, extra_ids)


def _default_item_rows():
    return [
        {
            "bill_number": "",
            "item_description": "",
            "required_activities": {},
        }
    ]


@st.dialog("New Customization Order", width="large")
def _new_order_dialog(services: dict):
    order_service = services["orders"]
    activity_service = services["activities"]
    accounting_service = services["accounting"]
    activities = activity_service.list_activities()

    if "new_order_item_rows" not in st.session_state:
        st.session_state.new_order_item_rows = _default_item_rows()

    name = st.text_input("Customer Name", key="new_ord_name")
    mobile = st.text_input("Mobile", key="new_ord_mobile")
    advance = st.number_input("Advance Amount", min_value=0.0, value=0.0, key="new_ord_adv")

    receiving_account_id = None
    if advance > 0:
        store_accounts = accounting_service.get_store_accounts()
        if store_accounts:
            account_options = {account.account_name: account.id for account in store_accounts}
            account_name = st.selectbox(
                "Receiving Account (Store)",
                list(account_options.keys()),
                key="new_ord_recv",
            )
            receiving_account_id = account_options[account_name]
        else:
            st.warning(
                "No store accounts found. Create one from the Accounts tab to record the advance."
            )

    notes = st.text_area("Notes", key="new_ord_notes")

    order_etd = st.date_input(
        "Expected Delivery Date (ETD)",
        value=date.today() + timedelta(days=7),
        key="new_ord_etd",
    )

    def _mark_item_etd_override(idx: int):
        rows = st.session_state.new_order_item_rows
        if idx < len(rows):
            rows[idx]["etd_overridden"] = True

    st.markdown("### Customization Items")
    st.caption("Each item defaults to the order ETD; change it per item as needed.")
    item_rows = []
    for index, row in enumerate(st.session_state.new_order_item_rows):
        st.markdown(f"**Item {index + 1}**")
        cols = st.columns(2)
        row["bill_number"] = cols[0].text_input(
            "Measurement Bill Number",
            value=row["bill_number"],
            key=f"new_item_bill_{index}",
        )
        row["item_description"] = cols[1].text_input(
            "Item Description",
            value=row["item_description"],
            key=f"new_item_desc_{index}",
        )

        # Items that the user hasn't manually changed track the order ETD.
        etd_key = f"new_item_etd_{index}"
        if not row.get("etd_overridden"):
            st.session_state[etd_key] = order_etd
        row["expected_delivery_date"] = st.date_input(
            "Item ETD",
            key=etd_key,
            on_change=_mark_item_etd_override,
            args=(index,),
        )

        required_map = {}
        for activity in activities:
            default_checked = row.get("required_activities", {}).get(
                activity.activity_name,
                activity.activity_name
                in ("Stitching", "Handwork", "Material Purchase"),
            )
            required_map[activity.activity_name] = st.checkbox(
                f"{activity.activity_name} (Required)",
                value=default_checked,
                key=f"new_item_act_{index}_{activity.id}",
            )
        row["required_activities"] = required_map

        if row["bill_number"] and row["item_description"]:
            item_rows.append(row)

    def _add_item_row():
        st.session_state.new_order_item_rows.append(
            {
                "bill_number": "",
                "item_description": "",
                "required_activities": {},
            }
        )

    def _remove_item_row():
        if len(st.session_state.new_order_item_rows) > 1:
            st.session_state.new_order_item_rows.pop()

    action_cols = st.columns(2)
    with action_cols[0]:
        st.button("Add Another Item", on_click=_add_item_row, use_container_width=True)
    with action_cols[1]:
        st.button(
            "Remove Last Item",
            on_click=_remove_item_row,
            disabled=len(st.session_state.new_order_item_rows) <= 1,
            use_container_width=True,
        )

    if st.button("Create Order", type="primary"):
        if not name or not mobile:
            st.error("Customer name and mobile are required")
            return
        if not item_rows:
            st.error(
                "Add at least one measurement bill number with item description"
            )
            return
        try:
            request = CreateOrderRequest(
                customer_name=name,
                phone_number=mobile,
                customization_items=item_rows,
                expected_delivery_date=order_etd,
                advance_amount=advance,
                receiving_account_id=receiving_account_id,
                notes=notes,
            )
            order = order_service.create_customization_order(request)
            st.session_state.new_order_item_rows = _default_item_rows()
            st.success(f"Created order {order.order_number}")
            navigation.go_to_detail("order_detail", order.id)
        except Exception as exc:
            st.error(str(exc))


def _render_items_tab(services: dict, order, invoices: list, deliveries: list):
    items = order.customization_items
    if not items:
        st.info("No items in this order.")
        return

    labels: dict[str, str] = {}
    for idx, item in enumerate(items):
        label = f"{item.bill_number} — {item.description or 'No description'}"
        if label in labels:
            label = f"{label} (#{idx + 1})"
        labels[label] = item.item_id

    selected_label = st.selectbox(
        "Select item", list(labels.keys()), key=f"orderview_item_sel_{order.id}"
    )
    item = order.get_item_by_id(labels[selected_label])
    if not item:
        return

    customization_item_detail_panel(
        services,
        order,
        item,
        invoices,
        deliveries,
        key_prefix=f"orderview_{order.id}_{item.item_id}",
        show_header=True,
        show_item_edit=True,
        allow_activity_dialogs=True,
    )


def _render_order_measurements_tab(services: dict, order) -> None:
    from vaybooks.bms.ui.components.measurement_form import measurement_form

    measurement_service = services["measurements"]
    records = measurement_service.list_by_customer(order.customer_id)
    if st.button("Add measurement", key=f"detail_add_ms_{order.id}"):
        st.session_state[f"detail_show_ms_form_{order.id}"] = True
    for rec in records:
        with st.expander(
            f"{rec.measurement_number} · {rec.person_type.value}"
            + (f" · {rec.wearer_name}" if rec.wearer_name else ""),
        ):
            for value in rec.values:
                st.write(
                    f"{value.field_key.replace('_', ' ').title()}: "
                    f"{value.value} {value.unit}"
                )
            try:
                from vaybooks.bms.infrastructure.pdf.measurement_pdf import (
                    generate_measurement_sheet_pdf,
                )

                business = services["business"].get_profile()
                customer = services["customers"].get_customer_detail(order.customer_id)
                pdf_bytes = generate_measurement_sheet_pdf(rec, customer, business)
                st.download_button(
                    "Download PDF",
                    data=pdf_bytes,
                    file_name=f"{rec.measurement_number}.pdf",
                    mime="application/pdf",
                    key=f"detail_ms_pdf_{rec.id}",
                )
            except Exception as exc:
                st.caption(str(exc))
    if st.session_state.get(f"detail_show_ms_form_{order.id}"):
        saved = measurement_form(
            services,
            customer_id=order.customer_id,
            order_id=order.id,
            key_prefix=f"detail_ms_{order.id}",
        )
        if saved:
            st.session_state.pop(f"detail_show_ms_form_{order.id}", None)
            st.success(f"Saved {saved.measurement_number}")
            st.rerun()


def _render_order_advance_tab(services: dict, order) -> None:
    from datetime import date, timedelta

    order_service = services["orders"]
    accounting = services["accounting"]
    etd = st.date_input(
        "Order ETD",
        value=order.expected_delivery_date or date.today() + timedelta(days=7),
        key=f"detail_adv_etd_{order.id}",
    )
    advance = st.number_input(
        "Advance amount",
        min_value=0.0,
        value=float(order.advance_amount or 0),
        step=100.0,
        key=f"detail_adv_amt_{order.id}",
    )
    cash_accounts = accounting.get_store_accounts()
    account_labels = {a.id: a.account_name for a in cash_accounts}
    receiving_id = None
    if account_labels:
        choice = st.selectbox(
            "Receiving account",
            options=list(account_labels.values()),
            key=f"detail_adv_recv_{order.id}",
        )
        receiving_id = next(
            aid for aid, name in account_labels.items() if name == choice
        )
    if st.button("Save advance", key=f"detail_adv_save_{order.id}"):
        try:
            order_service.update_order_etd(order.id, etd)
            _, voucher = order_service.save_order_advance(
                order.id, advance, receiving_id
            )
            if voucher:
                st.success(f"Advance saved · {voucher.voucher_number}")
            else:
                st.success("Advance cleared")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    voucher = order_service.find_advance_voucher(order.id)
    if voucher:
        try:
            from vaybooks.bms.infrastructure.pdf.advance_receipt_pdf import (
                generate_advance_receipt_pdf,
            )

            business = services["business"].get_profile()
            customer = services["customers"].get_customer_detail(order.customer_id)
            pdf_bytes = generate_advance_receipt_pdf(
                voucher, order, customer, business
            )
            st.download_button(
                "Download advance receipt",
                data=pdf_bytes,
                file_name=f"{voucher.voucher_number}_advance.pdf",
                mime="application/pdf",
                key=f"detail_adv_pdf_{order.id}",
            )
        except Exception as exc:
            st.caption(str(exc))


# --- invoice dialog ----------------------------------------------------------
def _inv_amt_key(order_id: str, bill_id: str) -> str:
    return f"inv_amt_{order_id}_{bill_id}"


def _inv_idisc_key(order_id: str, bill_id: str) -> str:
    return f"inv_idisc_{order_id}_{bill_id}"


def _inv_odisc_key(order_id: str) -> str:
    return f"inv_odisc_{order_id}"


def _on_inv_order_discount_change(order_id: str, bill_ids: list) -> None:
    """Order-level discount changed: distribute the difference across items."""
    new_od = float(st.session_state.get(_inv_odisc_key(order_id), 0.0) or 0.0)
    amounts = {
        b: float(st.session_state.get(_inv_amt_key(order_id, b), 0.0) or 0.0)
        for b in bill_ids
    }
    current = {
        b: float(st.session_state.get(_inv_idisc_key(order_id, b), 0.0) or 0.0)
        for b in bill_ids
    }
    new_disc = InvoiceDomainService.redistribute_discount_delta(
        amounts, current, new_od
    )
    for bill_id, value in new_disc.items():
        st.session_state[_inv_idisc_key(order_id, bill_id)] = value


def _on_inv_item_discount_change(order_id: str, bill_ids: list) -> None:
    """An item discount changed: the order discount is the sum of item ones."""
    total = sum(
        float(st.session_state.get(_inv_idisc_key(order_id, b), 0.0) or 0.0)
        for b in bill_ids
    )
    st.session_state[_inv_odisc_key(order_id)] = round(total, 2)


def _clear_invoice_widget_state(order_id: str) -> None:
    """Drop the per-invoice amount/discount widget state so a later invoice for
    the same order starts clean instead of inheriting stale values."""
    prefixes = (
        f"inv_amt_{order_id}_",
        f"inv_idisc_{order_id}_",
        f"inv_items_{order_id}",
    )
    stale = [
        key
        for key in list(st.session_state.keys())
        if key == _inv_odisc_key(order_id) or key.startswith(prefixes)
    ]
    for key in stale:
        st.session_state.pop(key, None)


def _invoice_dialog_content(services: dict, order_id: str, *, generate: bool):
    invoice_service = services["invoices"]
    order_service = services["orders"]
    order = order_service.get_order_detail(order_id)
    is_cancellation = order.order_status == OrderStatus.CANCELLED
    if is_cancellation:
        order = order_service.ensure_cancellation_charge_item(order_id)
    flag_key = _inv_flag(order_id)
    target = st.session_state.get(flag_key)
    invoice = None
    if target not in (None, "new", "generate"):
        invoice = invoice_service.get_invoice(target)
        if invoice:
            generate = invoice.is_generated

    business = services["business"].get_profile() if services.get("business") else None
    customer = services["customers"].get_customer_detail(order.customer_id)
    pos_state, supply_type = invoice_service.resolve_place_of_supply(customer, business)
    business_registered = business_is_registered(business)

    if generate:
        st.caption(
            "System tax invoice — auto-numbered, GST-aware, and printable for the customer."
            if not is_cancellation
            else "Tax invoice for the cancellation charge — to set off remaining advance."
        )
        next_number = (
            invoice.invoice_number
            if invoice
            else invoice_service.peek_next_invoice_number()
        )
        st.text_input("Invoice Number", value=next_number, disabled=True)
        with st.container(border=True):
            st.markdown("**Bill to**")
            st.write(getattr(customer, "customer_name", order.customer_name))
            if customer and customer.formatted_address:
                st.caption(customer.formatted_address)
            st.caption(f"Place of supply: **{state_name_for_code(pos_state) or '—'}**")
            st.caption(f"Supply type: **{supply_type}**")
    else:
        st.caption(
            "Log a paper cancellation charge for internal tracking and margin."
            if is_cancellation
            else "Log a paper bill number for internal tracking and margin."
        )
        invoice_number = st.text_input(
            "Invoice Number", value=invoice.invoice_number if invoice else ""
        )

    override = st.checkbox("Allow already-invoiced items", value=bool(invoice))
    options = _invoice_item_options(order, invoice.bill_ids if invoice else None)
    if is_cancellation:
        st.caption(
            "Invoice the cancellation charge to set off remaining advance on this order."
        )
    if not options:
        st.info(
            "No cancellation charge available."
            if is_cancellation
            else "No completed items available to invoice."
        )
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return
    default_labels = list(options.keys()) if is_cancellation else (
        [lbl for lbl, iid in options.items() if iid in set(invoice.bill_ids)]
        if invoice
        else []
    )
    if is_cancellation:
        cancel_label = default_labels[0] if default_labels else "Cancellation charge"
        st.markdown(f"**Item:** {cancel_label}")
        bill_ids = list(options.values())
    else:
        selected = st.multiselect(
            "Items", list(options.keys()), default=default_labels,
            key=f"inv_items_{order.id}",
        )
        bill_ids = [options[lbl] for lbl in selected]

    inv_date = st.date_input(
        "Invoice Date", value=invoice.invoice_date if invoice else date.today()
    )

    existing_prices = dict(invoice.item_amounts) if invoice and invoice.item_amounts else {}
    if invoice and not existing_prices and invoice.bill_ids:
        each = round(float(invoice.invoice_amount) / len(invoice.bill_ids), 2)
        existing_prices = {b: each for b in invoice.bill_ids}
    existing_discounts = (
        dict(invoice.item_discounts) if invoice and invoice.item_discounts else {}
    )
    if invoice and not existing_discounts and invoice.discount_amount:
        existing_discounts = InvoiceDomainService.allocate_discount_proportionally(
            existing_prices, float(invoice.discount_amount)
        )
    label_by_bill = {iid: lbl for lbl, iid in options.items()}

    odisc_key = _inv_odisc_key(order.id)
    if odisc_key not in st.session_state:
        st.session_state[odisc_key] = (
            round(float(invoice.discount_amount), 2) if invoice else 0.0
        )

    item_amounts: dict = {}
    item_discounts: dict = {}
    for bill_id in bill_ids:
        order_item = order.get_item_by_id(bill_id)
        amt_key = _inv_amt_key(order.id, bill_id)
        idisc_key = _inv_idisc_key(order.id, bill_id)
        if amt_key not in st.session_state:
            st.session_state[amt_key] = float(
                existing_prices.get(
                    bill_id,
                    order_item.sale_price if order_item and order_item.sale_price else 0.0,
                )
            )
        if idisc_key not in st.session_state:
            st.session_state[idisc_key] = round(
                float(existing_discounts.get(bill_id, 0.0)), 2
            )
        item_amounts[bill_id] = float(st.session_state.get(amt_key, 0.0) or 0.0)
        item_discounts[bill_id] = float(st.session_state.get(idisc_key, 0.0) or 0.0)

    previews = (
        invoice_service.preview_item_mph(
            order.id,
            item_amounts,
            item_discounts=item_discounts,
            exclude_invoice_id=invoice.id if invoice else None,
        )
        if bill_ids
        else []
    )
    preview_by_bill = {row["bill_id"]: row for row in previews}

    if not bill_ids:
        st.info("Select one or more items to invoice.")

    if bill_ids:
        st.markdown("**Invoiced items**")
    for bill_id in bill_ids:
        row = preview_by_bill.get(bill_id, {})
        with st.container(border=True):
            st.markdown(f"**{label_by_bill.get(bill_id, bill_id)}**")
            ro = st.columns(4)
            ro[0].caption("Previously invoiced")
            ro[0].write(f"\u20b9{row.get('previously_invoiced', 0.0):,.0f}")
            ro[1].caption("Expense total")
            ro[1].write(f"\u20b9{row.get('expense_selling_total', 0.0):,.0f}")
            ro[2].caption("Hours")
            ro[2].write(f"{row.get('in_house_hours', 0.0):.2f}")
            ro[3].caption("MPH")
            mph = row.get("margin_per_hour")
            ro[3].write(f"\u20b9{mph:,.0f}/h" if mph is not None else "\u2014")
            ed = st.columns(2)
            ed[0].number_input(
                "Amount", min_value=0.0, step=100.0,
                key=_inv_amt_key(order.id, bill_id),
            )
            ed[1].number_input(
                "Discount", min_value=0.0, step=100.0,
                key=_inv_idisc_key(order.id, bill_id),
                on_change=_on_inv_item_discount_change,
                args=(order.id, bill_ids),
            )

    amount = round(sum(item_amounts.values()), 2)
    item_discounts = {
        b: round(min(item_discounts.get(b, 0.0), item_amounts.get(b, 0.0)), 2)
        for b in bill_ids
    }
    discount_amount = round(sum(item_discounts.values()), 2)
    net_amount = round(amount - discount_amount, 2)

    gst_rate = DEFAULT_CUSTOMIZATION_GST_RATE
    hsn_sac = DEFAULT_CUSTOMIZATION_SAC
    tax_summary = None
    if generate and bill_ids:
        gst_cols = st.columns(2)
        gst_rate = gst_cols[0].number_input(
            "GST rate (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(invoice.gst_rate if invoice and invoice.gst_rate else DEFAULT_CUSTOMIZATION_GST_RATE),
            step=0.1,
            disabled=not business_registered,
        )
        hsn_sac = gst_cols[1].text_input(
            "SAC",
            value=invoice.hsn_sac if invoice and invoice.hsn_sac else DEFAULT_CUSTOMIZATION_SAC,
        )
        if business_registered:
            tax_summary = invoice_service.preview_invoice_gst(
                net_amount,
                gst_rate,
                business=business,
                place_of_supply_state=pos_state,
            )
        else:
            st.info("Business is not GST registered — tax will not be charged.")

    if bill_ids:
        st.number_input(
            "Order discount",
            min_value=0.0, max_value=amount, step=100.0, key=odisc_key,
            on_change=_on_inv_order_discount_change, args=(order.id, bill_ids),
            help="Distributed across items in proportion to their amount.",
        )

        total_expense = round(
            sum(r.get("expense_selling_total", 0.0) for r in previews), 2
        )
        total_hours = round(sum(r.get("in_house_hours", 0.0) for r in previews), 2)
        total_cum_net = round(
            sum(r.get("cumulative_net", 0.0) for r in previews), 2
        )
        total_margin = round(total_cum_net - total_expense, 2)
        total_mph = round(total_margin / total_hours, 2) if total_hours > 0 else None

        st.markdown("**Totals**")
        t1 = st.columns(4)
        t1[0].metric("Total amount", f"\u20b9{amount:,.0f}")
        t1[1].metric("Total discount", f"\u20b9{discount_amount:,.0f}")
        t1[2].metric("Net (taxable)", f"\u20b9{net_amount:,.0f}")
        t1[3].metric("Total expense", f"\u20b9{total_expense:,.0f}")
        t2 = st.columns(2)
        t2[0].metric("Total hours", f"{total_hours:.2f}")
        t2[1].metric(
            "Total MPH",
            f"\u20b9{total_mph:,.0f}/h" if total_mph is not None else "\u2014",
        )

        if generate and tax_summary and business_registered:
            st.markdown("**GST**")
            g = st.columns(5)
            g[0].metric("CGST", f"\u20b9{tax_summary['cgst_amount']:,.0f}")
            g[1].metric("SGST", f"\u20b9{tax_summary['sgst_amount']:,.0f}")
            g[2].metric("UTGST", f"\u20b9{tax_summary['utgst_amount']:,.0f}")
            g[3].metric("IGST", f"\u20b9{tax_summary['igst_amount']:,.0f}")
            g[4].metric("Grand total", f"\u20b9{tax_summary['grand_total']:,.0f}")

    accounting = services["accounting"]
    existing_voucher = (
        accounting.find_sales_voucher_by_invoice(invoice.id) if invoice else None
    )
    unapplied_advance = accounting.get_order_unapplied_advance(
        order.id,
        exclude_invoice_id=invoice.id if invoice else None,
    )
    st.divider()
    due_preview = (
        tax_summary["grand_total"]
        if generate and tax_summary
        else net_amount
    )
    post_entry = st.checkbox(
        "Post accounting entry (Dr Customer, Cr revenue; apply advance on customer)",
        value=bool(existing_voucher) if invoice else True,
    )
    if post_entry:
        advance_preview = round(min(unapplied_advance, due_preview), 2)
        balance_preview = round(due_preview - advance_preview, 2)
        if advance_preview > 0:
            st.caption(
                f"Advance applied: **₹{advance_preview:,.0f}** · "
                f"Customer balance due: **₹{balance_preview:,.0f}**"
            )
        if is_cancellation:
            revenue = accounting.get_cancellation_charges_account()
            if revenue:
                st.caption(f"Revenue credited to: **{revenue.account_name}**")
            else:
                st.warning(
                    'No "Cancellation Charges" revenue account found. Restart the app '
                    "to seed defaults or create one in Accounts."
                )
        else:
            customization = accounting.get_customization_account()
            if customization:
                st.caption(f"Revenue credited to: **{customization.account_name}**")
            else:
                st.warning(
                    'No "Customization" revenue account found. Restart the app to seed '
                    "defaults or create one in Accounts."
                )
        if discount_amount > 0 and not generate:
            discount_account = accounting.get_discount_account()
            if discount_account:
                st.caption(f"Discount debited to: **{discount_account.account_name}**")
            else:
                st.warning(
                    'No "Discount Allowed" account found. Create one in the '
                    "Accounts page to post the discount."
                )

    cols = st.columns(2)
    save_label = (
        "Generate cancellation charge"
        if generate and is_cancellation and not invoice
        else ("Record cancellation charge" if is_cancellation and not invoice else ("Generate & Save" if generate and not invoice else "Save"))
    )
    if cols[0].button(save_label, type="primary", use_container_width=True):
        try:
            with st.spinner("Please wait while saving invoice..."):
                if invoice:
                    invoice_service.update_invoice(
                        invoice.id,
                        invoice.invoice_number if generate else invoice_number,
                        bill_ids,
                        amount,
                        inv_date,
                        allow_already_invoiced=override,
                        post_entry=post_entry,
                        discount_amount=discount_amount,
                        item_amounts=item_amounts,
                        item_discounts=item_discounts,
                        gst_rate=gst_rate if generate else None,
                        hsn_sac=hsn_sac if generate else None,
                        business=business if generate else None,
                        customer=customer if generate else None,
                    )
                elif generate:
                    invoice_service.generate_invoice(
                        order.id,
                        bill_ids,
                        amount,
                        inv_date,
                        allow_already_invoiced=override,
                        post_entry=post_entry,
                        discount_amount=discount_amount,
                        item_amounts=item_amounts,
                        item_discounts=item_discounts,
                        gst_rate=gst_rate,
                        hsn_sac=hsn_sac,
                        business=business,
                        customer=customer,
                    )
                else:
                    invoice_service.record_invoice(
                        order.id,
                        invoice_number,
                        bill_ids,
                        amount,
                        inv_date,
                        allow_already_invoiced=override,
                        post_entry=post_entry,
                        discount_amount=discount_amount,
                        item_amounts=item_amounts,
                        item_discounts=item_discounts,
                    )
            _clear_invoice_widget_state(order.id)
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        _clear_invoice_widget_state(order.id)
        st.session_state.pop(flag_key, None)
        st.rerun()


@st.dialog("Record Invoice", width="large", on_dismiss=dismiss_armed_dialogs)
def _record_invoice_dialog(services: dict, order_id: str):
    _invoice_dialog_content(services, order_id, generate=False)


@st.dialog("Generate Invoice", width="large", on_dismiss=dismiss_armed_dialogs)
def _generate_invoice_dialog(services: dict, order_id: str):
    _invoice_dialog_content(services, order_id, generate=True)


def _open_invoice_dialog(services: dict, order_id: str) -> None:
    """Reopen an invoice for edit (armed via session flag at page bottom)."""
    target = st.session_state.get(_inv_flag(order_id))
    if not target or target in ("new", "generate"):
        return
    invoice = services["invoices"].get_invoice(target)
    if invoice and invoice.is_generated:
        _generate_invoice_dialog(services, order_id)
    else:
        _record_invoice_dialog(services, order_id)


def _render_invoices_tab(services: dict, order, invoices: list):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    mark_wired("orders.record_invoice")
    is_cancelled = order.order_status == OrderStatus.CANCELLED
    can_invoice = is_cancelled or order.has_completed_items()

    if can_invoice:
        btn_cols = st.columns(2)
        if is_cancelled:
            if btn_cols[0].button(
                "+ Record Cancellation Charge",
                key=f"rec_canc_{order.id}",
                type="primary",
            ):
                clear_all_dialog_flags()
                _record_invoice_dialog(services, order.id)
            if btn_cols[1].button(
                "+ Generate Cancellation Charge",
                key=f"gen_canc_{order.id}",
            ):
                clear_all_dialog_flags()
                _generate_invoice_dialog(services, order.id)
        else:
            if btn_cols[0].button(
                "+ Record Invoice", key=f"rec_inv_{order.id}", type="primary"
            ) or consume_action("orders.record_invoice"):
                clear_all_dialog_flags()
                _record_invoice_dialog(services, order.id)
            if btn_cols[1].button("+ Generate Invoice", key=f"gen_inv_{order.id}"):
                clear_all_dialog_flags()
                _generate_invoice_dialog(services, order.id)
    elif not is_cancelled:
        st.caption("Complete at least one item before invoicing.")
    if not invoices:
        st.caption("No invoices yet.")
        return
    accounting = services["accounting"]
    inv_flag = _inv_flag(order.id)
    business = services["business"].get_profile()
    customer = services["customers"].get_customer_detail(order.customer_id)

    def _invoice_builder(invoice):
        pdf_bytes = None
        if invoice.is_generated:
            try:
                from vaybooks.bms.infrastructure.pdf.customization_invoice_pdf import (
                    generate_customization_invoice_pdf,
                )

                pdf_bytes = generate_customization_invoice_pdf(
                    invoice, order, customer, business
                )
            except Exception:
                pdf_bytes = None
        return {
            "edit": InvoiceEditAction(
                flag_key=inv_flag,
                button_key=f"edit_inv_{invoice.id}",
                clear_dialogs=True,
                register_dialog=True,
            ),
            "pdf_bytes": pdf_bytes,
        }

    invoice_cards(
        invoices,
        order,
        suffix=f"inv_{order.id}",
        posted_lookup=lambda inv_id: bool(
            accounting.find_sales_voucher_by_invoice(inv_id)
        ),
        card_builder=_invoice_builder,
    )


# --- delivery dialog ---------------------------------------------------------
@st.dialog("Record Delivery", width="large", on_dismiss=dismiss_armed_dialogs)
def _delivery_dialog(services: dict, order_id: str):
    delivery_service = services["deliveries"]
    order = services["orders"].get_order_detail(order_id)
    flag_key = _del_flag(order_id)
    target = st.session_state.get(flag_key)
    delivery = None if target in (None, "new") else delivery_service.get_delivery(target)

    options = _completed_item_options(order, delivery.bill_ids if delivery else None)
    if not options:
        st.info("No completed items available to deliver.")
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return
    default_labels = (
        [lbl for lbl, iid in options.items() if iid in set(delivery.bill_ids)]
        if delivery
        else []
    )
    selected = st.multiselect(
        "Items", list(options.keys()), default=default_labels,
        key=f"del_items_{order.id}",
    )
    bill_ids = [options[lbl] for lbl in selected]
    del_date = st.date_input(
        "Delivery Date", value=delivery.delivery_date if delivery else date.today()
    )
    notes = st.text_area(
        "Delivery Notes", value=delivery.delivery_notes if delivery else ""
    )

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if delivery:
                delivery_service.update_delivery(delivery.id, bill_ids, del_date, notes)
            else:
                delivery_service.record_delivery(
                    order.id, bill_ids, del_date, notes, allow_already_delivered=True
                )
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


def _render_deliveries_tab(services: dict, order, deliveries: list):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    mark_wired("orders.record_delivery")
    if st.button("+ Record Delivery", key=f"rec_del_{order.id}", type="primary") or consume_action(
        "orders.record_delivery"
    ):
        clear_all_dialog_flags()
        _delivery_dialog(services, order.id)
    if not deliveries:
        st.caption("No deliveries yet.")
        return
    del_flag = _del_flag(order.id)

    def _delivery_builder(delivery):
        return {
            "edit": DeliveryEditAction(
                flag_key=del_flag,
                button_key=f"edit_del_{delivery.id}",
                clear_dialogs=True,
                register_dialog=True,
            )
        }

    delivery_cards(
        deliveries,
        order,
        suffix=f"del_{order.id}",
        card_builder=_delivery_builder,
    )


# --- receipt dialog ----------------------------------------------------------
@st.dialog("Record Receipt", width="large", on_dismiss=dismiss_armed_dialogs)
def _receipt_dialog(services: dict, order_id: str):
    accounting = services["accounting"]
    order = services["orders"].get_order_detail(order_id)
    flag_key = _rcpt_flag(order_id)
    target = st.session_state.get(flag_key)
    voucher = None if target in (None, "new") else accounting.get_voucher(target)

    customer_account = accounting.get_customer_account(order.customer_id)
    if not customer_account:
        st.error("No customer account found for this order.")
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return

    store_accounts = accounting.get_store_accounts()
    if not store_accounts:
        st.error("No store accounts. Create one in the Accounts page.")
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return
    account_options = {a.account_name: a.id for a in store_accounts}

    # For a receipt, the receiving account is the debit line.
    existing_recv_id = voucher.lines[0].account_id if voucher else None
    existing_amount = voucher.lines[0].debit_amount if voucher else 0.0

    recv_name = st.selectbox(
        "Receiving Account (Store)", list(account_options.keys()),
        index=_index_of(account_options, existing_recv_id),
    )
    amount = st.number_input("Amount", min_value=0.0, value=float(existing_amount))
    rcpt_date = st.date_input("Date", value=date.today())
    description = st.text_input(
        "Description", value=voucher.description if voucher else f"Receipt for {order.order_number}"
    )

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if voucher:
                accounting.update_customer_payment(
                    voucher.id, account_options[recv_name], customer_account.id,
                    amount, description, rcpt_date,
                )
            else:
                accounting.create_customer_payment(
                    account_options[recv_name], customer_account.id, amount,
                    description, rcpt_date, reference_order_id=order.id,
                )
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


def _render_receipts_tab(services: dict, order):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    accounting = services["accounting"]
    mark_wired("orders.record_receipt")
    if st.button("+ Record Receipt", key=f"rec_rcpt_{order.id}", type="primary") or consume_action(
        "orders.record_receipt"
    ):
        clear_all_dialog_flags()
        _receipt_dialog(services, order.id)
    receipts = [
        v
        for v in accounting.list_vouchers_by_order(order.id)
        if v.voucher_type == VoucherType.RECEIPT
    ]
    if not receipts:
        st.caption("No receipts recorded yet.")
        return

    rcpt_flag = _rcpt_flag(order.id)

    def _receipt_builder(voucher):
        return {
            "show_order_linked": False,
            "show_type_badge": False,
            "edit": VoucherEditAction(
                flag_key=rcpt_flag,
                button_key=f"edit_rcpt_{voucher.id}",
                clear_dialogs=True,
                register_dialog=True,
            ),
        }

    voucher_cards(
        receipts,
        suffix=f"rcpt_{order.id}",
        card_builder=_receipt_builder,
    )


# --- payment dialog ----------------------------------------------------------
@st.dialog("Record Vendor Payment", width="large", on_dismiss=dismiss_armed_dialogs)
def _payment_dialog(services: dict, order_id: str):
    accounting = services["accounting"]
    vendor_service = services["vendors"]
    service_config = services["vendor_services"]
    order = services["orders"].get_order_detail(order_id)
    flag_key = _pay_flag(order_id)
    target = st.session_state.get(flag_key)
    voucher = None if target in (None, "new") else accounting.get_voucher(target)

    store_accounts = accounting.get_store_accounts()
    service_list = service_config.list_services(active_only=True)
    vendors = vendor_service.list_all_vendors()
    if not store_accounts or not service_list or not vendors:
        st.error(
            "Need at least one vendor, one store account and one configured "
            "service (see Vendors and Service Configuration)."
        )
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return

    vendor_options = {}
    for v in vendors:
        acc = accounting.get_vendor_account(v.id)
        if acc:
            vendor_options[v.vendor_name] = acc.id
    pay_options = {a.account_name: a.id for a in store_accounts}
    svc_options = {s.service_name: s for s in service_list}

    # Vendor payment lines: [expense Dr, vendor Cr, vendor Dr, paying Cr].
    existing_vendor_id = voucher.lines[1].account_id if voucher else None
    existing_pay_id = voucher.lines[3].account_id if voucher else None
    existing_amount = voucher.lines[0].debit_amount if voucher else 0.0
    existing_service = voucher.reference_service_id if voucher else None
    svc_default = 0
    if existing_service and existing_service in {s.id for s in service_list}:
        svc_default = next(
            i for i, s in enumerate(service_list) if s.id == existing_service
        )

    vendor_name = st.selectbox(
        "Vendor", list(vendor_options.keys()),
        index=_index_of(vendor_options, existing_vendor_id),
    )
    service_name = st.selectbox(
        "Service / Material", list(svc_options.keys()), index=svc_default
    )
    pay_name = st.selectbox(
        "Paying Account (Store)", list(pay_options.keys()),
        index=_index_of(pay_options, existing_pay_id),
    )
    amount = st.number_input("Amount", min_value=0.0, value=float(existing_amount))
    pay_date = st.date_input("Date", value=date.today())
    description = st.text_input(
        "Description", value=voucher.description if voucher else f"Payment for {order.order_number}"
    )

    selected_service = svc_options[service_name]

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if voucher:
                accounting.update_vendor_payment(
                    voucher.id, vendor_options[vendor_name],
                    selected_service.expense_account_id, pay_options[pay_name],
                    amount, description, pay_date, service_id=selected_service.id,
                )
            else:
                services["purchases"].merge_vendor_payment_into_purchase(
                    vendor_options[vendor_name], selected_service.expense_account_id,
                    pay_options[pay_name], amount, description, pay_date,
                    service_id=selected_service.id, reference_order_id=order.id,
                )
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


def _render_payments_tab(services: dict, order):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    accounting = services["accounting"]
    service_names = {
        s.id: s.service_name
        for s in services["vendor_services"].list_services(active_only=False)
    }
    mark_wired("orders.record_payment")
    if st.button(
        "+ Record Vendor Payment", key=f"rec_pay_{order.id}", type="primary"
    ) or consume_action("orders.record_payment"):
        clear_all_dialog_flags()
        _payment_dialog(services, order.id)
    payments = accounting.list_order_vendor_payments(order.id)
    if not payments:
        st.caption("No payments recorded yet.")
        return
    ordered = sorted(payments, key=lambda x: x.voucher_date, reverse=True)
    pay_flag = _pay_flag(order.id)

    def _payment_builder(voucher):
        return {
            "service_label": service_names.get(voucher.reference_service_id),
            "show_order_linked": False,
            "show_type_badge": False,
            "edit": VoucherEditAction(
                flag_key=pay_flag,
                button_key=f"edit_pay_{voucher.id}",
                clear_dialogs=True,
                register_dialog=True,
            ),
        }

    voucher_cards(
        ordered,
        suffix=f"pay_{order.id}",
        card_builder=_payment_builder,
    )


# --- refund dialog -----------------------------------------------------------
def _refundable_advance(accounting, order_id: str, exclude_voucher_id=None) -> float:
    available = accounting.get_order_unapplied_advance(order_id)
    if exclude_voucher_id:
        voucher = accounting.get_voucher(exclude_voucher_id)
        if voucher and voucher.is_advance_refund:
            available += voucher.cash_movement_amount
    return round(max(available, 0.0), 2)


def _refundable_payments(accounting, order_id: str, exclude_voucher_id=None) -> float:
    return accounting.get_order_refundable_customer_payments(
        order_id, exclude_voucher_id=exclude_voucher_id
    )


@st.dialog("Record Refund", width="large", on_dismiss=dismiss_armed_dialogs)
def _refund_dialog(services: dict, order_id: str):
    accounting = services["accounting"]
    order = services["orders"].get_order_detail(order_id)
    flag_key = _refund_flag(order_id)
    target = st.session_state.get(flag_key)
    voucher = None if target in (None, "new") else accounting.get_voucher(target)

    customer_account = accounting.get_customer_account(order.customer_id)
    if not customer_account:
        st.error("No customer account found for this order.")
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return
    store_accounts = accounting.get_store_accounts()
    if not store_accounts:
        st.error("No store accounts. Create one in the Accounts page.")
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return
    store_options = {a.account_name: a.id for a in store_accounts}

    exclude_id = voucher.id if voucher else None
    advance_available = _refundable_advance(accounting, order.id, exclude_id)
    payment_available = _refundable_payments(accounting, order.id, exclude_id)

    if voucher:
        refund_type = "advance" if voucher.is_advance_refund else "payment"
    else:
        refund_type = "advance" if advance_available > 0 else "payment"

    st.caption(
        f"Unapplied advance: **₹{advance_available:,.0f}** · "
        f"Customer payments: **₹{payment_available:,.0f}**"
    )

    if not voucher:
        refund_type = st.radio(
            "Refund type",
            options=["advance", "payment"],
            format_func=lambda x: (
                "Advance refund (unused advance)"
                if x == "advance"
                else "Payment refund (receipt on this order)"
            ),
            index=0 if refund_type == "advance" else 1,
            horizontal=True,
        )

    # Refund lines: advance 4-line uses store credit on line 3; payment 2-line on line 1.
    if voucher and voucher.is_advance_refund:
        existing_store_id = voucher.lines[3].account_id if len(voucher.lines) > 3 else None
        default_amount = voucher.cash_movement_amount
    elif voucher:
        existing_store_id = voucher.lines[1].account_id if len(voucher.lines) > 1 else None
        default_amount = voucher.cash_movement_amount
    else:
        existing_store_id = None
        pool = advance_available if refund_type == "advance" else payment_available
        default_amount = max(pool, 0.0)

    store_name = st.selectbox(
        "Refund from (Store account)", list(store_options.keys()),
        index=_index_of(store_options, existing_store_id),
    )
    max_amount = advance_available if refund_type == "advance" else payment_available
    amount = st.number_input(
        "Amount", min_value=0.0, max_value=float(max_amount), value=float(default_amount)
    )
    refund_date = st.date_input("Date", value=date.today())
    default_desc = (
        f"Advance refund - {order.order_number}"
        if refund_type == "advance"
        else f"Payment refund - {order.order_number}"
    )
    description = st.text_input(
        "Description",
        value=voucher.description if voucher else default_desc,
    )

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if voucher:
                if voucher.is_advance_refund:
                    accounting.update_advance_refund(
                        voucher.id, customer_account.id, store_options[store_name],
                        amount, description, refund_date,
                    )
                else:
                    accounting.update_customer_payment_refund(
                        voucher.id, customer_account.id, store_options[store_name],
                        amount, description, refund_date,
                    )
            elif refund_type == "advance":
                accounting.create_advance_refund(
                    customer_account.id, store_options[store_name], amount,
                    description, refund_date, reference_order_id=order.id,
                )
            else:
                accounting.create_customer_payment_refund(
                    customer_account.id, store_options[store_name], amount,
                    description, refund_date, reference_order_id=order.id,
                )
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


@st.dialog("Cancel Order", width="large", on_dismiss=dismiss_armed_dialogs)
def _cancel_order_dialog(services: dict, order_id: str) -> None:
    order_service = services["orders"]
    accounting = services["accounting"]
    order = order_service.get_order_detail(order_id)
    flag_key = _cancel_flag(order_id)

    if not order:
        st.error("Order not found")
        if st.button("Close", key=f"cancel_close_missing_{order_id}"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return

    if order.order_status == OrderStatus.CANCELLED:
        st.info("This order is already cancelled.")
        if st.button("Close", key=f"cancel_close_done_{order_id}"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return

    unapplied = round(accounting.get_order_unapplied_advance(order.id), 2)

    if unapplied > 0:
        st.markdown(f"**Amount with us:** ₹{unapplied:,.0f}")
        st.write("Do you want to initiate a refund now?")
        st.caption(
            "Choose **Yes** to record a cash refund and cancel the order. "
            "Choose **No** to cancel only — advance stays on this order for "
            "service invoices or a later refund from the Refunds tab."
        )
        customer_account = accounting.get_customer_account(order.customer_id)
        store_accounts = accounting.get_store_accounts()
        if not customer_account:
            st.error("No customer account found for this order.")
        elif not store_accounts:
            st.error("No store account found. Create one in Accounts before refunding.")
        else:
            store_options = {a.account_name: a.id for a in store_accounts}
            store_name = st.selectbox(
                "Refund from (store account)",
                list(store_options.keys()),
                key=f"cancel_refund_store_{order_id}",
            )
            refund_amount = st.number_input(
                "Refund amount",
                min_value=0.0,
                max_value=float(unapplied),
                value=float(unapplied),
                step=100.0,
                key=f"cancel_refund_amount_{order_id}",
            )
            refund_date = st.date_input(
                "Refund date",
                value=date.today(),
                key=f"cancel_refund_date_{order_id}",
            )

            cols = st.columns(3)
            if cols[0].button(
                "Yes, refund & cancel",
                type="primary",
                use_container_width=True,
                key=f"cancel_yes_refund_{order_id}",
            ):
                try:
                    order_service.cancel_order(order.id)
                    accounting.create_advance_refund(
                        customer_account.id,
                        store_options[store_name],
                        refund_amount,
                        f"Advance refund - {order.order_number}",
                        refund_date,
                        reference_order_id=order.id,
                    )
                    st.session_state.pop(flag_key, None)
                    st.toast("Order cancelled and refund recorded")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if cols[1].button(
                "No, cancel only",
                use_container_width=True,
                key=f"cancel_no_refund_{order_id}",
            ):
                try:
                    order_service.cancel_order(order.id)
                    st.session_state.pop(flag_key, None)
                    st.toast(
                        "Order cancelled — advance kept for invoices or later refund"
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if cols[2].button(
                "Close",
                use_container_width=True,
                key=f"cancel_close_{order_id}",
            ):
                st.session_state.pop(flag_key, None)
                st.rerun()
            return

        if st.button("Cancel order only", key=f"cancel_fallback_{order_id}"):
            try:
                order_service.cancel_order(order.id)
                st.session_state.pop(flag_key, None)
                st.toast("Order cancelled")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        return

    st.write("Cancel this customization order?")
    cols = st.columns(2)
    if cols[0].button(
        "Yes, cancel order",
        type="primary",
        use_container_width=True,
        key=f"cancel_confirm_{order_id}",
    ):
        try:
            order_service.cancel_order(order.id)
            st.session_state.pop(flag_key, None)
            st.toast("Order cancelled")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button(
        "Close",
        use_container_width=True,
        key=f"cancel_abort_{order_id}",
    ):
        st.session_state.pop(flag_key, None)
        st.rerun()


def _render_refunds_tab(services: dict, order):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    accounting = services["accounting"]
    mark_wired("orders.record_refund")
    if st.button("+ Record Refund", key=f"rec_refund_{order.id}", type="primary") or consume_action(
        "orders.record_refund"
    ):
        clear_all_dialog_flags()
        _refund_dialog(services, order.id)
    refunds = [
        v
        for v in accounting.list_vouchers_by_order(order.id)
        if v.voucher_type == VoucherType.REFUND
    ]
    if not refunds:
        st.caption("No refunds recorded yet.")
        return

    refund_flag = _refund_flag(order.id)

    def _refund_builder(voucher):
        return {
            "show_order_linked": False,
            "show_type_badge": False,
            "edit": VoucherEditAction(
                flag_key=refund_flag,
                button_key=f"edit_refund_{voucher.id}",
                clear_dialogs=True,
                register_dialog=True,
            ),
        }

    voucher_cards(
        refunds,
        suffix=f"refund_{order.id}",
        card_builder=_refund_builder,
    )


def _render_order_financials(services: dict, order, invoices: list):
    """Card view: order MPH, total invoiced, received, and balance."""
    accounting = services["accounting"]

    total_invoiced = round(sum(inv.net_amount for inv in invoices), 2)
    total_margin = round(sum(inv.margin_amount for inv in invoices), 2)
    # In-house hours come from recorded time entries (time is tracked for
    # in-house service activities), not from the expense records.
    time_entries = services["time_tracking"].get_entries_by_order(order.id)
    total_hours = round(sum(e.duration_minutes for e in time_entries) / 60.0, 2)
    order_mph = round(total_margin / total_hours, 2) if total_hours > 0 else None

    vouchers = accounting.list_vouchers_by_order(order.id)
    total_received = accounting.get_order_total_received(order.id)
    total_refunds = round(
        sum(v.cash_movement_amount for v in vouchers if v.voucher_type == VoucherType.REFUND),
        2,
    )
    balance = round(total_invoiced - total_received, 2)

    expense_totals = services["expenses"].get_order_totals(order.id)
    total_expenses = round(expense_totals.get("total_selling", 0), 2)

    metric_grid(
        [
            ("Total Invoiced", f"₹{total_invoiced:,.0f}"),
            ("Received (net)", f"₹{total_received:,.0f}"),
            ("Balance Due", f"₹{balance:,.0f}"),
            ("Total Expenses", f"₹{total_expenses:,.0f}"),
            (
                "Refunded",
                f"₹{total_refunds:,.0f}",
                "Advance/credit paid back to the customer",
            ),
            (
                "Order MPH",
                f"₹{order_mph:,.0f}" if order_mph is not None else "—",
                "Total margin ÷ total in-house hours",
            ),
        ],
        suffix=f"order_fin_{order.id}",
    )
    if total_hours > 0:
        st.caption(
            f"Margin ₹{total_margin:,.0f} over {total_hours:,.2f} in-house hours"
        )


def _render_order_view(services: dict, order_id: str):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("order_detail")
    mark_wired("nav.back")

    order_service = services["orders"]
    invoice_service = services["invoices"]
    delivery_service = services["deliveries"]

    if st.button("← Back to orders", key="order_view_back") or consume_action("nav.back"):
        navigation.go_back_to_list("orders", "orders_list")
        return

    order = order_service.get_order_detail(order_id)
    if not order:
        st.error("Order not found")
        return

    skip_notice = st.session_state.pop(ACTIVITY_SKIP_NOTICE, None)
    if skip_notice:
        st.info(skip_notice)

    invoices = invoice_service.list_invoices_by_order(order.id)
    deliveries = delivery_service.list_by_order(order.id)

    st.title(compact_order_ref(order.order_number))

    with panel(f"order_head_{order.id}"):
        with st.container(border=True):
            head = st.columns([2, 3])
            with head[0]:
                st.caption("Status")
                st.markdown(
                    status_badge(order.order_status.value), unsafe_allow_html=True
                )
            with head[1]:
                st.markdown(
                    f"**{order.customer_name}**  ·  📞 {order.phone_number}"
                )
                st.caption(f"Advance ₹{order.advance_amount:,.0f}")
            if order.notes:
                st.caption(f"Notes: {order.notes}")

            st.divider()
            etd_cols = st.columns([2, 3])
            new_etd = etd_cols[0].date_input(
                "Expected Delivery Date (ETD)",
                value=order.expected_delivery_date,
                key=f"order_etd_{order.id}",
            )
            propagate = etd_cols[1].checkbox(
                "Also update items still using the order date",
                value=True,
                key=f"order_etd_prop_{order.id}",
            )
            if st.button(
                "Update Delivery Date",
                key=f"order_etd_btn_{order.id}",
            ):
                try:
                    order_service.update_order_delivery_date(
                        order.id, new_etd, propagate_to_items=propagate
                    )
                    st.toast("Delivery date updated")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    _render_order_financials(services, order, invoices)

    if order.order_status == OrderStatus.DRAFT:
        draft_cols = st.columns(3)
        if draft_cols[0].button("Continue workspace", type="primary", key=f"resume_ws_{order.id}"):
            st.session_state["order_workspace_order_id"] = order.id
            st.session_state["order_workspace_step"] = "Measurements"
            navigation.go_to_list("order_workspace")
        if draft_cols[1].button("Confirm order", key=f"confirm_ord_{order.id}"):
            try:
                order_service.confirm_order(order.id)
                st.success("Order confirmed")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    (
        tab_overview,
        tab_meas,
        tab_items,
        tab_adv,
        tab_inv,
        tab_del,
        tab_rcpt,
        tab_pay,
        tab_refund,
    ) = st.tabs(
        [
            "Overview",
            "Measurements",
            "Items",
            "Advance & ETD",
            "Invoices",
            "Deliveries",
            "Receipts",
            "Payments",
            "Refunds",
        ]
    )
    with tab_overview:
        st.write(f"Order date: {order.order_date}")
        st.write(f"ETD: {order.expected_delivery_date}")
        st.write(f"Items: {len(order.customization_items)}")
        if order.notes:
            st.write(f"Notes: {order.notes}")
    with tab_meas:
        _render_order_measurements_tab(services, order)
    with tab_items:
        add_cols = st.columns([1, 3])
        if add_cols[0].button("Add item", key=f"detail_add_item_{order.id}"):
            st.session_state["order_workspace_order_id"] = order.id
            st.session_state["order_workspace_step"] = "Items"
            navigation.go_to_list("order_workspace")
        _render_items_tab(services, order, invoices, deliveries)
    with tab_adv:
        _render_order_advance_tab(services, order)
    with tab_inv:
        _render_invoices_tab(services, order, invoices)
    with tab_del:
        _render_deliveries_tab(services, order, deliveries)
    with tab_rcpt:
        _render_receipts_tab(services, order)
    with tab_pay:
        _render_payments_tab(services, order)
    with tab_refund:
        _render_refunds_tab(services, order)

    st.divider()
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    mark_wired("orders.mark_complete", "orders.cancel")
    action_cols = st.columns(2)
    if order.order_status == OrderStatus.DELIVERED:
        if action_cols[0].button(
            "Mark Complete", type="primary", key=f"complete_ord_{order.id}"
        ) or consume_action("orders.mark_complete"):
            try:
                order_service.complete_order(order.id)
                st.success("Order marked complete")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    if order.order_status not in (OrderStatus.CANCELLED, OrderStatus.COMPLETED):
        if action_cols[1].button(
            "Cancel Order", type="secondary", key=f"cancel_ord_{order.id}"
        ) or consume_action("orders.cancel"):
            clear_all_dialog_flags()
            st.session_state[_cancel_flag(order.id)] = True
            register_armed_dialog(_cancel_flag(order.id))
            st.rerun()

    # Popups opened at page top level (order view is a page, not a dialog).
    # Only one dialog may open per run, so this is a strict if/elif chain.
    if st.session_state.get(_cancel_flag(order.id)):
        _cancel_order_dialog(services, order.id)
    elif inv_target := st.session_state.get(_inv_flag(order.id)):
        if inv_target not in ("new", "generate"):
            _open_invoice_dialog(services, order.id)
    elif st.session_state.get(_del_flag(order.id)):
        _delivery_dialog(services, order.id)
    elif st.session_state.get(_rcpt_flag(order.id)):
        _receipt_dialog(services, order.id)
    elif st.session_state.get(_pay_flag(order.id)):
        _payment_dialog(services, order.id)
    elif st.session_state.get(_refund_flag(order.id)):
        _refund_dialog(services, order.id)


def render_order_detail(services: dict):
    """Detail route entry point: reads ``?id=`` and renders the order view."""
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("order_detail")
    mark_wired("nav.back")
    order_id = navigation.current_detail_id("order_detail")
    if not order_id:
        st.error("No order selected.")
        if st.button("← Back to orders") or consume_action("nav.back"):
            navigation.go_back_to_list("orders", "orders_list")
        return
    _render_order_view(services, order_id)
