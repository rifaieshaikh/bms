"""GRN receive grid: Product + ordered/prev + Received/Accepted/Damaged/Rejected (+ batch/serial)."""

from __future__ import annotations

from typing import Any

import streamlit as st

_COL_WEIGHTS = [2.2, 0.8, 0.9, 0.9, 0.9, 0.9, 0.9]


def _qty_key(key_prefix: str, uid: str, field: str) -> str:
    return f"{key_prefix}_r{uid}_{field}"


def _hide_qty_steppers(key_prefix: str) -> None:
    st.markdown(
        f"""
<style>
div[class*="st-key-{key_prefix}"][class*="_qty_"] input[type="number"]::-webkit-outer-spin-button,
div[class*="st-key-{key_prefix}"][class*="_qty_"] input[type="number"]::-webkit-inner-spin-button {{
  -webkit-appearance: none;
  margin: 0;
}}
div[class*="st-key-{key_prefix}"][class*="_qty_"] input[type="number"] {{
  -moz-appearance: textfield;
  appearance: textfield;
}}
div[class*="st-key-{key_prefix}"][class*="_qty_"] button {{
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
    product_flags: dict[str, dict[str, bool]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Render PO lines; return (submit lines with Received > 0, over-pending rows).

    Received has no max. Overages are rows where Received > pending
    (Qty ordered − Previously received).
    """
    flags = product_flags or {}
    rows_meta: list[dict[str, Any]] = []
    for i, pl in enumerate(po_lines):
        product_id = getattr(pl, "product_id", None)
        if not product_id:
            continue
        qty_ordered = float(getattr(pl, "qty_ordered", 0) or 0)
        previously = float(getattr(pl, "qty_received", 0) or 0)
        pending = float(getattr(pl, "qty_pending", max(qty_ordered - previously, 0.0)) or 0)
        uid = str(product_id or i)
        pf = flags.get(str(product_id), {})
        rows_meta.append(
            {
                "uid": uid,
                "product_id": product_id,
                "product_name": pl.product_name or product_id,
                "qty_ordered": qty_ordered,
                "previously_received": previously,
                "pending": pending,
                "rate": float(getattr(pl, "rate", 0) or 0),
                "track_batch": bool(pf.get("track_batch")),
                "track_serial": bool(pf.get("track_serial")),
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
    header[1].markdown("**Ordered**")
    header[2].markdown("**Prev.**")
    header[3].markdown("**Received**")
    header[4].markdown("**Accepted**")
    header[5].markdown("**Damaged**")
    header[6].markdown("**Rejected**")

    qty_keys: list[str] = []
    result: list[dict[str, Any]] = []
    overages: list[dict[str, Any]] = []
    for row in rows_meta:
        uid = str(row["uid"])
        recv_key = _qty_key(key_prefix, uid, "qty_recv")
        acc_key = _qty_key(key_prefix, uid, "qty_acc")
        dmg_key = _qty_key(key_prefix, uid, "qty_dmg")
        rej_key = _qty_key(key_prefix, uid, "qty_rej")
        qty_keys.extend([recv_key, acc_key, dmg_key, rej_key])
        cols = st.columns(_COL_WEIGHTS)
        cols[0].write(row["product_name"])
        cols[1].write(f"{row['qty_ordered']:g}")
        cols[2].write(f"{row['previously_received']:g}")
        pending = float(row["pending"])
        qty_received = cols[3].number_input(
            "Received",
            min_value=0.0,
            value=0.0,
            key=recv_key,
            label_visibility="collapsed",
            help=f"Pending {pending:g} (no hard max — confirm if over)",
        )
        qty_accepted = cols[4].number_input(
            "Accepted",
            min_value=0.0,
            value=0.0,
            key=acc_key,
            label_visibility="collapsed",
        )
        qty_damaged = cols[5].number_input(
            "Damaged",
            min_value=0.0,
            value=0.0,
            key=dmg_key,
            label_visibility="collapsed",
        )
        qty_rejected = cols[6].number_input(
            "Rejected",
            min_value=0.0,
            value=0.0,
            key=rej_key,
            label_visibility="collapsed",
        )
        received = float(qty_received or 0)
        accepted = float(qty_accepted or 0)
        damaged = float(qty_damaged or 0)
        rejected = float(qty_rejected or 0)
        short = round(max(pending - received, 0.0), 2)
        if received > 0 or accepted > 0 or damaged > 0 or rejected > 0:
            st.caption(
                f"{row['product_name']}: short {short:g} "
                f"(accepted+damaged+rejected must equal received)"
            )

        batch_number = ""
        serial_numbers: list[str] = []
        if row["track_batch"] or row["track_serial"]:
            track_cols = st.columns([1, 1] if (row["track_batch"] and row["track_serial"]) else [1])
            col_i = 0
            if row["track_batch"]:
                batch_key = _qty_key(key_prefix, uid, "batch")
                qty_keys.append(batch_key)
                batch_number = track_cols[col_i].text_input(
                    "Batch number",
                    key=batch_key,
                    placeholder="Batch number",
                ).strip()
                col_i += 1
            if row["track_serial"]:
                serial_key = _qty_key(key_prefix, uid, "serials")
                qty_keys.append(serial_key)
                serial_text = track_cols[col_i].text_area(
                    "Serial numbers",
                    key=serial_key,
                    placeholder="One serial per line",
                    height=68,
                )
                serial_numbers = [
                    s.strip()
                    for s in (serial_text or "").replace(",", "\n").splitlines()
                    if s.strip()
                ]

        if received <= 0:
            continue
        # Default accepted to received when disposition left blank
        if accepted == 0 and damaged == 0 and rejected == 0:
            accepted = received
        line = {
            "product_id": row["product_id"],
            "product_name": row["product_name"],
            "qty_received": received,
            "qty_accepted": accepted,
            "qty_damaged": damaged,
            "qty_rejected": rejected,
            "rate": row["rate"],
            "pending": pending,
            "batch_number": batch_number,
            "serial_numbers": serial_numbers,
            "track_batch": row["track_batch"],
            "track_serial": row["track_serial"],
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
