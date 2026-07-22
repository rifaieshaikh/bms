"""Purchase return detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.document_detail import (
    document_header,
    format_document_date,
    format_money,
    line_items_table,
    totals_ladder,
)


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("purchase_return_detail")
    mark_wired("nav.back")
    return_id = navigation.current_detail_id("purchase_return_detail") or st.query_params.get(
        "id"
    )
    if not return_id:
        st.warning("Purchase return not specified")
        return

    purchases = services["purchases"]
    purchase_return = purchases.get_purchase_return(return_id)
    if not purchase_return:
        st.warning("Purchase return not found")
        return

    if st.button("← Back", key="purchase_return_detail_back") or consume_action(
        "nav.back"
    ):
        navigation.go_back_to_list("purchase_returns_list", "purchase-returns")
        return

    document_header(
        number=purchase_return.return_number,
        caption_parts=[f"Vendor: {purchase_return.vendor_name}"],
        left_facts=[
            ("Return date", format_document_date(purchase_return.return_date)),
            ("Vendor", purchase_return.vendor_name or "—"),
        ],
        right_facts=[
            ("Total", format_money(purchase_return.total_amount)),
            (
                "Source bill",
                (purchase_return.source_bill_id or "—")[:16]
                if purchase_return.source_bill_id
                else "—",
            ),
        ],
        suffix=f"pret_{purchase_return.id}",
    )

    table_rows = [
        {
            "item_name": line.product_name or line.product_id or "—",
            "product": line.product_name or line.product_id or "—",
            "qty": line.qty,
            "rate": line.rate,
            "total": line.line_total,
            "line_total": line.line_total,
        }
        for line in purchase_return.lines
    ]
    line_items_table(
        table_rows,
        show_gst=False,
        suffix=f"pret_{purchase_return.id}",
        item_column_label="Item",
    )
    totals_ladder(
        show_gst=False,
        grand_total=purchase_return.total_amount,
        suffix=f"pret_{purchase_return.id}",
    )
    if purchase_return.notes:
        st.caption(f"Notes: {purchase_return.notes}")
