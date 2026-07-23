"""Customer-specific sales price history."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_CUSTOMER_PRICES
from vaybooks.bms.ui.keyboard.wired import mark_wired

_HISTORY_DIALOG = "customer_price_history_dialog"


def _fmt_date(value) -> str:
    if isinstance(value, datetime):
        return value.date().strftime("%d %b %Y")
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _entry_to_row(entry, *, mobile: str = "", selling_rate: float = 0.0) -> dict:
    rate = round(float(getattr(entry, "rate", 0) or 0), 2)
    selling = round(float(selling_rate or 0), 2)
    return {
        "id": getattr(entry, "id", ""),
        "customer_id": getattr(entry, "customer_id", ""),
        "customer_name": getattr(entry, "customer_name", "") or "",
        "mobile": mobile or "",
        "product_id": getattr(entry, "product_id", ""),
        "sku": getattr(entry, "sku", "") or "",
        "product_name": getattr(entry, "product_name", "") or "",
        "customer_rate": rate,
        "selling_rate": selling,
        "difference": round(rate - selling, 2),
        "effective_date": getattr(entry, "effective_date", None),
        "store_invoice_number": getattr(entry, "store_invoice_number", "") or "",
        "voucher_id": getattr(entry, "voucher_id", "") or "",
    }


def _latest_rows(services) -> list[dict]:
    sales = services.get("sales")
    if not sales:
        return []
    entries = sales.list_customer_prices(limit=2000)
    customers = services.get("customers")
    inventory = services.get("inventory")
    phone_by_customer: dict[str, str] = {}
    selling_by_product: dict[str, float] = {}
    latest: dict[tuple[str, str], object] = {}
    for entry in entries:
        key = (entry.customer_id, entry.product_id)
        existing = latest.get(key)
        if existing is None:
            latest[key] = entry
            continue
        existing_date = getattr(existing, "effective_date", date.min)
        entry_date = getattr(entry, "effective_date", date.min)
        existing_created = getattr(existing, "created_at", datetime.min)
        entry_created = getattr(entry, "created_at", datetime.min)
        if entry_date > existing_date or (
            entry_date == existing_date and entry_created > existing_created
        ):
            latest[key] = entry

    rows = []
    for entry in latest.values():
        customer_id = entry.customer_id
        product_id = entry.product_id
        if customer_id not in phone_by_customer and customers:
            detail = customers.get_customer_detail(customer_id)
            phone_by_customer[customer_id] = (
                (getattr(detail, "phone_number", "") or "") if detail else ""
            )
        if product_id not in selling_by_product and inventory:
            product = inventory.get_product(product_id)
            selling_by_product[product_id] = float(
                getattr(product, "selling_rate", 0) or 0
            ) if product else 0.0
        rows.append(
            _entry_to_row(
                entry,
                mobile=phone_by_customer.get(customer_id, ""),
                selling_rate=selling_by_product.get(product_id, 0.0),
            )
        )
    return rows


def _load_customer_prices(services, filters, sort):
    try:
        return _latest_rows(services)
    except Exception:
        return []


@st.dialog(
    "Customer price history",
    width="large",
    on_dismiss=make_dismiss_handler(_HISTORY_DIALOG),
)
def _history_dialog(services: dict) -> None:
    payload = st.session_state.get(_HISTORY_DIALOG)
    if not payload:
        return
    sales = services.get("sales")
    customer_id = payload.get("customer_id")
    product_id = payload.get("product_id")
    st.markdown(
        f"**{payload.get('customer_name') or 'Customer'}** · "
        f"{payload.get('sku') or ''} {payload.get('product_name') or ''}"
    )
    history = []
    if sales:
        history = sales.list_customer_price_history(
            customer_id, product_id, limit=100
        )
    if not history:
        st.info("No recorded rates for this customer and product.")
        return
    rows = [
        {
            "Effective date": _fmt_date(item.effective_date),
            "Customer rate": float(item.rate or 0),
            "Source invoice": item.store_invoice_number or "—",
            "Recorded": _fmt_date(item.created_at),
        }
        for item in history
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_table(page_rows, services):
    if not page_rows:
        return
    rows = []
    for row in page_rows:
        rows.append(
            {
                "Customer": row.get("customer_name") or "",
                "Mobile": row.get("mobile") or "",
                "SKU": row.get("sku") or "",
                "Product": row.get("product_name") or "",
                "Customer rate": row.get("customer_rate") or 0,
                "Current selling price": row.get("selling_rate") or 0,
                "Difference": row.get("difference") or 0,
                "Effective date": _fmt_date(row.get("effective_date")),
                "Source invoice": row.get("store_invoice_number") or "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    options = {
        f"{row.get('customer_name')} · {row.get('sku')} · "
        f"{row.get('product_name')}": row
        for row in page_rows
    }
    if not options:
        return
    selected = st.selectbox(
        "View rate history",
        ["—"] + list(options.keys()),
        key="customer_prices_history_pick",
    )
    if selected != "—" and st.button(
        "Open history", key="customer_prices_history_open"
    ):
        st.session_state[_HISTORY_DIALOG] = options[selected]
        st.rerun()


def render(services: dict):
    mark_wired("list.filters.open", "list.sort.open")
    if st.session_state.get(_HISTORY_DIALOG):
        _history_dialog(services)
    render_list(
        INVENTORY_CUSTOMER_PRICES,
        services=services,
        load_fn=_load_customer_prices,
        card_renderer=_render_table,
        count_label="customer prices",
        empty_text="No customer-specific prices recorded yet. "
        "They appear when a Sales Invoice posts a new rate for a customer.",
        page_key_nav="inventory_customer_prices_list",
    )
