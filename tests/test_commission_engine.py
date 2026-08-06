"""Unit tests for rule-based commission engine (sales + collection)."""

from datetime import date

from vaybooks.bms.application.sales.commission_engine import (
    CommissionEngine,
    InvoiceCommissionContext,
    InvoiceLineContext,
    PartyCommissionSource,
)
from vaybooks.bms.domain.sales.commission_rules import (
    AgingTier,
    COMMISSION_TYPE_PERCENTAGE,
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
)


def _ctx(**kwargs):
    defaults = dict(
        invoice_id="inv1",
        customer_id="cust1",
        invoice_date=date(2026, 1, 1),
        lines=[
            InvoiceLineContext(
                product_id="p1",
                taxable_amount=1000.0,
                category_ids=["cat_a"],
            ),
            InvoiceLineContext(
                product_id="p2",
                taxable_amount=500.0,
                category_ids=["cat_b"],
            ),
        ],
        taxable_total=1500.0,
        is_fully_paid=True,
        commission_agent_ids=["agent1"],
        sales_rep_ids=[],
    )
    defaults.update(kwargs)
    return InvoiceCommissionContext(**defaults)


def test_sales_rules_only_fire_on_invoice():
    profile = CommissionProfile(
        sales_rules=[
            CommissionRule(
                scope_type=SCOPE_ALL,
                grain=GRAIN_INVOICE,
                commission_type=COMMISSION_TYPE_PERCENTAGE,
                commission_rate=10,
            )
        ],
        collection_rules=[
            CommissionRule(
                scope_type=SCOPE_ALL,
                grain=GRAIN_INVOICE,
                commission_type=COMMISSION_TYPE_PERCENTAGE,
                commission_rate=5,
            )
        ],
    )
    party = PartyCommissionSource(PARTY_AGENT, "agent1", profile)
    engine = CommissionEngine()
    sales = engine.accrue_on_invoice(_ctx(), [party])
    assert len(sales) == 1
    assert sales[0].basis == "sales"
    assert sales[0].amount == 150.0

    collection = engine.accrue_on_collection(
        _ctx(),
        [party],
        payment_amount=1500.0,
        payment_date=date(2026, 1, 15),
        receipt_id="r1",
    )
    assert len(collection) == 1
    assert collection[0].basis == "collection"
    assert collection[0].amount == 75.0


def test_line_grain_product_and_category_scope():
    profile = CommissionProfile(
        sales_rules=[
            CommissionRule(
                id="r_prod",
                priority=1,
                scope_type=SCOPE_PRODUCT,
                scope_ids=["p1"],
                grain=GRAIN_LINE,
                commission_rate=10,
            ),
            CommissionRule(
                id="r_cat",
                priority=2,
                scope_type=SCOPE_PRODUCT_CATEGORY,
                scope_ids=["cat_b"],
                grain=GRAIN_LINE,
                commission_rate=4,
            ),
        ]
    )
    party = PartyCommissionSource(PARTY_AGENT, "agent1", profile)
    engine = CommissionEngine()
    results = engine.accrue_on_invoice(_ctx(), [party])
    by_product = {r.line_product_id: r.amount for r in results}
    assert by_product["p1"] == 100.0
    assert by_product["p2"] == 20.0


def test_maximize_vs_minimize_conflict():
    rules = [
        CommissionRule(
            id="low",
            priority=1,
            scope_type=SCOPE_ALL,
            grain=GRAIN_INVOICE,
            commission_rate=2,
        ),
        CommissionRule(
            id="high",
            priority=2,
            scope_type=SCOPE_CUSTOMER,
            scope_ids=["cust1"],
            grain=GRAIN_INVOICE,
            commission_rate=8,
        ),
    ]
    max_profile = CommissionProfile(
        conflict_strategy=CONFLICT_MAXIMIZE, sales_rules=rules
    )
    min_profile = CommissionProfile(
        conflict_strategy=CONFLICT_MINIMIZE, sales_rules=rules
    )
    engine = CommissionEngine()
    max_amt = engine.accrue_on_invoice(
        _ctx(), [PartyCommissionSource(PARTY_AGENT, "a", max_profile)]
    )[0].amount
    min_amt = engine.accrue_on_invoice(
        _ctx(), [PartyCommissionSource(PARTY_AGENT, "a", min_profile)]
    )[0].amount
    assert max_amt == 120.0
    assert min_amt == 30.0


def test_threshold_gates_until_crossed():
    profile = CommissionProfile(
        min_sales_amount=1000.0,
        sales_rules=[
            CommissionRule(
                scope_type=SCOPE_ALL,
                grain=GRAIN_INVOICE,
                commission_rate=10,
            )
        ],
    )
    party = PartyCommissionSource(PARTY_AGENT, "agent1", profile)
    engine = CommissionEngine(threshold_base_lookup=lambda *_: 0.0)
    # First invoice 800 — entirely below threshold → no commission
    first = engine.accrue_on_invoice(
        _ctx(taxable_total=800.0, lines=[]), [party]
    )
    assert first == []

    # With prior base 800, new 500 → only 300 eligible above remaining 200 threshold
    engine2 = CommissionEngine(threshold_base_lookup=lambda *_: 800.0)
    second = engine2.accrue_on_invoice(
        _ctx(taxable_total=500.0, lines=[]), [party]
    )
    assert len(second) == 1
    assert second[0].base_amount == 300.0
    assert second[0].amount == 30.0


