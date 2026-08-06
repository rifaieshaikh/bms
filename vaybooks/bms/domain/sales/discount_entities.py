"""Configurable discount rules for sales orders, invoices, and boutique invoices."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError

SCOPE_PRODUCT = "product"
SCOPE_CATEGORY = "category"
SCOPE_CUSTOMER = "customer"
SCOPE_SEASONAL = "seasonal"
SCOPE_GLOBAL = "global"
VALID_SCOPES = frozenset(
    {
        SCOPE_PRODUCT,
        SCOPE_CATEGORY,
        SCOPE_CUSTOMER,
        SCOPE_SEASONAL,
        SCOPE_GLOBAL,
    }
)

# Specificity rank for tie-break when priorities are equal (higher = more specific).
SCOPE_SPECIFICITY = {
    SCOPE_CUSTOMER: 50,
    SCOPE_PRODUCT: 40,
    SCOPE_CATEGORY: 30,
    SCOPE_SEASONAL: 20,
    SCOPE_GLOBAL: 10,
}

DISCOUNT_TYPE_PERCENT = "percent"
DISCOUNT_TYPE_FIXED = "fixed"
VALID_DISCOUNT_TYPES = frozenset({DISCOUNT_TYPE_PERCENT, DISCOUNT_TYPE_FIXED})

APPLY_SALES_ORDER = "sales_order"
APPLY_SALES_INVOICE = "sales_invoice"
APPLY_BOUTIQUE_INVOICE = "boutique_invoice"
VALID_APPLY_TO = frozenset(
    {APPLY_SALES_ORDER, APPLY_SALES_INVOICE, APPLY_BOUTIQUE_INVOICE}
)

# Boutique bill items have no product/category FK — only these scopes apply.
BOUTIQUE_SCOPES = frozenset({SCOPE_CUSTOMER, SCOPE_SEASONAL, SCOPE_GLOBAL})

DEFAULT_APPLY_TO = [
    APPLY_SALES_ORDER,
    APPLY_SALES_INVOICE,
    APPLY_BOUTIQUE_INVOICE,
]

SCOPE_LABELS = {
    SCOPE_PRODUCT: "Product",
    SCOPE_CATEGORY: "Category",
    SCOPE_CUSTOMER: "Customer",
    SCOPE_SEASONAL: "Seasonal",
    SCOPE_GLOBAL: "Global",
}


@dataclass
class DiscountRule:
    name: str
    scope: str = SCOPE_GLOBAL
    discount_type: str = DISCOUNT_TYPE_PERCENT
    value: float = 0.0
    priority: int = 100
    is_active: bool = True
    product_ids: List[str] = field(default_factory=list)
    category_ids: List[str] = field(default_factory=list)
    customer_ids: List[str] = field(default_factory=list)
    segment_ids: List[str] = field(default_factory=list)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    apply_to: List[str] = field(default_factory=lambda: list(DEFAULT_APPLY_TO))
    max_discount_amount: Optional[float] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


@dataclass
class DiscountResult:
    rule_id: str
    rule_name: str
    amount: float
    scope: str = ""


def _clean_ids(values: Optional[List[str]]) -> List[str]:
    return [str(v).strip() for v in (values or []) if str(v).strip()]


def validate_discount_rule(rule: DiscountRule) -> DiscountRule:
    name = (rule.name or "").strip()
    if not name:
        raise ValidationError("Discount rule name is required")

    scope = (rule.scope or "").strip().lower()
    if scope not in VALID_SCOPES:
        raise ValidationError(
            "Discount scope must be product, category, customer, seasonal, or global"
        )

    discount_type = (rule.discount_type or "").strip().lower()
    if discount_type not in VALID_DISCOUNT_TYPES:
        raise ValidationError("Discount type must be percent or fixed")

    value = round(float(rule.value or 0), 4)
    if value < 0:
        raise ValidationError("Discount value cannot be negative")
    if discount_type == DISCOUNT_TYPE_PERCENT and value > 100:
        raise ValidationError("Discount percentage cannot exceed 100")

    product_ids = _clean_ids(rule.product_ids)
    category_ids = _clean_ids(rule.category_ids)
    customer_ids = _clean_ids(rule.customer_ids)
    segment_ids = _clean_ids(rule.segment_ids)

    if scope == SCOPE_PRODUCT and not product_ids:
        raise ValidationError("Product discount rules require at least one product")
    if scope == SCOPE_CATEGORY and not category_ids:
        raise ValidationError("Category discount rules require at least one category")
    if scope == SCOPE_CUSTOMER and not customer_ids and not segment_ids:
        raise ValidationError(
            "Customer discount rules require at least one customer or segment"
        )
    if scope == SCOPE_SEASONAL:
        if not rule.valid_from or not rule.valid_to:
            raise ValidationError("Seasonal discounts require valid_from and valid_to")

    if rule.valid_from and rule.valid_to and rule.valid_from > rule.valid_to:
        raise ValidationError("valid_from cannot be after valid_to")

    apply_to = [
        a.strip().lower()
        for a in (rule.apply_to or [])
        if str(a).strip().lower() in VALID_APPLY_TO
    ]
    if not apply_to:
        apply_to = list(DEFAULT_APPLY_TO)

    max_amount = rule.max_discount_amount
    if max_amount is not None:
        max_amount = round(float(max_amount), 2)
        if max_amount < 0:
            raise ValidationError("Max discount amount cannot be negative")

    return DiscountRule(
        id=str(rule.id or uuid4().hex),
        name=name,
        scope=scope,
        discount_type=discount_type,
        value=value,
        priority=int(rule.priority if rule.priority is not None else 100),
        is_active=bool(rule.is_active),
        product_ids=product_ids,
        category_ids=category_ids,
        customer_ids=customer_ids,
        segment_ids=segment_ids,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        apply_to=apply_to,
        max_discount_amount=max_amount,
        created_at=rule.created_at or utc_now(),
        updated_at=utc_now(),
    )
