"""Cards for delivery notes."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid, status_badge


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _dn_row(dn) -> dict:
    ref = getattr(dn, "reference_label", None) or dn.so_number or ""
    charges = getattr(dn, "charges", None)
    return {
        "id": dn.id,
        "dn_number": dn.dn_number,
        "so_number": dn.so_number,
        "invoice_number": getattr(dn, "invoice_number", "") or "",
        "reference_label": ref,
        "customer_id": dn.customer_id,
        "customer_name": dn.customer_name,
        "delivery_date": dn.delivery_date,
        "status": dn.status.value if hasattr(dn.status, "value") else str(dn.status),
        "total_amount": dn.total_amount,
        "total_qty": getattr(dn, "total_qty", 0),
        "delivery_partner_name": getattr(dn, "delivery_partner_name", "") or "",
        "vehicle_number": getattr(dn, "vehicle_number", "") or "",
        "delivery_charge": charges.amount if charges else 0,
        "payment_status": (
            charges.payment_status.value
            if charges and hasattr(charges.payment_status, "value")
            else (charges.payment_status if charges else "")
        ),
        "location_id": getattr(dn, "location_id", "") or "",
        "delivery_partner_id": getattr(dn, "delivery_partner_id", "") or "",
    }


def _dn_card(row: dict, suffix: str) -> None:
    with st.container(border=True):
        st.markdown(f'<p class="z-card-title">{row.get("dn_number")}</p>', unsafe_allow_html=True)
        st.caption(row.get("customer_name") or "Customer")
        if row.get("reference_label"):
            st.caption(row.get("reference_label"))
        if row.get("delivery_partner_name"):
            st.caption(row.get("delivery_partner_name"))
        if row.get("vehicle_number"):
            st.caption(f"Vehicle {row.get('vehicle_number')}")
        st.caption(_fmt_date(row.get("delivery_date")))
        st.markdown(status_badge(row.get("status") or "Draft", compact=True), unsafe_allow_html=True)
        st.caption(
            f"Qty {float(row.get('total_qty') or 0):g} · "
            f"Charge ₹{float(row.get('delivery_charge') or 0):,.0f} · "
            f"{row.get('payment_status') or '—'}"
        )
        if st.button("View", key=f"dn_view_{suffix}_{row.get('id')}", width="stretch"):
            navigation.go_to_detail("delivery_note_detail", row.get("id"))

def delivery_note_cards(rows: list[dict], suffix: str = "dn") -> None:
    render_card_grid(rows, lambda row, _idx: _dn_card(row, suffix), suffix=suffix)
