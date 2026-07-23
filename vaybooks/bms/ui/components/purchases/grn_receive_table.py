"""GRN receive grid: Product + Qty ordered + Previously received + Received."""

from __future__ import annotations

from typing import Any

import streamlit as st

_COL_WEIGHTS = [2.8, 1.0, 1.1, 1.2]


def _qty_recv_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_qty_recv"


def _hide_qty_steppers(key_prefix: str) -> None:
    st.markdown(
        f"""
<style>
div[class*="st-key-{key_prefix}"][class*="_qty_recv"] input[type="number"]::-webkit-outer-spin-button,
div[class*="st-key-{key_prefix}"][class*="_qty_recv"] input[type="number"]::-webkit-inner-spin-button {{
  -webkit-appearance: none;
  margin: 0;
}}
div[class*="st-key-{key_prefix}"][class*="_qty_recv"] input[type="number"] {{
  -moz-appearance: textfield;
  appearance: textfield;
}}
div[class*="st-key-{key_prefix}"][class*="_qty_recv"] button {{
  display: none !important;
}}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_grn_receive_table(
    *,
    key_prefix: str,
    po_lines: list,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Render PO lines; return (submit lines with Received > 0, over-pending rows).

    Received has no max. Overages are rows where Received > pending
    (Qty ordered − Previously received).
    """
    rows_meta: list[dict[str, Any]] = []
    for i, pl in enumerate(po_lines):
        product_id = getattr(pl, "product_id", None)
        if not product_id:
            continue
        qty_ordered = float(getattr(pl, "qty_ordered", 0) or 0)
        previously = float(getattr(pl, "qty_received", 0) or 0)
        pending = float(getattr(pl, "qty_pending", max(qty_ordered - previously, 0.0)) or 0)
        uid = str(product_id or i)
        rows_meta.append(
            {
                "uid": uid,
                "product_id": product_id,
                "product_name": pl.product_name or product_id,
                "qty_ordered": qty_ordered,
                "previously_received": previously,
                "pending": pending,
                "rate": float(getattr(pl, "rate", 0) or 0),
            }
        )

    kb_chain_key = f"{key_prefix}_kb_chain"
    kb_columns_key = f"{key_prefix}_kb_columns"
    if not rows_meta:
        st.session_state[kb_chain_key] = []
        st.session_state[kb_columns_key] = {"product": [], "qty": [], "rate": []}
        st.info("No lines on this purchase order.")
        return [], []

    _hide_qty_steppers(key_prefix)

    header = st.columns(_COL_WEIGHTS)
    header[0].markdown("**Product**")
    header[1].markdown("**Qty ordered**")
    header[2].markdown("**Previously received**")
    header[3].markdown("**Received**")

    qty_keys: list[str] = []
    result: list[dict[str, Any]] = []
    overages: list[dict[str, Any]] = []
    for row in rows_meta:
        uid = str(row["uid"])
        qkey = _qty_recv_key(key_prefix, uid)
        qty_keys.append(qkey)
        cols = st.columns(_COL_WEIGHTS)
        cols[0].write(row["product_name"])
        cols[1].write(f"{row['qty_ordered']:g}")
        cols[2].write(f"{row['previously_received']:g}")
        pending = float(row["pending"])
        qty = cols[3].number_input(
            "Received",
            min_value=0.0,
            value=0.0,
            key=qkey,
            label_visibility="collapsed",
            help=f"Pending {pending:g} (no hard max — confirm if over)",
        )
        received = float(qty or 0)
        if received <= 0:
            continue
        line = {
            "product_id": row["product_id"],
            "product_name": row["product_name"],
            "qty_received": received,
            "rate": row["rate"],
            "pending": pending,
        }
        result.append(line)
        if received > pending + 0.001:
            overages.append(
                {
                    **line,
                    "qty_ordered": row["qty_ordered"],
                    "previously_received": row["previously_received"],
                    "excess": round(received - pending, 2),
                }
            )

    st.session_state[kb_chain_key] = list(qty_keys)
    st.session_state[kb_columns_key] = {
        "product": [],
        "qty": list(qty_keys),
        "rate": [],
    }
    return result, overages


def grn_table_focus_chain(key_prefix: str) -> list[str]:
    return list(st.session_state.get(f"{key_prefix}_kb_chain") or [])


def grn_table_focus_columns(key_prefix: str) -> dict[str, list[str]]:
    raw = st.session_state.get(f"{key_prefix}_kb_columns") or {}
    return {
        "product": list(raw.get("product") or []),
        "qty": list(raw.get("qty") or []),
        "rate": list(raw.get("rate") or []),
    }
