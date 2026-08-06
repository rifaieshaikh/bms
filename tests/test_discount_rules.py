"""Unit tests for discount rules resolver and app-service exclusivity."""

from datetime import date, timedelta
from typing import List, Optional

import pytest

from vaybooks.bms.application.sales.discounts.service import DiscountAppService
from vaybooks.bms.domain.sales.discount_entities import (
    APPLY_BOUTIQUE_INVOICE,
    APPLY_SALES_INVOICE,
    APPLY_SALES_ORDER,
    DISCOUNT_TYPE_FIXED,
    DISCOUNT_TYPE_PERCENT,
    SCOPE_CATEGORY,
    SCOPE_CUSTOMER,
    SCOPE_GLOBAL,
    SCOPE_PRODUCT,
    SCOPE_SEASONAL,
    DiscountRule,
)
from vaybooks.bms.domain.sales.discount_resolver import (
    compute_discount_amount,
    resolve_line_discount,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class InMemoryDiscountRuleRepository:
    def __init__(self):
        self._rules: dict[str, DiscountRule] = {}

    def save(self, rule: DiscountRule) -> DiscountRule:
        self._rules[rule.id] = rule
        return rule

    def find_by_id(self, rule_id: str) -> Optional[DiscountRule]:
        return self._rules.get(rule_id)

    def list_all(self, active_only: bool = False) -> List[DiscountRule]:
        rules = list(self._rules.values())
        if active_only:
            rules = [r for r in rules if r.is_active]
        return sorted(rules, key=lambda r: (r.priority, r.name, r.id))

    def list_active_seasonal(
        self, exclude_id: Optional[str] = None
    ) -> List[DiscountRule]:
        return [
            r
            for r in self.list_all(active_only=True)
            if r.scope == SCOPE_SEASONAL and r.id != exclude_id
        ]

    def delete(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)


def _rule(**kwargs) -> DiscountRule:
    defaults = dict(
        name="Rule",
        scope=SCOPE_GLOBAL,
        discount_type=DISCOUNT_TYPE_PERCENT,
        value=10.0,
        priority=100,
        is_active=True,
        apply_to=[APPLY_SALES_ORDER, APPLY_SALES_INVOICE, APPLY_BOUTIQUE_INVOICE],
    )
    defaults.update(kwargs)
    return DiscountRule(**defaults)


def test_percent_and_fixed_amounts_use_selling_rate_gross():
    percent = _rule(discount_type=DISCOUNT_TYPE_PERCENT, value=10)
    fixed = _rule(discount_type=DISCOUNT_TYPE_FIXED, value=50)
    assert compute_discount_amount(rule=percent, qty=2, rate=100) == 20.0
    assert compute_discount_amount(rule=fixed, qty=2, rate=100) == 50.0


def test_max_discount_cap():
    rule = _rule(discount_type=DISCOUNT_TYPE_PERCENT, value=50, max_discount_amount=30)
    assert compute_discount_amount(rule=rule, qty=2, rate=100) == 30.0


def test_priority_lower_wins_over_specificity():
    product_rule = _rule(
        name="Product 20%",
        scope=SCOPE_PRODUCT,
        product_ids=["p1"],
        value=20,
        priority=50,
    )
    global_rule = _rule(name="Global 5%", scope=SCOPE_GLOBAL, value=5, priority=10)
    result = resolve_line_discount(
        [product_rule, global_rule],
        qty=1,
        rate=100,
        product_id="p1",
        apply_to=APPLY_SALES_INVOICE,
        on_date=date.today(),
    )
    assert result is not None
    assert result.rule_name == "Global 5%"
    assert result.amount == 5.0


def test_specificity_tiebreak_when_priority_equal():
    product_rule = _rule(
        name="Product",
        scope=SCOPE_PRODUCT,
        product_ids=["p1"],
        value=10,
        priority=10,
    )
    customer_rule = _rule(
        name="Customer",
        scope=SCOPE_CUSTOMER,
        customer_ids=["c1"],
        value=15,
        priority=10,
    )
    result = resolve_line_discount(
        [product_rule, customer_rule],
        qty=1,
        rate=100,
        product_id="p1",
        customer_id="c1",
        apply_to=APPLY_SALES_INVOICE,
        on_date=date.today(),
    )
    assert result is not None
    assert result.rule_name == "Customer"
    assert result.amount == 15.0


def test_category_and_segment_matching():
    category_rule = _rule(
        name="Cat",
        scope=SCOPE_CATEGORY,
        category_ids=["cat1"],
        value=8,
        priority=20,
    )
    segment_rule = _rule(
        name="Seg",
        scope=SCOPE_CUSTOMER,
        segment_ids=["seg1"],
        value=12,
        priority=30,
    )
    cat_result = resolve_line_discount(
        [category_rule],
        qty=1,
        rate=200,
        product_id="p1",
        category_ids=["cat1", "cat2"],
        apply_to=APPLY_SALES_ORDER,
        on_date=date.today(),
    )
    seg_result = resolve_line_discount(
        [segment_rule],
        qty=1,
        rate=200,
        customer_id="c9",
        customer_segment_ids=["seg1"],
        apply_to=APPLY_SALES_ORDER,
        on_date=date.today(),
    )
    assert cat_result and cat_result.amount == 16.0
    assert seg_result and seg_result.amount == 24.0


def test_seasonal_date_window():
    today = date.today()
    rule = _rule(
        name="Season",
        scope=SCOPE_SEASONAL,
        value=10,
        valid_from=today - timedelta(days=1),
        valid_to=today + timedelta(days=1),
    )
    inside = resolve_line_discount(
        [rule],
        qty=1,
        rate=100,
        apply_to=APPLY_SALES_INVOICE,
        on_date=today,
    )
    outside = resolve_line_discount(
        [rule],
        qty=1,
        rate=100,
        apply_to=APPLY_SALES_INVOICE,
        on_date=today + timedelta(days=5),
    )
    assert inside and inside.amount == 10.0
    assert outside is None


def test_boutique_ignores_product_and_category_scopes():
    product_rule = _rule(
        name="Product",
        scope=SCOPE_PRODUCT,
        product_ids=["p1"],
        value=20,
        priority=1,
    )
    global_rule = _rule(name="Global", scope=SCOPE_GLOBAL, value=5, priority=50)
    result = resolve_line_discount(
        [product_rule, global_rule],
        qty=1,
        rate=1000,
        product_id="p1",
        apply_to=APPLY_BOUTIQUE_INVOICE,
        on_date=date.today(),
        boutique=True,
    )
    assert result is not None
    assert result.rule_name == "Global"
    assert result.amount == 50.0


def test_apply_to_filter():
    rule = _rule(
        name="SO only",
        scope=SCOPE_GLOBAL,
        value=10,
        apply_to=[APPLY_SALES_ORDER],
    )
    so = resolve_line_discount(
        [rule],
        qty=1,
        rate=100,
        apply_to=APPLY_SALES_ORDER,
        on_date=date.today(),
    )
    inv = resolve_line_discount(
        [rule],
        qty=1,
        rate=100,
        apply_to=APPLY_SALES_INVOICE,
        on_date=date.today(),
    )
    assert so and so.amount == 10.0
    assert inv is None


def test_seasonal_exclusivity_rejects_second_active():
    svc = DiscountAppService(InMemoryDiscountRuleRepository())
    today = date.today()
    svc.create_rule(
        _rule(
            name="Summer",
            scope=SCOPE_SEASONAL,
            value=10,
            valid_from=today,
            valid_to=today + timedelta(days=30),
            is_active=True,
        )
    )
    with pytest.raises(ValidationError, match="seasonal campaign"):
        svc.create_rule(
            _rule(
                name="Winter",
                scope=SCOPE_SEASONAL,
                value=15,
                valid_from=today,
                valid_to=today + timedelta(days=30),
                is_active=True,
            )
        )


def test_reorder_priorities():
    svc = DiscountAppService(InMemoryDiscountRuleRepository())
    a = svc.create_rule(_rule(name="A", priority=10, value=1))
    b = svc.create_rule(_rule(name="B", priority=20, value=2))
    c = svc.create_rule(_rule(name="C", priority=30, value=3))
    svc.reorder_priorities([c.id, a.id, b.id])
    rules = {r.id: r for r in svc.list_rules()}
    assert rules[c.id].priority == 10
    assert rules[a.id].priority == 20
    assert rules[b.id].priority == 30
