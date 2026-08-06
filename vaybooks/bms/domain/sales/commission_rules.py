"""Rule-based commission profiles for agents and sales reps."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.exceptions import ValidationError

SCOPE_ALL = "all"
SCOPE_CUSTOMER = "customer"
SCOPE_PRODUCT_CATEGORY = "product_category"
SCOPE_PRODUCT = "product"
_SCOPE_TYPES = {SCOPE_ALL, SCOPE_CUSTOMER, SCOPE_PRODUCT_CATEGORY, SCOPE_PRODUCT}

GRAIN_LINE = "line"
GRAIN_INVOICE = "invoice"
_GRAINS = {GRAIN_LINE, GRAIN_INVOICE}

COMMISSION_TYPE_PERCENTAGE = "percentage"
COMMISSION_TYPE_FLAT = "flat_per_invoice"
_COMMISSION_TYPES = {COMMISSION_TYPE_PERCENTAGE, COMMISSION_TYPE_FLAT}

CONFLICT_MAXIMIZE = "maximize"
CONFLICT_MINIMIZE = "minimize"
_CONFLICT_STRATEGIES = {CONFLICT_MAXIMIZE, CONFLICT_MINIMIZE}

THRESHOLD_MONTHLY = "monthly"
THRESHOLD_QUARTERLY = "quarterly"
THRESHOLD_YEARLY = "yearly"
_THRESHOLD_PERIODS = {THRESHOLD_MONTHLY, THRESHOLD_QUARTERLY, THRESHOLD_YEARLY}

PARTY_AGENT = "agent"
PARTY_SALES_REP = "sales_rep"
_PARTY_TYPES = {PARTY_AGENT, PARTY_SALES_REP}

BASIS_SALES = "sales"
BASIS_COLLECTION = "collection"


@dataclass
class AgingTier:
    max_days_overdue: Optional[int]  # None = beyond all other tiers
    commission_rate: float


@dataclass
class CommissionRule:
    id: str = field(default_factory=lambda: uuid4().hex)
    priority: int = 0
    scope_type: str = SCOPE_ALL
    scope_ids: List[str] = field(default_factory=list)
    grain: str = GRAIN_LINE
    commission_type: str = COMMISSION_TYPE_PERCENTAGE
    commission_rate: float = 0.0
    aging_tiers: List[AgingTier] = field(default_factory=list)
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    is_active: bool = True


@dataclass
class CommissionProfile:
    include_unpaid: bool = True
    min_sales_amount: float = 0.0
    min_collection_amount: float = 0.0
    threshold_reset_period: str = THRESHOLD_MONTHLY
    conflict_strategy: str = CONFLICT_MAXIMIZE
    sales_rules: List[CommissionRule] = field(default_factory=list)
    collection_rules: List[CommissionRule] = field(default_factory=list)


def empty_commission_profile() -> CommissionProfile:
    return CommissionProfile()


def _parse_date(value: Any) -> Optional[date]:
    from datetime import datetime

    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


def aging_tier_to_dict(tier: AgingTier) -> dict:
    return {
        "max_days_overdue": tier.max_days_overdue,
        "commission_rate": float(tier.commission_rate),
    }


def aging_tier_from_dict(raw: dict) -> AgingTier:
    max_days = raw.get("max_days_overdue")
    return AgingTier(
        max_days_overdue=None if max_days is None else int(max_days),
        commission_rate=float(raw.get("commission_rate") or 0),
    )


def rule_to_dict(rule: CommissionRule) -> dict:
    return {
        "id": rule.id,
        "priority": int(rule.priority),
        "scope_type": rule.scope_type,
        "scope_ids": list(rule.scope_ids or []),
        "grain": rule.grain,
        "commission_type": rule.commission_type,
        "commission_rate": float(rule.commission_rate or 0),
        "aging_tiers": [aging_tier_to_dict(t) for t in rule.aging_tiers or []],
        "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
        "valid_until": rule.valid_until.isoformat() if rule.valid_until else None,
        "is_active": bool(rule.is_active),
    }


def rule_from_dict(raw: Optional[dict]) -> CommissionRule:
    raw = raw or {}
    return CommissionRule(
        id=str(raw.get("id") or uuid4().hex),
        priority=int(raw.get("priority") or 0),
        scope_type=str(raw.get("scope_type") or SCOPE_ALL).strip().lower(),
        scope_ids=[str(i).strip() for i in (raw.get("scope_ids") or []) if str(i).strip()],
        grain=str(raw.get("grain") or GRAIN_LINE).strip().lower(),
        commission_type=str(
            raw.get("commission_type") or COMMISSION_TYPE_PERCENTAGE
        ).strip().lower(),
        commission_rate=float(raw.get("commission_rate") or 0),
        aging_tiers=[
            aging_tier_from_dict(t) for t in (raw.get("aging_tiers") or []) if isinstance(t, dict)
        ],
        valid_from=_parse_date(raw.get("valid_from")),
        valid_until=_parse_date(raw.get("valid_until")),
        is_active=bool(raw.get("is_active", True)),
    )


def profile_to_dict(profile: Optional[CommissionProfile]) -> dict:
    profile = profile or empty_commission_profile()
    return {
        "include_unpaid": bool(profile.include_unpaid),
        "min_sales_amount": float(profile.min_sales_amount or 0),
        "min_collection_amount": float(profile.min_collection_amount or 0),
        "threshold_reset_period": profile.threshold_reset_period,
        "conflict_strategy": profile.conflict_strategy,
        "sales_rules": [rule_to_dict(r) for r in profile.sales_rules or []],
        "collection_rules": [rule_to_dict(r) for r in profile.collection_rules or []],
    }


def profile_from_dict(raw: Optional[dict]) -> CommissionProfile:
    raw = raw or {}
    return CommissionProfile(
        include_unpaid=bool(raw.get("include_unpaid", True)),
        min_sales_amount=float(raw.get("min_sales_amount") or 0),
        min_collection_amount=float(raw.get("min_collection_amount") or 0),
        threshold_reset_period=str(
            raw.get("threshold_reset_period") or THRESHOLD_MONTHLY
        ).strip().lower(),
        conflict_strategy=str(
            raw.get("conflict_strategy") or CONFLICT_MAXIMIZE
        ).strip().lower(),
        sales_rules=[
            rule_from_dict(r) for r in (raw.get("sales_rules") or []) if isinstance(r, dict)
        ],
        collection_rules=[
            rule_from_dict(r)
            for r in (raw.get("collection_rules") or [])
            if isinstance(r, dict)
        ],
    )


def validate_aging_tiers(tiers: List[AgingTier]) -> List[AgingTier]:
    if not tiers:
        return []
    cleaned: List[AgingTier] = []
    for tier in tiers:
        rate = round(float(tier.commission_rate or 0), 4)
        if rate < 0 or rate > 100:
            raise ValidationError("Aging tier commission rate must be between 0 and 100")
        max_days = tier.max_days_overdue
        if max_days is not None:
            max_days = int(max_days)
            if max_days < 0:
                raise ValidationError("Aging tier days cannot be negative")
        cleaned.append(AgingTier(max_days_overdue=max_days, commission_rate=rate))
    bounded = [t for t in cleaned if t.max_days_overdue is not None]
    unbounded = [t for t in cleaned if t.max_days_overdue is None]
    if len(unbounded) > 1:
        raise ValidationError("Only one open-ended aging tier is allowed")
    bounded.sort(key=lambda t: int(t.max_days_overdue or 0))
    return bounded + unbounded


def validate_commission_rule(rule: CommissionRule) -> CommissionRule:
    scope_type = (rule.scope_type or SCOPE_ALL).strip().lower()
    if scope_type not in _SCOPE_TYPES:
        raise ValidationError(
            "Commission rule scope must be all, customer, product_category, or product"
        )
    grain = (rule.grain or GRAIN_LINE).strip().lower()
    if grain not in _GRAINS:
        raise ValidationError("Commission rule grain must be line or invoice")
    ctype = (rule.commission_type or COMMISSION_TYPE_PERCENTAGE).strip().lower()
    if ctype not in _COMMISSION_TYPES:
        raise ValidationError(
            "Commission type must be percentage or flat_per_invoice"
        )
    rate = round(float(rule.commission_rate or 0), 4)
    if rate < 0:
        raise ValidationError("Commission rate cannot be negative")
    if ctype == COMMISSION_TYPE_PERCENTAGE and rate > 100:
        raise ValidationError("Commission percentage cannot exceed 100")
    scope_ids = [str(i).strip() for i in (rule.scope_ids or []) if str(i).strip()]
    if scope_type != SCOPE_ALL and not scope_ids:
        raise ValidationError("Scoped commission rules require at least one scope id")
    if rule.valid_from and rule.valid_until and rule.valid_from > rule.valid_until:
        raise ValidationError("Commission rule valid_from cannot be after valid_until")
    return CommissionRule(
        id=str(rule.id or uuid4().hex),
        priority=int(rule.priority or 0),
        scope_type=scope_type,
        scope_ids=scope_ids,
        grain=grain,
        commission_type=ctype,
        commission_rate=rate,
        aging_tiers=validate_aging_tiers(list(rule.aging_tiers or [])),
        valid_from=rule.valid_from,
        valid_until=rule.valid_until,
        is_active=bool(rule.is_active),
    )


def validate_commission_profile(profile: Optional[CommissionProfile]) -> CommissionProfile:
    profile = profile or empty_commission_profile()
    period = (profile.threshold_reset_period or THRESHOLD_MONTHLY).strip().lower()
    if period not in _THRESHOLD_PERIODS:
        raise ValidationError(
            "Threshold reset period must be monthly, quarterly, or yearly"
        )
    strategy = (profile.conflict_strategy or CONFLICT_MAXIMIZE).strip().lower()
    if strategy not in _CONFLICT_STRATEGIES:
        raise ValidationError("Conflict strategy must be maximize or minimize")
    min_sales = round(float(profile.min_sales_amount or 0), 2)
    min_collection = round(float(profile.min_collection_amount or 0), 2)
    if min_sales < 0 or min_collection < 0:
        raise ValidationError("Commission thresholds cannot be negative")
    return CommissionProfile(
        include_unpaid=bool(profile.include_unpaid),
        min_sales_amount=min_sales,
        min_collection_amount=min_collection,
        threshold_reset_period=period,
        conflict_strategy=strategy,
        sales_rules=[validate_commission_rule(r) for r in profile.sales_rules or []],
        collection_rules=[
            validate_commission_rule(r) for r in profile.collection_rules or []
        ],
    )


def resolve_aging_rate(tiers: List[AgingTier], days_overdue: int) -> Optional[float]:
    """Return the tier rate for days_overdue, or None if no tiers configured."""
    if not tiers:
        return None
    days = max(int(days_overdue or 0), 0)
    for tier in tiers:
        if tier.max_days_overdue is None:
            return float(tier.commission_rate)
        if days <= int(tier.max_days_overdue):
            return float(tier.commission_rate)
    return float(tiers[-1].commission_rate)


def compute_rule_amount(
    *,
    rule: CommissionRule,
    base_amount: float,
    days_overdue: Optional[int] = None,
) -> tuple[float, float]:
    """Return (rate_used, commission_amount) for a single rule against a base."""
    base = round(float(base_amount or 0), 2)
    if base <= 0:
        return 0.0, 0.0
    rate = float(rule.commission_rate or 0)
    if rule.aging_tiers and days_overdue is not None:
        aged = resolve_aging_rate(rule.aging_tiers, days_overdue)
        if aged is not None:
            rate = aged
    if rule.commission_type == COMMISSION_TYPE_FLAT:
        amount = round(rate, 2)
    else:
        amount = round(base * rate / 100.0, 2)
    if amount < 0:
        amount = 0.0
    if amount > base:
        amount = base
    return rate, amount


def period_key_for(event_date: date, reset_period: str) -> str:
    """Build a period key used for threshold counters."""
    d = event_date
    period = (reset_period or THRESHOLD_MONTHLY).strip().lower()
    if period == THRESHOLD_YEARLY:
        return f"{d.year}"
    if period == THRESHOLD_QUARTERLY:
        q = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{q}"
    return f"{d.year:04d}-{d.month:02d}"


def rule_is_effective(rule: CommissionRule, on_date: date) -> bool:
    if not rule.is_active:
        return False
    if rule.valid_from and on_date < rule.valid_from:
        return False
    if rule.valid_until and on_date > rule.valid_until:
        return False
    return True
