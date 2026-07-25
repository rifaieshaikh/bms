"""Stock transfer detail with status-driven actions."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import StockTransferStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.document_detail import (
    document_actions,
    document_header,
    format_document_date,
)


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("inventory_transfer_detail")
    mark_wired("nav.back")
    inventory = services["inventory"]
    transfer_id = navigation.current_detail_id("inventory_transfer_detail")

    if st.button("← Back to transfers", key="inv_transfer_detail_back") or consume_action(
        "nav.back"
    ):
        navigation.go_back_to_list("inventory_transfers", "inventory_transfers_list")
        return

    if not transfer_id:
        st.error("Transfer not specified")
        return

    transfer = inventory.get_stock_transfer(transfer_id)
    if not transfer:
        st.error("Stock transfer not found")
        return

    document_header(
        number=transfer.transfer_number,
        status=transfer.status.value,
        caption_parts=[f"{transfer.from_location_name} → {transfer.to_location_name}"],
        left_facts=[
            ("Transfer date", format_document_date(transfer.transfer_date)),
            ("From location", transfer.from_location_name),
        ],
        right_facts=[
            ("To location", transfer.to_location_name),
            ("Status", transfer.status.value),
        ],
        suffix=f"transfer_{transfer.id}",
    )

    st.subheader("Line items")
    if not transfer.lines:
        st.info("No line items recorded.")
    else:
        rows = [
            {
                "Product": line.product_name or line.product_id,
                "Qty": line.qty,
            }
            for line in transfer.lines
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    if transfer.notes:
        st.caption(f"Notes: {transfer.notes}")

    actions = []
    if transfer.status == StockTransferStatus.DRAFT:
        actions.append(
            {"label": "Dispatch", "key": "transfer_dispatch", "type": "primary"}
        )
        actions.append({"label": "Cancel", "key": "transfer_cancel"})
    elif transfer.status == StockTransferStatus.DISPATCHED:
        actions.append(
            {"label": "Receive", "key": "transfer_receive", "type": "primary"}
        )
        actions.append({"label": "Cancel", "key": "transfer_cancel"})

    clicked = document_actions(actions, suffix=f"transfer_{transfer.id}")
    if clicked.get("transfer_dispatch"):
        try:
            inventory.dispatch_stock_transfer(transfer.id)
            st.success("Transfer dispatched")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if clicked.get("transfer_receive"):
        try:
            inventory.receive_stock_transfer(transfer.id)
            st.success("Transfer received")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if clicked.get("transfer_cancel"):
        try:
            inventory.cancel_stock_transfer(transfer.id)
            st.success("Transfer cancelled")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
