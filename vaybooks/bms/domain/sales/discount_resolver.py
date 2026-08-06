"""Resolve one winning discount rule per line (priority-first, no stacking)."""

from __future__ import annotations

from datetime import date
from typing import Iterable, List, Optional, Sequence

from vaybooks.bms.domain.sales.discount_entities import (
    BOUTIQUE_SCOPES,
    DISCOUNT_TYPE_PERCENT,
    SCOPE_CATEGORY,
    SCOPE_CUSTOMER,
    SCOPE_GLOBAL,
    SCOPE_PRODUCT,
    SCOPE_SEASONAL,
    SCOPE_SPECIFICITY,
    DiscountResult,
    DiscountRule,
)


def rule_is_effective(rule: DiscountRule, on_date: date) -> bool:
    if not rule.is_active:
        return False
    if rule.valid_from and on_date < rule.valid_from:
        return False
    if rule.valid_to and on_date > rule.valid_to:
        return False
    return True


def compute_discount_amount(
    *,
    rule: DiscountRule,
    qty: float,
    rate: float,
) -> float:
    """Compute ₹ discount from selling-rate gross, capped at line gross and optional max."""
    gross = round(max(float(qty or 0), 0.0) * max(float(rate or 0), 0.0), 2)
    if gross <= 0:
        return 0.0
    if rule.discount_type == DISCOUNT_TYPE_PERCENT:
        amount = round(gross * min(max(float(rule.value or 0), 0.0), 100.0) / 100.0, 2)
    else:
        amount = round(max(float(rule.value or 0), 0.0), 2)
    amount = min(amount, gross)
    if rule.max_discount_amount is not None:
        amount = min(amount, round(float(rule.max_discount_amount), 2))
    return round(max(amount, 0.0), 2)


def _targets_intersect(rule_ids: Sequence[str], candidate_ids: Sequence[str]) -> bool:
    if not rule_ids:
        return False
    return bool(set(rule_ids) & set(candidate_ids))


def _optional_target_ok(
    rule: DiscountRule,
    *,
    product_id: str,
    category_ids: Sequence[str],
    customer_id: str,
    customer_segment_ids: Sequence[str],
) -> bool:
    """When seasonal/global set optional targets, all non-empty target groups must match."""
    checks: list[bool] = []
    if rule.product_ids:
        checks.append(product_id in rule.product_ids)
    if rule.category_ids:
        checks.append(_targets_intersect(rule.category_ids, category_ids))
    if rule.customer_ids:
        checks.append(customer_id in rule.customer_ids)
    if rule.segment_ids:
        checks.append(_targets_intersect(rule.segment_ids, customer_segment_ids))
    if not checks:
        return True
    return all(checks)


def rule_matches_line(
    rule: DiscountRule,
    *,
    product_id: str = "",
    category_ids: Optional[Sequence[str]] = None,
    customer_id: str = "",
    customer_segment_ids: Optional[Sequence[str]] = None,
    apply_to: str,
    on_date: date,
    boutique: bool = False,
) -> bool:
    if apply_to not in (rule.apply_to or []):
        return False
    if not rule_is_effective(rule, on_date):
        return False
    if boutique and rule.scope not in BOUTIQUE_SCOPES:
        return False

    category_ids = list(category_ids or [])
    customer_segment_ids = list(customer_segment_ids or [])
    product_id = (product_id or "").strip()
    customer_id = (customer_id or "").strip()

    if rule.scope == SCOPE_PRODUCT:
        return bool(product_id) and product_id in (rule.product_ids or [])

    if rule.scope == SCOPE_CATEGORY:
        return _targets_intersect(rule.category_ids or [], category_ids)

    if rule.scope == SCOPE_CUSTOMER:
        if customer_id and customer_id in (rule.customer_ids or []):
            return True
        return _targets_intersect(rule.segment_ids or [], customer_segment_ids)

    if rule.scope == SCOPE_SEASONAL:
        return _optional_target_ok(
            rule,
            product_id=product_id,
            category_ids=category_ids,
            customer_id=customer_id,
            customer_segment_ids=customer_segment_ids,
        )

    if rule.scope == SCOPE_GLOBAL:
        return _optional_target_ok(
            rule,
            product_id=product_id,
            category_ids=category_ids,
            customer_id=customer_id,
            customer_segment_ids=customer_segment_ids,
        )

    return False


def _sort_key(rule: DiscountRule) -> tuple:
    # Lower priority wins; higher specificity breaks ties.
    return (
        int(rule.priority),
        -int(SCOPE_SPECIFICITY.get(rule.scope, 0)),
        rule.name or "",
        rule.id or "",
    )


def pick_winning_rule(candidates: Iterable[DiscountRule]) -> Optional[DiscountRule]:
    ranked = sorted(candidates, key=_sort_key)
    return ranked[0] if ranked else None


def resolve_line_discount(
    rules: Sequence[DiscountRule],
    *,
    qty: float,
    rate: float,
    product_id: str = "",
    category_ids: Optional[Sequence[str]] = None,
    customer_id: str = "",
    customer_segment_ids: Optional[Sequence[str]] = None,
    apply_to: str,
    on_date: date,
    boutique: bool = False,
) -> Optional[DiscountResult]:
    """Return the single winning discount for a line, or None."""
    matches = [
        rule
        for rule in rules
        if rule_matches_line(
            rule,
            product_id=product_id,
            category_ids=category_ids,
            customer_id=customer_id,
            customer_segment_ids=customer_segment_ids,
            apply_to=apply_to,
            on_date=on_date,
            boutique=boutique,
        )
    ]
    winner = pick_winning_rule(matches)
    if not winner:
        return None
    amount = compute_discount_amount(rule=winner, qty=qty, rate=rate)
    if amount <= 0:
        return None
    return DiscountResult(
        rule_id=winner.id,
        rule_name=winner.name,
        amount=amount,
        scope=winner.scope,
    )


def resolve_lines(
    rules: Sequence[DiscountRule],
    lines: Sequence[dict],
    *,
    customer_id: str = "",
    customer_segment_ids: Optional[Sequence[str]] = None,
    apply_to: str,
    on_date: date,
    boutique: bool = False,
    qty_field: str = "qty",
) -> List[Optional[DiscountResult]]:
    """Resolve one discount per line dict.

    Each line may include: product_id, category_ids, qty (or qty_field), rate.
    For boutique, pass qty=1 and rate=item gross.
    """
    results: List[Optional[DiscountResult]] = []
    for raw in lines:
        qty = float(raw.get(qty_field) if raw.get(qty_field) is not None else raw.get("qty") or 0)
        rate = float(raw.get("rate") or 0)
        product_id = str(raw.get("product_id") or "").strip()
        category_ids = list(raw.get("category_ids") or [])
        results.append(
            resolve_line_discount(
                rules,
                qty=qty,
                rate=rate,
                product_id=product_id,
                category_ids=category_ids,
                customer_id=customer_id,
                customer_segment_ids=customer_segment_ids,
                apply_to=apply_to,
                on_date=on_date,
                boutique=boutique,
            )
        )
    return results
