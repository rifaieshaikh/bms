"""ERP-style shared helpers for sales document detail pages."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Sequence

import pandas as pd
import streamlit as st

from vaybooks.bms.ui.styles import panel, status_badge


def format_document_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def format_money(value: float, *, whole: bool = False) -> str:
    amount = float(value or 0)
    if whole:
        return f"₹{amount:,.0f}"
    return f"₹{amount:,.2f}"


def document_header(
    *,
    number: str,
    status: str | None = None,
    caption_parts: Sequence[str] | None = None,
    left_facts: Sequence[tuple[str, str]] | None = None,
    right_facts: Sequence[tuple[str, str]] | None = None,
    suffix: str,
) -> None:
    """Render title, optional status badge, caption trail, and fact panel."""
    title_cols = st.columns([5, 1] if status else [1])
    with title_cols[0]:
        st.title(number)
    if status:
        with title_cols[1]:
            st.markdown(
                status_badge(status),
                unsafe_allow_html=True,
            )
    parts = [part for part in (caption_parts or []) if part]
    if parts:
        st.caption(" · ".join(parts))

    left = list(left_facts or [])
    right = list(right_facts or [])
    if not left and not right:
        return

    with panel(f"doc_header_{suffix}"):
        with st.container(border=True):
            cols = st.columns(2)
            for label, value in left:
                cols[0].write(f"**{label}:** {value}")
            for label, value in right:
                cols[1].write(f"**{label}:** {value}")


def document_actions(
    actions: Sequence[dict],
    *,
    suffix: str,
) -> dict[str, bool]:
    """Render a compact action row. Returns which action keys were clicked.

    Each action may include:
    - ``label`` (required)
    - ``key`` (required)
    - ``type``: Streamlit button type (default ``secondary``)
    - ``kind``: ``button`` (default) or ``download``
    - ``data`` / ``file_name`` / ``mime`` for downloads
    - ``disabled``: bool
    - ``on_click``: optional zero-arg callback invoked when clicked
    """
    visible = [action for action in actions if action]
    if not visible:
        return {}
    cols = st.columns(min(len(visible), 4) or 1)
    clicked: dict[str, bool] = {}
    for index, action in enumerate(visible):
        col = cols[index % len(cols)]
        key = str(action["key"])
        kind = action.get("kind", "button")
        with col:
            if kind == "download":
                pressed = st.download_button(
                    action["label"],
                    data=action.get("data") or b"",
                    file_name=action.get("file_name") or "document.pdf",
                    mime=action.get("mime") or "application/pdf",
                    key=f"{suffix}_{key}",
                    type=action.get("type", "secondary"),
                    use_container_width=True,
                    disabled=bool(action.get("disabled")),
                )
            else:
                pressed = st.button(
                    action["label"],
                    key=f"{suffix}_{key}",
                    type=action.get("type", "secondary"),
                    use_container_width=True,
                    disabled=bool(action.get("disabled")),
                )
            clicked[key] = bool(pressed)
            if pressed and callable(action.get("on_click")):
                action["on_click"]()
    return clicked


def line_items_table(
    rows: Sequence[dict[str, Any]],
    *,
    show_gst: bool = True,
    suffix: str = "items",
    item_column_label: str = "Product",
) -> None:
    """Render a dense ERP-style items dataframe.

    ``item_column_label`` is typically ``Product`` (sales) or ``Item`` (purchase).
    Display name prefers ``item_name``, then ``product``, then ``description``.
    """
    st.subheader("Line items")
    if not rows:
        st.info("No line items recorded.")
        return

    name_col = item_column_label or "Product"
    frame_rows: list[dict[str, Any]] = []
    for row in rows:
        item = {
            name_col: (
                row.get("item_name")
                or row.get("product")
                or row.get("description")
                or "—"
            ),
            "Qty": float(row.get("qty") or 0),
            "Rate": float(row.get("rate") or 0),
            "Total": float(row.get("total") or row.get("line_total") or 0),
        }
        if row.get("sku"):
            item["SKU"] = row["sku"]
        if show_gst:
            item["HSN/SAC"] = row.get("hsn_sac") or ""
            item["Taxable"] = float(row.get("taxable") or row.get("taxable_amount") or 0)
            item["GST %"] = float(row.get("gst_rate") or 0)
            item["CGST"] = float(row.get("cgst") or row.get("cgst_amount") or 0)
            item["SGST"] = float(row.get("sgst") or row.get("sgst_amount") or 0)
            item["UTGST"] = float(row.get("utgst") or row.get("utgst_amount") or 0)
            item["IGST"] = float(row.get("igst") or row.get("igst_amount") or 0)
        if row.get("qty_ordered") is not None:
            item["Ordered"] = float(row.get("qty_ordered") or 0)
        if row.get("qty_delivered") is not None:
            item["Delivered"] = float(row.get("qty_delivered") or 0)
        if row.get("qty_received") is not None:
            item["Received"] = float(row.get("qty_received") or 0)
        if row.get("qty_invoiced") is not None:
            item["Invoiced"] = float(row.get("qty_invoiced") or 0)
        if row.get("discount") is not None:
            item["Discount"] = float(row.get("discount") or 0)
        frame_rows.append(item)

    df = pd.DataFrame(frame_rows)
    drop_cols = []
    for col in ("CGST", "SGST", "UTGST", "IGST", "Discount", "GST %"):
        if col in df.columns and float(df[col].fillna(0).sum()) == 0:
            drop_cols.append(col)
    if drop_cols:
        df = df.drop(columns=drop_cols)

    preferred = [
        "SKU",
        name_col,
        "HSN/SAC",
        "Ordered",
        "Delivered",
        "Received",
        "Invoiced",
        "Qty",
        "Rate",
        "Discount",
        "Taxable",
        "GST %",
        "CGST",
        "SGST",
        "UTGST",
        "IGST",
        "Total",
    ]
    ordered_cols = [col for col in preferred if col in df.columns]
    df = df[ordered_cols]

    money_cols = {
        "Rate",
        "Discount",
        "Taxable",
        "CGST",
        "SGST",
        "UTGST",
        "IGST",
        "Total",
    }
    qty_cols = {"Qty", "Ordered", "Delivered", "Received", "Invoiced", "GST %"}
    column_config: dict[str, Any] = {}
    for col in df.columns:
        if col in money_cols:
            column_config[col] = st.column_config.NumberColumn(
                col, format="₹%.2f", width="small"
            )
        elif col in qty_cols:
            column_config[col] = st.column_config.NumberColumn(
                col, format="%g", width="small"
            )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        key=f"doc_items_{suffix}",
    )


def totals_ladder(
    summary: dict[str, Any] | None = None,
    *,
    show_gst: bool = True,
    grand_total: float | None = None,
    extra_rows: Sequence[tuple[str, float]] | None = None,
    suffix: str = "totals",
) -> None:
    """Compact right-aligned totals ladder."""
    summary = summary or {}
    rows: list[tuple[str, float]] = []
    if show_gst:
        rows.append(("Taxable", float(summary.get("taxable") or 0)))
        if float(summary.get("igst") or 0) > 0:
            rows.append(("IGST", float(summary.get("igst") or 0)))
        else:
            if float(summary.get("cgst") or 0) > 0:
                rows.append(("CGST", float(summary.get("cgst") or 0)))
            if float(summary.get("utgst") or 0) > 0:
                rows.append(("UTGST", float(summary.get("utgst") or 0)))
            elif float(summary.get("sgst") or 0) > 0:
                rows.append(("SGST", float(summary.get("sgst") or 0)))
        if float(summary.get("total_tax") or 0) > 0:
            rows.append(("Total GST", float(summary.get("total_tax") or 0)))
        total = grand_total
        if total is None:
            total = float(summary.get("grand_total") or 0)
        rows.append(("Grand total", float(total or 0)))
    else:
        total = grand_total
        if total is None:
            total = float(summary.get("grand_total") or 0)
        rows.append(("Total", float(total or 0)))

    for label, value in extra_rows or []:
        rows.append((label, float(value or 0)))

    spacer, body = st.columns([2, 1])
    with body:
        with panel(f"doc_totals_{suffix}"):
            with st.container(border=True):
                for label, value in rows:
                    left, right = st.columns([2, 1])
                    left.caption(label)
                    right.markdown(f"**{format_money(value, whole=True)}**")


def secondary_sections(
    *,
    notes: str = "",
    custom_fields: Sequence[Any] | None = None,
    document_content=None,
) -> None:
    """Collapsed notes, payment, and terms sections."""
    fields = [
        field
        for field in (custom_fields or [])
        if getattr(field, "value", None) not in (None, "")
    ]
    if not fields and document_content is not None:
        fields = [
            field
            for field in getattr(document_content, "custom_fields", []) or []
            if getattr(field, "value", None) not in (None, "")
        ]

    if notes or fields:
        with st.expander("Additional details", expanded=False):
            if notes:
                st.write(f"**Notes:** {notes}")
            for field in fields:
                label = getattr(field, "label", None) or field.get("label")
                value = getattr(field, "value", None)
                if value is None and isinstance(field, dict):
                    value = field.get("value")
                st.write(f"**{label}:** {value}")

    account = getattr(document_content, "bank_account", None) if document_content else None
    if account:
        with st.expander("Payment details", expanded=False):
            st.write(f"**{account.account_name}**")
            if account.bank_name:
                st.caption(f"Bank: {account.bank_name}")
            if account.account_number:
                st.caption(f"Account: {account.account_number}")
            if account.ifsc:
                st.caption(f"IFSC: {account.ifsc}")
            if account.branch:
                st.caption(f"Branch: {account.branch}")
            if account.upi_or_note:
                st.caption(account.upi_or_note)

    terms = ""
    policies = []
    if document_content is not None:
        terms = getattr(document_content, "terms_and_conditions", "") or ""
        policies = list(getattr(document_content, "policies", []) or [])
        if isinstance(document_content, dict):
            terms = document_content.get("terms_and_conditions", "") or ""
            policies = document_content.get("policies", []) or []

    if terms or policies:
        with st.expander("Terms, conditions and policies", expanded=False):
            if terms:
                st.write(terms)
            for policy in sorted(
                policies,
                key=lambda item: getattr(item, "display_order", 0)
                if not isinstance(item, dict)
                else int(item.get("display_order") or 0),
            ):
                title = (
                    getattr(policy, "title", None)
                    if not isinstance(policy, dict)
                    else policy.get("title")
                )
                content = (
                    getattr(policy, "content", None)
                    if not isinstance(policy, dict)
                    else policy.get("content")
                )
                st.write(f"**{title}**")
                st.write(content or "")


def sales_line_row_from_entity(line, *, inventory=None) -> dict[str, Any]:
    """Map a sales line entity (estimate/SO-style) to a table row."""
    qty = float(
        getattr(line, "qty", None)
        or getattr(line, "qty_ordered", None)
        or getattr(line, "qty_delivered", None)
        or 0
    )
    product_id = getattr(line, "product_id", "") or ""
    sku = ""
    if inventory and product_id:
        product = inventory.get_product(product_id)
        if product:
            sku = getattr(product, "sku", "") or ""
    return {
        "sku": sku,
        "product": getattr(line, "product_name", None) or product_id or "—",
        "hsn_sac": getattr(line, "hsn_sac", "") or "",
        "qty": qty,
        "qty_ordered": getattr(line, "qty_ordered", None),
        "qty_delivered": getattr(line, "qty_delivered", None),
        "qty_invoiced": getattr(line, "qty_invoiced", None),
        "rate": float(getattr(line, "rate", 0) or 0),
        "taxable": float(getattr(line, "taxable_amount", 0) or 0),
        "gst_rate": float(getattr(line, "gst_rate", 0) or 0),
        "cgst": float(getattr(line, "cgst_amount", 0) or 0),
        "sgst": float(getattr(line, "sgst_amount", 0) or 0),
        "utgst": float(getattr(line, "utgst_amount", 0) or 0),
        "igst": float(getattr(line, "igst_amount", 0) or 0),
        "total": float(getattr(line, "line_total", 0) or 0),
        "discount": float(getattr(line, "discount", 0) or 0)
        if hasattr(line, "discount")
        else None,
    }
