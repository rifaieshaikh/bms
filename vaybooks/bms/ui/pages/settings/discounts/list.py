"""Settings → Discounts: CRUD for product/category/customer/seasonal/global rules."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.sales.discount_entities import (
    APPLY_BOUTIQUE_INVOICE,
    APPLY_SALES_INVOICE,
    APPLY_SALES_ORDER,
    DISCOUNT_TYPE_FIXED,
    DISCOUNT_TYPE_PERCENT,
    SCOPE_CATEGORY,
    SCOPE_CUSTOMER,
    SCOPE_GLOBAL,
    SCOPE_LABELS,
    SCOPE_PRODUCT,
    SCOPE_SEASONAL,
    DiscountRule,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE
from vaybooks.bms.ui.styles import render_card_grid, status_badge

S_ADD = "discount_add_dialog"
S_EDIT = "discount_edit_dialog"
S_DELETE = "discount_delete_dialog"

APPLY_LABELS = {
    APPLY_SALES_ORDER: "Sales order",
    APPLY_SALES_INVOICE: "Sales invoice",
    APPLY_BOUTIQUE_INVOICE: "Boutique invoice",
}

TYPE_LABELS = {
    DISCOUNT_TYPE_PERCENT: "Percent (%)",
    DISCOUNT_TYPE_FIXED: "Fixed (₹)",
}


def _match_scope(rule, value) -> bool:
    return getattr(rule, "scope", "") == value


def _match_active(rule, _value) -> bool:
    return bool(getattr(rule, "is_active", False))


DISCOUNTS = ListSchema(
    entity_key="discount_rules",
    title="Discounts",
    filter_fields=[
        FilterField("name", "Name", F.REGEX),
        FilterField(
            "scope_filter",
            "Scope",
            F.SELECT,
            options=[(k, v) for k, v in SCOPE_LABELS.items()],
            match=_match_scope,
        ),
        FilterField(
            "active_only",
            "Active only",
            F.CHECKBOX,
            match=_match_active,
        ),
    ],
    sort_options=[
        SortOption("priority", "Priority"),
        SortOption("name", "Name"),
        SortOption("created_at", "Created"),
    ],
    default_sort="priority",
    default_desc=False,
    page_size=CARD_PAGE_SIZE,
)


def _product_options(services) -> dict[str, str]:
    inventory = services.get("inventory")
    if not inventory:
        return {}
    return {
        p.id: f"{p.name}" + (f" ({p.sku})" if getattr(p, "sku", "") else "")
        for p in inventory.list_products(active_only=True)
    }


def _category_options(services) -> dict[str, str]:
    inventory = services.get("inventory")
    if not inventory:
        return {}
    return {c.id: c.name for c in inventory.list_categories(active_only=True)}


def _customer_options(services) -> dict[str, str]:
    customers = services.get("customers")
    if not customers:
        return {}
    return {
        c.id: (c.customer_name or c.phone_number or c.id)
        for c in customers.list_all_customers()
    }


def _segment_options(services) -> dict[str, str]:
    segments = services.get("party_segments")
    if not segments:
        return {}
    return {
        s.id: s.name
        for s in segments.list_for_party("customer", active_only=True)
    }


def _labels_for_ids(id_to_label: dict[str, str], ids: list[str]) -> list[str]:
    return [id_to_label[i] for i in ids if i in id_to_label]


def _ids_for_labels(id_to_label: dict[str, str], labels: list[str]) -> list[str]:
    label_to_id = {v: k for k, v in id_to_label.items()}
    return [label_to_id[lbl] for lbl in labels if lbl in label_to_id]


def _apply_to_from_labels(selected: list[str]) -> list[str]:
    return [key for key, label in APPLY_LABELS.items() if label in selected]


def _discount_type_from_label(label: str) -> str:
    for key, text in TYPE_LABELS.items():
        if text == label:
            return key
    return DISCOUNT_TYPE_PERCENT


def _rule_form_fields(services, *, prefix: str, rule: DiscountRule | None = None):
    name = st.text_input(
        "Name *",
        value=rule.name if rule else "",
        key=f"{prefix}_name",
    )
    scope_options = list(SCOPE_LABELS.values())
    current_scope_label = SCOPE_LABELS.get(
        rule.scope if rule else SCOPE_GLOBAL, SCOPE_LABELS[SCOPE_GLOBAL]
    )
    scope_label = st.selectbox(
        "Scope *",
        scope_options,
        index=scope_options.index(current_scope_label),
        key=f"{prefix}_scope",
    )
    scope = next(k for k, v in SCOPE_LABELS.items() if v == scope_label)

    type_options = list(TYPE_LABELS.values())
    current_type = TYPE_LABELS.get(
        rule.discount_type if rule else DISCOUNT_TYPE_PERCENT,
        TYPE_LABELS[DISCOUNT_TYPE_PERCENT],
    )
    type_label = st.selectbox(
        "Discount type *",
        type_options,
        index=type_options.index(current_type),
        key=f"{prefix}_type",
    )
    discount_type = _discount_type_from_label(type_label)
    value = st.number_input(
        "Value *",
        min_value=0.0,
        max_value=100.0 if discount_type == DISCOUNT_TYPE_PERCENT else 1_000_000.0,
        value=float(rule.value if rule else 0),
        step=0.1,
        key=f"{prefix}_value",
    )
    priority = st.number_input(
        "Priority (lower = higher precedence)",
        min_value=1,
        max_value=10_000,
        value=int(rule.priority if rule else 100),
        step=10,
        key=f"{prefix}_priority",
    )
    is_active = st.checkbox(
        "Active",
        value=bool(rule.is_active) if rule else True,
        key=f"{prefix}_active",
    )

    product_ids: list[str] = []
    category_ids: list[str] = []
    customer_ids: list[str] = []
    segment_ids: list[str] = []

    if scope == SCOPE_PRODUCT:
        opts = _product_options(services)
        selected = st.multiselect(
            "Products *",
            list(opts.values()),
            default=_labels_for_ids(opts, rule.product_ids if rule else []),
            key=f"{prefix}_products",
        )
        product_ids = _ids_for_labels(opts, selected)
    elif scope == SCOPE_CATEGORY:
        opts = _category_options(services)
        selected = st.multiselect(
            "Categories *",
            list(opts.values()),
            default=_labels_for_ids(opts, rule.category_ids if rule else []),
            key=f"{prefix}_categories",
        )
        category_ids = _ids_for_labels(opts, selected)
    elif scope == SCOPE_CUSTOMER:
        cust_opts = _customer_options(services)
        seg_opts = _segment_options(services)
        selected_customers = st.multiselect(
            "Customers",
            list(cust_opts.values()),
            default=_labels_for_ids(cust_opts, rule.customer_ids if rule else []),
            key=f"{prefix}_customers",
        )
        selected_segments = st.multiselect(
            "Segments",
            list(seg_opts.values()),
            default=_labels_for_ids(seg_opts, rule.segment_ids if rule else []),
            key=f"{prefix}_segments",
        )
        customer_ids = _ids_for_labels(cust_opts, selected_customers)
        segment_ids = _ids_for_labels(seg_opts, selected_segments)
    elif scope == SCOPE_SEASONAL:
        st.caption(
            "Only one active seasonal campaign is allowed. Optional filters narrow the campaign."
        )
        cust_opts = _customer_options(services)
        prod_opts = _product_options(services)
        cat_opts = _category_options(services)
        selected_customers = st.multiselect(
            "Optional customers",
            list(cust_opts.values()),
            default=_labels_for_ids(cust_opts, rule.customer_ids if rule else []),
            key=f"{prefix}_seasonal_customers",
        )
        selected_products = st.multiselect(
            "Optional products",
            list(prod_opts.values()),
            default=_labels_for_ids(prod_opts, rule.product_ids if rule else []),
            key=f"{prefix}_seasonal_products",
        )
        selected_categories = st.multiselect(
            "Optional categories",
            list(cat_opts.values()),
            default=_labels_for_ids(cat_opts, rule.category_ids if rule else []),
            key=f"{prefix}_seasonal_categories",
        )
        customer_ids = _ids_for_labels(cust_opts, selected_customers)
        product_ids = _ids_for_labels(prod_opts, selected_products)
        category_ids = _ids_for_labels(cat_opts, selected_categories)

    date_cols = st.columns(2)
    default_from = rule.valid_from if rule and rule.valid_from else None
    default_to = rule.valid_to if rule and rule.valid_to else None
    if scope == SCOPE_SEASONAL:
        valid_from = date_cols[0].date_input(
            "Valid from *",
            value=default_from or date.today(),
            key=f"{prefix}_from",
        )
        valid_to = date_cols[1].date_input(
            "Valid to *",
            value=default_to or date.today(),
            key=f"{prefix}_to",
        )
    else:
        use_dates = st.checkbox(
            "Limit by date range",
            value=bool(default_from or default_to),
            key=f"{prefix}_use_dates",
        )
        if use_dates:
            valid_from = date_cols[0].date_input(
                "Valid from",
                value=default_from or date.today(),
                key=f"{prefix}_from",
            )
            valid_to = date_cols[1].date_input(
                "Valid to",
                value=default_to or date.today(),
                key=f"{prefix}_to",
            )
        else:
            valid_from = None
            valid_to = None

    apply_default = [
        APPLY_LABELS[a]
        for a in (rule.apply_to if rule else list(APPLY_LABELS.keys()))
        if a in APPLY_LABELS
    ]
    apply_selected = st.multiselect(
        "Apply to *",
        list(APPLY_LABELS.values()),
        default=apply_default,
        key=f"{prefix}_apply_to",
    )
    max_cap = st.number_input(
        "Max discount amount (₹, optional)",
        min_value=0.0,
        value=float(rule.max_discount_amount) if rule and rule.max_discount_amount else 0.0,
        step=1.0,
        key=f"{prefix}_max",
    )

    return {
        "name": name,
        "scope": scope,
        "discount_type": discount_type,
        "value": float(value),
        "priority": int(priority),
        "is_active": bool(is_active),
        "product_ids": product_ids,
        "category_ids": category_ids,
        "customer_ids": customer_ids,
        "segment_ids": segment_ids,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "apply_to": _apply_to_from_labels(apply_selected),
        "max_discount_amount": float(max_cap) if max_cap > 0 else None,
    }


@st.dialog("Add Discount Rule", width="large", on_dismiss=make_dismiss_handler(S_ADD))
def _add_dialog(services, discounts_svc):
    fields = _rule_form_fields(services, prefix="add_disc")
    if st.button("Create Rule", type="primary", width="stretch"):
        try:
            discounts_svc.create_rule(DiscountRule(**fields))
            st.session_state.pop(S_ADD, None)
            st.success(f"Created discount: {fields['name'].strip()}")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Discount Rule", width="large", on_dismiss=make_dismiss_handler(S_EDIT))
def _edit_dialog(services, discounts_svc, rule_id: str):
    rule = discounts_svc.get_rule(rule_id)
    if not rule:
        st.error("Discount rule not found")
        return
    fields = _rule_form_fields(services, prefix=f"edit_disc_{rule_id}", rule=rule)
    cols = st.columns(2)
    if cols[0].button("Save Changes", type="primary", width="stretch"):
        try:
            discounts_svc.update_rule(rule_id, **fields)
            st.session_state.pop(S_EDIT, None)
            st.success("Discount rule updated")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Delete", width="stretch"):
        st.session_state.pop(S_EDIT, None)
        st.session_state[S_DELETE] = rule_id
        st.rerun()


@st.dialog("Delete Discount Rule", on_dismiss=make_dismiss_handler(S_DELETE))
def _delete_dialog(discounts_svc, rule_id: str):
    rule = discounts_svc.get_rule(rule_id)
    label = rule.name if rule else "this rule"
    st.warning(f"Delete **{label}**?")
    cols = st.columns(2)
    if cols[0].button("Delete", type="primary", width="stretch"):
        try:
            discounts_svc.delete_rule(rule_id)
            st.session_state.pop(S_DELETE, None)
            st.success("Discount rule deleted")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(S_DELETE, None)
        st.rerun()


def _value_caption(rule: DiscountRule) -> str:
    if rule.discount_type == DISCOUNT_TYPE_PERCENT:
        return f"{rule.value:g}%"
    return f"₹{rule.value:,.2f}"


def _rule_card(rule: DiscountRule, index: int, discounts_svc):
    with st.container(border=True):
        status = "Active" if rule.is_active else "Inactive"
        color = "green" if rule.is_active else "gray"
        st.markdown(f"**{rule.name}**")
        st.markdown(status_badge(status, color), unsafe_allow_html=True)
        st.caption(
            f"{SCOPE_LABELS.get(rule.scope, rule.scope)} · {_value_caption(rule)} · "
            f"Priority {rule.priority}"
        )
        if rule.valid_from or rule.valid_to:
            st.caption(
                f"Valid: {rule.valid_from or '…'} → {rule.valid_to or '…'}"
            )
        cols = st.columns(4)
        if cols[0].button(
            "↑",
            key=f"disc_up_{index}_{rule.id}",
            help="Higher precedence",
            width="stretch",
        ):
            try:
                discounts_svc.move_priority(rule.id, direction="up")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
        if cols[1].button(
            "↓",
            key=f"disc_down_{index}_{rule.id}",
            help="Lower precedence",
            width="stretch",
        ):
            try:
                discounts_svc.move_priority(rule.id, direction="down")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
        if cols[2].button(
            "Edit",
            key=f"edit_disc_btn_{index}_{rule.id}",
            width="stretch",
        ):
            st.session_state[S_EDIT] = rule.id
        if cols[3].button(
            "Delete",
            key=f"del_disc_btn_{index}_{rule.id}",
            width="stretch",
        ):
            st.session_state[S_DELETE] = rule.id


def _load_rules(services, filters, sort):
    discounts_svc = services.get("discounts")
    if not discounts_svc:
        return []
    try:
        return discounts_svc.list_rules(active_only=False)
    except Exception:
        return []


def _render_cards(page_rules, services):
    discounts_svc = services.get("discounts")

    def _card(rule, i):
        return _rule_card(rule, i, discounts_svc)

    render_card_grid(page_rules, _card, suffix="discounts")


def render(services: dict):
    discounts_svc = services.get("discounts")
    if discounts_svc is None:
        st.error("Discount service is not available.")
        return

    st.caption(
        "Configure product, category, customer, seasonal, and global discounts. "
        "Lower priority wins; only one rule applies per line. "
        "Use Apply discounts on sales orders, invoices, and boutique invoices."
    )
    bar = render_list(
        DISCOUNTS,
        services=services,
        load_fn=_load_rules,
        card_renderer=_render_cards,
        primary_label="Add Discount",
        primary_key="discounts_add_btn",
        count_label="rules",
        empty_text="No discount rules yet. Create one to start suggesting discounts on sales.",
        page_key_nav="discounts_list",
    )
    if bar["primary_clicked"]:
        st.session_state[S_ADD] = True

    if st.session_state.get(S_ADD):
        _add_dialog(services, discounts_svc)
    if st.session_state.get(S_EDIT):
        _edit_dialog(services, discounts_svc, st.session_state[S_EDIT])
    if st.session_state.get(S_DELETE):
        _delete_dialog(discounts_svc, st.session_state[S_DELETE])
