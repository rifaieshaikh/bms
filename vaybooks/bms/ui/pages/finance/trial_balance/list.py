"""Trial Balance route."""

import pandas as pd
import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.components.filter_sort_bar import render_filter_sort_bar
from vaybooks.bms.ui.list_schemas import TRIAL_BALANCE
from vaybooks.bms.ui.pagination import TRIAL_BALANCE_PAGE_SIZE, paginate_list, \
    render_page_controls


def render(services: dict):
    accounting_service = services["accounting"]
    try:
        trial = accounting_service.get_trial_balance()
    except Exception:
        trial = []
    for row in trial:
        row["balance"] = round(row.get("debit", 0) - row.get("credit", 0), 2)

    bar = render_filter_sort_bar(TRIAL_BALANCE, services=services)
    filters, sort = bar["filters"], bar["sort"]

    filtered = F.apply_filters(trial, TRIAL_BALANCE, filters)
    ordered = F.sort_records(filtered, TRIAL_BALANCE, sort)

    if not ordered:
        st.info("No balances to show.")
        return

    total_debit = round(sum(r["debit"] for r in ordered), 2)
    total_credit = round(sum(r["credit"] for r in ordered), 2)
    balanced = abs(total_debit - total_credit) < 0.01
    cols = st.columns(3)
    cols[0].metric("Total Debit", f"₹{total_debit:,.2f}")
    cols[1].metric("Total Credit", f"₹{total_credit:,.2f}")
    cols[2].metric("Status", "Balanced ✓" if balanced else "Unbalanced ✗")

    token = F.filter_token(TRIAL_BALANCE, filters, sort)
    page_trial, page, total_pages = paginate_list(
        ordered,
        page_key="trial_balance_page",
        page_size=TRIAL_BALANCE_PAGE_SIZE,
        filter_key="trial_balance_page_token",
        filter_value=token,
    )
    rows = [
        {
            "Account": r["account_name"],
            "Type": r["account_type"],
            "Debit": f"{r['debit']:,.2f}" if r["debit"] else "",
            "Credit": f"{r['credit']:,.2f}" if r["credit"] else "",
        }
        for r in page_trial
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    render_page_controls(
        page, total_pages, len(ordered),
        page_key="trial_balance_page", prev_key="trial_balance_prev",
        next_key="trial_balance_next", label="accounts",
    )
