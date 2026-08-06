"""Rule-based commission engine for agents and sales reps."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Sequence

from vaybooks.bms.domain.sales.commission_accrual import (
    CommissionAccrualCandidate,
    CommissionAccrualEntry,
    STATUS_ACCRUED,
    STATUS_REVERSED,
    candidate_to_entry,
)
from vaybooks.bms.domain.sales.commission_rules import (
    BASIS_COLLECTION,
    BASIS_SALES,
    COMMISSION_TYPE_FLAT,
    CONFLICT_MAXIMIZE,
    CONFLICT_MINIMIZE,
    CommissionProfile,
    CommissionRule,
    GRAIN_INVOICE,
    GRAIN_LINE,
    PARTY_AGENT,
    PARTY_SALES_REP,
    SCOPE_ALL,
    SCOPE_CUSTOMER,
    SCOPE_PRODUCT,
    SCOPE_PRODUCT_CATEGORY,
    compute_rule_amount,
    empty_commission_profile,
    period_key_for,
    rule_is_effective,
)


@dataclass
class InvoiceLineContext:
    product_id: str
    taxable_amount: float
    category_ids: List[str] = field(default_factory=list)
    qty: float = 0.0


@dataclass
class InvoiceCommissionContext:
    invoice_id: str
    customer_id: str
    invoice_date: date
    lines: List[InvoiceLineContext]
    taxable_total: float
    is_fully_paid: bool = False
    amount_collected_on_invoice: float = 0.0
    commission_agent_ids: List[str] = field(default_factory=list)
    sales_rep_ids: List[str] = field(default_factory=list)


@dataclass
class PartyCommissionSource:
    party_type: str
    party_id: str
    profile: CommissionProfile


class CommissionEngine:
    """Pure computation engine. Persistence / GL posting happen in the app service."""

    def __init__(
        self,
        *,
        threshold_base_lookup: Optional[
            Callable[[str, str, str, str], float]
        ] = None,
    ):
        """
        threshold_base_lookup(party_type, party_id, period_key, basis) -> prior base total
        """
        self._threshold_base_lookup = threshold_base_lookup or (
            lambda *_args: 0.0
        )

    def accrue_on_invoice(
        self,
        ctx: InvoiceCommissionContext,
        parties: Sequence[PartyCommissionSource],
        *,
        event_date: Optional[date] = None,
    ) -> List[CommissionAccrualCandidate]:
        event_date = event_date or ctx.invoice_date
        results: List[CommissionAccrualCandidate] = []
        for party in parties:
            profile = party.profile or empty_commission_profile()
            if not profile.include_unpaid and not ctx.is_fully_paid:
                # Paid-only: still allow sales rules when cash settles the invoice now.
                if ctx.amount_collected_on_invoice <= 0 and not ctx.is_fully_paid:
                    continue
            results.extend(
                self._run_for_party(
                    party=party,
                    profile=profile,
                    rules=list(profile.sales_rules or []),
                    basis=BASIS_SALES,
                    ctx=ctx,
                    base_total=ctx.taxable_total,
                    payment_amount=None,
                    payment_date=None,
                    receipt_id="",
                    event_date=event_date,
                    aging_days=None,
                )
            )
        return [c for c in results if c.amount > 0]

    def accrue_on_collection(
        self,
        ctx: InvoiceCommissionContext,
        parties: Sequence[PartyCommissionSource],
        *,
        payment_amount: float,
        payment_date: date,
        receipt_id: str = "",
    ) -> List[CommissionAccrualCandidate]:
        payment_amount = round(float(payment_amount or 0), 2)
        if payment_amount <= 0:
            return []
        aging_days = max((payment_date - ctx.invoice_date).days, 0)
        results: List[CommissionAccrualCandidate] = []
        for party in parties:
            profile = party.profile or empty_commission_profile()
            results.extend(
                self._run_for_party(
                    party=party,
                    profile=profile,
                    rules=list(profile.collection_rules or []),
                    basis=BASIS_COLLECTION,
                    ctx=ctx,
                    base_total=payment_amount,
                    payment_amount=payment_amount,
                    payment_date=payment_date,
                    receipt_id=receipt_id,
                    event_date=payment_date,
                    aging_days=aging_days,
                )
            )
        return [c for c in results if c.amount > 0]

    def reverse_for_return(
        self,
        existing: Sequence[CommissionAccrualEntry],
        *,
        return_ratio: float,
    ) -> List[CommissionAccrualCandidate]:
        """Build reversal candidates (negative amounts) proportional to return_ratio."""
        ratio = min(max(float(return_ratio or 0), 0.0), 1.0)
        if ratio <= 0:
            return []
        out: List[CommissionAccrualCandidate] = []
        for entry in existing:
            if entry.status != STATUS_ACCRUED:
                continue
            if entry.reversal_of_id:
                continue
            amount = round(float(entry.amount) * ratio, 2)
            if amount <= 0:
                continue
            out.append(
                CommissionAccrualCandidate(
                    party_type=entry.party_type,
                    party_id=entry.party_id,
                    basis=entry.basis,
                    rule_id=entry.rule_id,
                    source_invoice_id=entry.source_invoice_id,
                    source_receipt_id=entry.source_receipt_id,
                    line_product_id=entry.line_product_id,
                    customer_id=entry.customer_id,
                    base_amount=round(float(entry.base_amount) * ratio, 2),
                    rate=entry.rate,
                    amount=-amount,
                    aging_days=entry.aging_days,
                    period_key=entry.period_key,
                    event_date=entry.event_date,
                )
            )
        return out

    def _run_for_party(
        self,
        *,
        party: PartyCommissionSource,
        profile: CommissionProfile,
        rules: List[CommissionRule],
        basis: str,
        ctx: InvoiceCommissionContext,
        base_total: float,
        payment_amount: Optional[float],
        payment_date: Optional[date],
        receipt_id: str,
        event_date: date,
        aging_days: Optional[int],
    ) -> List[CommissionAccrualCandidate]:
        active_rules = [r for r in rules if rule_is_effective(r, event_date)]
        if not active_rules:
            return []

        period_key = period_key_for(event_date, profile.threshold_reset_period)
        threshold = (
            float(profile.min_sales_amount or 0)
            if basis == BASIS_SALES
            else float(profile.min_collection_amount or 0)
        )
        prior_base = float(
            self._threshold_base_lookup(
                party.party_type, party.party_id, period_key, basis
            )
            or 0
        )

        # Units to evaluate: invoice-level and/or per-line depending on matching rules.
        units = self._build_units(
            ctx=ctx,
            rules=active_rules,
            base_total=base_total,
            payment_amount=payment_amount,
        )
        candidates: List[CommissionAccrualCandidate] = []
        applied_base = 0.0

        for unit in units:
            unit_base = round(float(unit["base_amount"]), 2)
            if unit_base <= 0:
                continue
            matched = self._matching_rules(
                rules=active_rules,
                grain=unit["grain"],
                customer_id=ctx.customer_id,
                product_id=unit.get("product_id") or "",
                category_ids=list(unit.get("category_ids") or []),
            )
            if not matched:
                continue
            chosen = self._resolve_conflict(
                matched,
                base_amount=unit_base,
                aging_days=aging_days,
                strategy=profile.conflict_strategy,
            )
            if not chosen:
                continue
            rule, rate, amount = chosen
            # Threshold: only the portion of base above the remaining threshold earns.
            eligible_base = unit_base
            if threshold > 0:
                remaining = max(threshold - (prior_base + applied_base), 0.0)
                if remaining >= unit_base:
                    applied_base = round(applied_base + unit_base, 2)
                    continue
                if remaining > 0:
                    eligible_base = round(unit_base - remaining, 2)
                    if rule.commission_type == COMMISSION_TYPE_FLAT:
                        # Flat applies once only if any eligible base remains.
                        rate, amount = compute_rule_amount(
                            rule=rule,
                            base_amount=eligible_base,
                            days_overdue=aging_days,
                        )
                    else:
                        rate, amount = compute_rule_amount(
                            rule=rule,
                            base_amount=eligible_base,
                            days_overdue=aging_days,
                        )
            if amount <= 0:
                applied_base = round(applied_base + unit_base, 2)
                continue
            candidates.append(
                CommissionAccrualCandidate(
                    party_type=party.party_type,
                    party_id=party.party_id,
                    basis=basis,
                    rule_id=rule.id,
                    source_invoice_id=ctx.invoice_id,
                    source_receipt_id=receipt_id,
                    line_product_id=str(unit.get("product_id") or ""),
                    customer_id=ctx.customer_id,
                    base_amount=eligible_base,
                    rate=rate,
                    amount=amount,
                    aging_days=aging_days,
                    period_key=period_key,
                    event_date=event_date,
                )
            )
            applied_base = round(applied_base + unit_base, 2)
        return candidates

    def _build_units(
        self,
        *,
        ctx: InvoiceCommissionContext,
        rules: List[CommissionRule],
        base_total: float,
        payment_amount: Optional[float],
    ) -> List[dict]:
        wants_line = any(r.grain == GRAIN_LINE for r in rules)
        wants_invoice = any(r.grain == GRAIN_INVOICE for r in rules)
        units: List[dict] = []
        invoice_taxable = round(float(ctx.taxable_total or 0), 2)
        if wants_invoice:
            units.append(
                {
                    "grain": GRAIN_INVOICE,
                    "product_id": "",
                    "category_ids": [],
                    "base_amount": (
                        round(float(payment_amount), 2)
                        if payment_amount is not None
                        else base_total
                    ),
                }
            )
        if wants_line and ctx.lines:
            line_taxables = [
                round(float(line.taxable_amount or 0), 2) for line in ctx.lines
            ]
            line_sum = round(sum(line_taxables), 2)
            for line, line_taxable in zip(ctx.lines, line_taxables):
                if line_taxable <= 0:
                    continue
                if payment_amount is not None and invoice_taxable > 0:
                    share = line_taxable / invoice_taxable
                    line_base = round(float(payment_amount) * share, 2)
                elif payment_amount is not None and line_sum > 0:
                    share = line_taxable / line_sum
                    line_base = round(float(payment_amount) * share, 2)
                else:
                    line_base = line_taxable
                units.append(
                    {
                        "grain": GRAIN_LINE,
                        "product_id": line.product_id,
                        "category_ids": list(line.category_ids or []),
                        "base_amount": line_base,
                    }
                )
        elif wants_line and not ctx.lines:
            # Fallback: treat whole amount as one synthetic line.
            units.append(
                {
                    "grain": GRAIN_LINE,
                    "product_id": "",
                    "category_ids": [],
                    "base_amount": (
                        round(float(payment_amount), 2)
                        if payment_amount is not None
                        else base_total
                    ),
                }
            )
        return units

    def _matching_rules(
        self,
        *,
        rules: List[CommissionRule],
        grain: str,
        customer_id: str,
        product_id: str,
        category_ids: List[str],
    ) -> List[CommissionRule]:
        matched: List[CommissionRule] = []
        for rule in rules:
            if rule.grain != grain:
                continue
            scope = rule.scope_type
            ids = set(rule.scope_ids or [])
            if scope == SCOPE_ALL:
                matched.append(rule)
            elif scope == SCOPE_CUSTOMER and customer_id in ids:
                matched.append(rule)
            elif scope == SCOPE_PRODUCT and product_id and product_id in ids:
                matched.append(rule)
            elif scope == SCOPE_PRODUCT_CATEGORY and ids.intersection(
                set(category_ids or [])
            ):
                matched.append(rule)
        return matched

    def _resolve_conflict(
        self,
        rules: List[CommissionRule],
        *,
        base_amount: float,
        aging_days: Optional[int],
        strategy: str,
    ) -> Optional[tuple[CommissionRule, float, float]]:
        scored: List[tuple[CommissionRule, float, float]] = []
        for rule in rules:
            rate, amount = compute_rule_amount(
                rule=rule, base_amount=base_amount, days_overdue=aging_days
            )
            scored.append((rule, rate, amount))
        if not scored:
            return None
        strategy = (strategy or CONFLICT_MAXIMIZE).strip().lower()
        if strategy == CONFLICT_MINIMIZE:
            scored.sort(key=lambda t: (t[2], t[0].priority, t[0].id))
        else:
            scored.sort(key=lambda t: (-t[2], t[0].priority, t[0].id))
        return scored[0]


def build_parties_from_tags(
    *,
    agent_ids: Sequence[str],
    sales_rep_ids: Sequence[str],
    agent_profiles: Dict[str, CommissionProfile],
    sales_rep_profiles: Dict[str, CommissionProfile],
) -> List[PartyCommissionSource]:
    parties: List[PartyCommissionSource] = []
    for agent_id in agent_ids or []:
        aid = str(agent_id or "").strip()
        if not aid or aid not in agent_profiles:
            continue
        parties.append(
            PartyCommissionSource(
                party_type=PARTY_AGENT,
                party_id=aid,
                profile=agent_profiles[aid],
            )
        )
    for rep_id in sales_rep_ids or []:
        rid = str(rep_id or "").strip()
        if not rid or rid not in sales_rep_profiles:
            continue
        parties.append(
            PartyCommissionSource(
                party_type=PARTY_SALES_REP,
                party_id=rid,
                profile=sales_rep_profiles[rid],
            )
        )
    return parties


def persist_candidates(
    candidates: Sequence[CommissionAccrualCandidate],
) -> List[CommissionAccrualEntry]:
    entries: List[CommissionAccrualEntry] = []
    for candidate in candidates:
        entry = candidate_to_entry(candidate)
        if candidate.amount < 0:
            # Reversal entries: store absolute amount with reversed status linkage later.
            entry.amount = abs(float(candidate.amount))
            entry.status = STATUS_REVERSED
        entries.append(entry)
    return entries