def test_aging_tiers_on_collection():
    profile = CommissionProfile(
        collection_rules=[
            CommissionRule(
                scope_type=SCOPE_ALL,
                grain=GRAIN_INVOICE,
                commission_rate=10,
                aging_tiers=[
                    AgingTier(max_days_overdue=30, commission_rate=5),
                    AgingTier(max_days_overdue=60, commission_rate=2),
                    AgingTier(max_days_overdue=None, commission_rate=0),
                ],
            )
        ]
    )
    party = PartyCommissionSource(PARTY_AGENT, "agent1", profile)
    engine = CommissionEngine()
    early = engine.accrue_on_collection(
        _ctx(),
        [party],
        payment_amount=1000.0,
        payment_date=date(2026, 1, 20),
    )
    assert early[0].rate == 5.0
    assert early[0].amount == 50.0
    assert early[0].aging_days == 19

    late = engine.accrue_on_collection(
        _ctx(),
        [party],
        payment_amount=1000.0,
        payment_date=date(2026, 4, 1),
    )
    # Zero-rate aging tiers produce no accrual candidates.
    assert late == []


def test_multi_agent_and_sales_rep_independent():
    agent_profile = CommissionProfile(
        sales_rules=[
            CommissionRule(
                scope_type=SCOPE_ALL, grain=GRAIN_INVOICE, commission_rate=10
            )
        ]
    )
    rep_profile = CommissionProfile(
        sales_rules=[
            CommissionRule(
                scope_type=SCOPE_ALL, grain=GRAIN_INVOICE, commission_rate=5
            )
        ]
    )
    engine = CommissionEngine()
    results = engine.accrue_on_invoice(
        _ctx(sales_rep_ids=["rep1"]),
        [
            PartyCommissionSource(PARTY_AGENT, "agent1", agent_profile),
            PartyCommissionSource(PARTY_SALES_REP, "rep1", rep_profile),
        ],
    )
    assert len(results) == 2
    by_party = {(r.party_type, r.party_id): r.amount for r in results}
    assert by_party[(PARTY_AGENT, "agent1")] == 150.0
    assert by_party[(PARTY_SALES_REP, "rep1")] == 75.0


def test_collection_line_split_proportional():
    profile = CommissionProfile(
        collection_rules=[
            CommissionRule(
                scope_type=SCOPE_PRODUCT,
                scope_ids=["p1"],
                grain=GRAIN_LINE,
                commission_rate=10,
            )
        ]
    )
    party = PartyCommissionSource(PARTY_AGENT, "agent1", profile)
    engine = CommissionEngine()
    # Pay 750 of 1500 → p1 share = 1000/1500 * 750 = 500 → commission 50
    results = engine.accrue_on_collection(
        _ctx(),
        [party],
        payment_amount=750.0,
        payment_date=date(2026, 1, 10),
    )
    assert len(results) == 1
    assert results[0].line_product_id == "p1"
    assert results[0].base_amount == 500.0
    assert results[0].amount == 50.0


def test_reverse_for_return_proportional():
    from vaybooks.bms.domain.sales.commission_accrual import (
        STATUS_ACCRUED,
        CommissionAccrualEntry,
    )

    existing = [
        CommissionAccrualEntry(
            party_type=PARTY_AGENT,
            party_id="agent1",
            basis="sales",
            rule_id="r1",
            source_invoice_id="inv1",
            base_amount=1500.0,
            rate=10.0,
            amount=150.0,
            period_key="2026-01",
            status=STATUS_ACCRUED,
        )
    ]
    engine = CommissionEngine()
    half = engine.reverse_for_return(existing, return_ratio=0.5)
    assert len(half) == 1
    assert half[0].amount == -75.0
    assert half[0].base_amount == 750.0


def test_include_unpaid_false_skips_unpaid_invoice():
    profile = CommissionProfile(
        include_unpaid=False,
        sales_rules=[
            CommissionRule(
                scope_type=SCOPE_ALL, grain=GRAIN_INVOICE, commission_rate=10
            )
        ],
    )
    party = PartyCommissionSource(PARTY_AGENT, "agent1", profile)
    engine = CommissionEngine()
    skipped = engine.accrue_on_invoice(
        _ctx(is_fully_paid=False, amount_collected_on_invoice=0), [party]
    )
    assert skipped == []
    allowed = engine.accrue_on_invoice(
        _ctx(is_fully_paid=True), [party]
    )
    assert len(allowed) == 1
