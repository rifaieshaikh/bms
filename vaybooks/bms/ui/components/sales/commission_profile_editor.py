"""Shared Streamlit editor for sales/collection commission rule profiles."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

import streamlit as st

from vaybooks.bms.domain.sales.commission_rules import (
    COMMISSION_TYPE_FLAT,
    COMMISSION_TYPE_PERCENTAGE,
    CONFLICT_MAXIMIZE,
    CONFLICT_MINIMIZE,
    CommissionProfile,
    CommissionRule,
    GRAIN_INVOICE,
    GRAIN_LINE,
    SCOPE_ALL,
    SCOPE_CUSTOMER,
    SCOPE_PRODUCT,
    SCOPE_PRODUCT_CATEGORY,
    THRESHOLD_MONTHLY,
    THRESHOLD_QUARTERLY,
    THRESHOLD_YEARLY,
    AgingTier,
    empty_commission_profile,
)


def _rule_editor(
    key_prefix: str,
    label: str,
    rules: List[CommissionRule],
) -> List[CommissionRule]:
    st.markdown(f"**{label}**")
    count = st.number_input(
        f"Number of {label.lower()}",
        min_value=0,
        max_value=20,
        value=len(rules),
        key=f"{key_prefix}_count",
    )
    out: List[CommissionRule] = []
    for i in range(int(count)):
        existing = rules[i] if i < len(rules) else CommissionRule()
        with st.expander(f"{label} #{i + 1}", expanded=i == 0):
            c1, c2, c3 = st.columns(3)
            scope_opts = [
                SCOPE_ALL,
                SCOPE_CUSTOMER,
                SCOPE_PRODUCT_CATEGORY,
                SCOPE_PRODUCT,
            ]
            scope_idx = (
                scope_opts.index(existing.scope_type)
                if existing.scope_type in scope_opts
                else 0
            )
            scope_type = c1.selectbox(
                "Scope",
                scope_opts,
                index=scope_idx,
                key=f"{key_prefix}_{i}_scope",
                format_func=lambda v: {
                    SCOPE_ALL: "All",
                    SCOPE_CUSTOMER: "Customer",
                    SCOPE_PRODUCT_CATEGORY: "Product category",
                    SCOPE_PRODUCT: "Product",
                }.get(v, v),
            )
            grain_opts = [GRAIN_LINE, GRAIN_INVOICE]
            grain_idx = (
                grain_opts.index(existing.grain)
                if existing.grain in grain_opts
                else 0
            )
            grain = c2.selectbox(
                "Grain",
                grain_opts,
                index=grain_idx,
                key=f"{key_prefix}_{i}_grain",
                format_func=lambda v: "Line" if v == GRAIN_LINE else "Invoice",
            )
            priority = c3.number_input(
                "Priority",
                min_value=0,
                value=int(existing.priority or 0),
                key=f"{key_prefix}_{i}_priority",
            )
            scope_ids_raw = st.text_input(
                "Scope IDs (comma-separated)",
                value=",".join(existing.scope_ids or []),
                key=f"{key_prefix}_{i}_scope_ids",
                disabled=scope_type == SCOPE_ALL,
            )
            scope_ids = [
                s.strip() for s in scope_ids_raw.split(",") if s.strip()
            ]
            t1, t2 = st.columns(2)
            type_opts = [COMMISSION_TYPE_PERCENTAGE, COMMISSION_TYPE_FLAT]
            type_idx = (
                type_opts.index(existing.commission_type)
                if existing.commission_type in type_opts
                else 0
            )
            ctype = t1.selectbox(
                "Type",
                type_opts,
                index=type_idx,
                key=f"{key_prefix}_{i}_type",
                format_func=lambda v: (
                    "Percentage" if v == COMMISSION_TYPE_PERCENTAGE else "Flat"
                ),
            )
            rate = t2.number_input(
                "Rate / amount",
                min_value=0.0,
                value=float(existing.commission_rate or 0),
                key=f"{key_prefix}_{i}_rate",
            )
            active = st.checkbox(
                "Active",
                value=bool(existing.is_active),
                key=f"{key_prefix}_{i}_active",
            )
            aging_n = st.number_input(
                "Aging tiers (collection rules)",
                min_value=0,
                max_value=10,
                value=len(existing.aging_tiers or []),
                key=f"{key_prefix}_{i}_aging_n",
            )
            tiers: List[AgingTier] = []
            for j in range(int(aging_n)):
                et = (
                    existing.aging_tiers[j]
                    if j < len(existing.aging_tiers or [])
                    else AgingTier(max_days_overdue=30, commission_rate=0)
                )
                a1, a2 = st.columns(2)
                open_ended = a1.checkbox(
                    "Open-ended",
                    value=et.max_days_overdue is None,
                    key=f"{key_prefix}_{i}_aging_{j}_open",
                )
                max_days = None
                if not open_ended:
                    max_days = int(
                        a1.number_input(
                            "Max days overdue",
                            min_value=0,
                            value=int(et.max_days_overdue or 30),
                            key=f"{key_prefix}_{i}_aging_{j}_days",
                        )
                    )
                tier_rate = a2.number_input(
                    "Tier rate %",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(et.commission_rate or 0),
                    key=f"{key_prefix}_{i}_aging_{j}_rate",
                )
                tiers.append(
                    AgingTier(max_days_overdue=max_days, commission_rate=tier_rate)
                )
            out.append(
                CommissionRule(
                    id=existing.id,
                    priority=int(priority),
                    scope_type=scope_type,
                    scope_ids=scope_ids,
                    grain=grain,
                    commission_type=ctype,
                    commission_rate=float(rate),
                    aging_tiers=tiers,
                    valid_from=existing.valid_from,
                    valid_until=existing.valid_until,
                    is_active=active,
                )
            )
    return out


def render_commission_profile_editor(
    key_prefix: str,
    profile: Optional[CommissionProfile] = None,
) -> CommissionProfile:
    profile = profile or empty_commission_profile()
    st.subheader("Commission profile")
    c1, c2 = st.columns(2)
    include_unpaid = c1.checkbox(
        "Include unpaid invoices (sales rules)",
        value=bool(profile.include_unpaid),
        key=f"{key_prefix}_include_unpaid",
    )
    strategy_opts = [CONFLICT_MAXIMIZE, CONFLICT_MINIMIZE]
    strategy = c2.selectbox(
        "When multiple rules match",
        strategy_opts,
        index=(
            strategy_opts.index(profile.conflict_strategy)
            if profile.conflict_strategy in strategy_opts
            else 0
        ),
        key=f"{key_prefix}_strategy",
        format_func=lambda v: (
            "Maximize commission" if v == CONFLICT_MAXIMIZE else "Minimize commission"
        ),
    )
    t1, t2, t3 = st.columns(3)
    min_sales = t1.number_input(
        "Min sales threshold",
        min_value=0.0,
        value=float(profile.min_sales_amount or 0),
        key=f"{key_prefix}_min_sales",
    )
    min_collection = t2.number_input(
        "Min collection threshold",
        min_value=0.0,
        value=float(profile.min_collection_amount or 0),
        key=f"{key_prefix}_min_coll",
    )
    period_opts = [THRESHOLD_MONTHLY, THRESHOLD_QUARTERLY, THRESHOLD_YEARLY]
    period = t3.selectbox(
        "Threshold reset",
        period_opts,
        index=(
            period_opts.index(profile.threshold_reset_period)
            if profile.threshold_reset_period in period_opts
            else 0
        ),
        key=f"{key_prefix}_period",
    )
    sales_rules = _rule_editor(
        f"{key_prefix}_sales", "Sales rules", list(profile.sales_rules or [])
    )
    collection_rules = _rule_editor(
        f"{key_prefix}_coll",
        "Collection rules",
        list(profile.collection_rules or []),
    )
    draft = CommissionProfile(
        include_unpaid=include_unpaid,
        min_sales_amount=float(min_sales),
        min_collection_amount=float(min_collection),
        threshold_reset_period=period,
        conflict_strategy=strategy,
        sales_rules=sales_rules,
        collection_rules=collection_rules,
    )
    # Do not hard-validate on every Streamlit rerun — incomplete scoped rules
    # (scope set but IDs not filled yet) are normal while editing. Callers
    # should validate on save via validate_commission_profile().
    incomplete = [
        f"{label} #{i + 1}"
        for label, rules in (
            ("Sales rule", sales_rules),
            ("Collection rule", collection_rules),
        )
        for i, rule in enumerate(rules)
        if (rule.scope_type or SCOPE_ALL) != SCOPE_ALL and not (rule.scope_ids or [])
    ]
    if incomplete:
        st.caption(
            "Enter scope IDs for: "
            + ", ".join(incomplete)
            + " (or set Scope to All)."
        )
    return draft


def render_commission_party_multiselect(
    key_prefix: str,
    *,
    agents: list,
    sales_reps: list,
    selected_agent_ids: Optional[list] = None,
    selected_sales_rep_ids: Optional[list] = None,
) -> dict:
    """Multi-select commission agents and sales reps for SO/invoice/receipt."""
    selected_agent_ids = list(selected_agent_ids or [])
    selected_sales_rep_ids = list(selected_sales_rep_ids or [])
    agent_labels = {a.agent_name: a.id for a in agents}
    rep_labels = {w.worker_name: w.id for w in sales_reps}
    with st.expander("Commission parties", expanded=bool(selected_agent_ids or selected_sales_rep_ids)):
        if not agents and not sales_reps:
            st.caption("No commission agents or commission-enabled employees yet.")
            return {"commission_agent_ids": [], "sales_rep_ids": []}
        agent_default = [
            name
            for name, aid in agent_labels.items()
            if aid in selected_agent_ids
        ]
        rep_default = [
            name for name, rid in rep_labels.items() if rid in selected_sales_rep_ids
        ]
        picked_agents = st.multiselect(
            "Commission agents",
            options=list(agent_labels.keys()),
            default=agent_default,
            key=f"{key_prefix}_agents",
        )
        picked_reps = st.multiselect(
            "Sales reps (employees)",
            options=list(rep_labels.keys()),
            default=rep_default,
            key=f"{key_prefix}_reps",
        )
        return {
            "commission_agent_ids": [agent_labels[n] for n in picked_agents],
            "sales_rep_ids": [rep_labels[n] for n in picked_reps],
        }
