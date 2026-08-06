from __future__ import annotations

from datetime import date
from typing import List, Optional, Sequence

from vaybooks.bms.domain.sales.discount_entities import (
    SCOPE_SEASONAL,
    DiscountResult,
    DiscountRule,
    validate_discount_rule,
)
from vaybooks.bms.domain.sales.discount_resolver import resolve_line_discount, resolve_lines
from vaybooks.bms.domain.sales.repository import DiscountRuleRepository
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError


class DiscountAppService:
    def __init__(self, rule_repo: DiscountRuleRepository):
        self._repo = rule_repo

    def list_rules(self, active_only: bool = False) -> List[DiscountRule]:
        return self._repo.list_all(active_only=active_only)

    def get_rule(self, rule_id: str) -> Optional[DiscountRule]:
        return self._repo.find_by_id(rule_id)

    def create_rule(self, rule: DiscountRule) -> DiscountRule:
        cleaned = validate_discount_rule(rule)
        self._assert_seasonal_exclusivity(cleaned)
        return self._repo.save(cleaned)

    def update_rule(self, rule_id: str, **kwargs) -> DiscountRule:
        existing = self._repo.find_by_id(rule_id)
        if not existing:
            raise ValidationError("Discount rule not found")
        existing.update(**kwargs)
        cleaned = validate_discount_rule(existing)
        cleaned.id = rule_id
        cleaned.created_at = existing.created_at
        self._assert_seasonal_exclusivity(cleaned)
        return self._repo.save(cleaned)

    def delete_rule(self, rule_id: str) -> None:
        self._repo.delete(rule_id)

    def reorder_priorities(self, ordered_ids: Sequence[str]) -> List[DiscountRule]:
        """Assign priorities 10, 20, 30… in the given order (first = highest precedence)."""
        updated: List[DiscountRule] = []
        for index, rule_id in enumerate(ordered_ids):
            rule = self._repo.find_by_id(rule_id)
            if not rule:
                continue
            rule.priority = (index + 1) * 10
            rule.updated_at = utc_now()
            updated.append(self._repo.save(rule))
        return updated

    def move_priority(self, rule_id: str, *, direction: str) -> List[DiscountRule]:
        """Move a rule up (higher precedence) or down in the priority list."""
        rules = self._repo.list_all(active_only=False)
        ids = [r.id for r in rules]
        if rule_id not in ids:
            raise ValidationError("Discount rule not found")
        idx = ids.index(rule_id)
        if direction == "up" and idx > 0:
            ids[idx - 1], ids[idx] = ids[idx], ids[idx - 1]
        elif direction == "down" and idx < len(ids) - 1:
            ids[idx + 1], ids[idx] = ids[idx], ids[idx + 1]
        return self.reorder_priorities(ids)

    def _assert_seasonal_exclusivity(self, rule: DiscountRule) -> None:
        if rule.scope != SCOPE_SEASONAL or not rule.is_active:
            return
        others = self._repo.list_active_seasonal(exclude_id=rule.id)
        if others:
            names = ", ".join(r.name for r in others)
            raise ValidationError(
                f"Another seasonal campaign is already active ({names}). "
                "Deactivate it first."
            )

    def suggest_line_discount(
        self,
        *,
        qty: float,
        rate: float,
        product_id: str = "",
        category_ids: Optional[Sequence[str]] = None,
        customer_id: str = "",
        customer_segment_ids: Optional[Sequence[str]] = None,
        apply_to: str,
        on_date: Optional[date] = None,
        boutique: bool = False,
        rules: Optional[Sequence[DiscountRule]] = None,
    ) -> Optional[DiscountResult]:
        active_rules = list(rules) if rules is not None else self._repo.list_all(active_only=True)
        return resolve_line_discount(
            active_rules,
            qty=qty,
            rate=rate,
            product_id=product_id,
            category_ids=category_ids,
            customer_id=customer_id,
            customer_segment_ids=customer_segment_ids,
            apply_to=apply_to,
            on_date=on_date or date.today(),
            boutique=boutique,
        )

    def suggest_line_discounts(
        self,
        lines: Sequence[dict],
        *,
        customer_id: str = "",
        customer_segment_ids: Optional[Sequence[str]] = None,
        apply_to: str,
        on_date: Optional[date] = None,
        boutique: bool = False,
        qty_field: str = "qty",
    ) -> List[Optional[DiscountResult]]:
        rules = self._repo.list_all(active_only=True)
        return resolve_lines(
            rules,
            lines,
            customer_id=customer_id,
            customer_segment_ids=customer_segment_ids,
            apply_to=apply_to,
            on_date=on_date or date.today(),
            boutique=boutique,
            qty_field=qty_field,
        )
