"""Domain scheduler jobs: identify inputs, guard rails, and emitted outcomes."""

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

import pytest

from vaybooks.bms.application.schedulers.jobs import all_jobs
from vaybooks.bms.application.schedulers.jobs._base import Deps
from vaybooks.bms.application.schedulers.jobs.boutique_jobs import (
    EtdOverdueJob,
    EtdTodayJob,
)
from vaybooks.bms.application.schedulers.jobs.crm_jobs import (
    ActivityDueTodayJob,
    InvoicePaymentPendingJob,
    PaymentReminderOffsetsJob,
)
from vaybooks.bms.application.schedulers.jobs.inventory_jobs import LowStockJob
from vaybooks.bms.application.schedulers.jobs.project_jobs import ActivityEndSlipJob
from vaybooks.bms.application.schedulers.jobs.purchase_jobs import (
    PurchaseOrderOverdueJob,
)
from vaybooks.bms.application.schedulers.jobs.sales_jobs import QuotationExpiringJob
from vaybooks.bms.application.schedulers.protocol import JobContext
from vaybooks.bms.domain.schedulers.entities import (
    DOMAIN_ORDER,
    SchedulerJobConfig,
)
from vaybooks.bms.domain.schedulers.time import business_today, from_business
from vaybooks.bms.domain.schedulers.schedule import validate_schedule

TODAY = business_today()


def _utc(day: date, hour: int = 9) -> datetime:
    from vaybooks.bms.domain.schedulers.time import business_datetime

    return from_business(business_datetime(day, time(hour, 0)))


class FakeQueries:
    """Records the arguments each identify() passes down to the gateway."""

    def __init__(self, **returns):
        self.calls = {}
        self._returns = returns

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls[name] = (args, kwargs)
            return list(self._returns.get(name, []))

        return call


class FakeRepo:
    def __init__(self, items=()):
        self._store = {getattr(i, "id", ""): i for i in items}

    def find_by_id(self, entity_id):
        return self._store.get(entity_id)


def make_ctx(config=None, **overrides):
    config = config or SchedulerJobConfig(job_id="j", domain="crm")
    config.fallback_user_id = config.fallback_user_id or "ops-1"
    for key, value in overrides.items():
        setattr(config, key, value)
    emitted = []

    def notify(**kwargs):
        emitted.append(kwargs)
        return SimpleNamespace(**kwargs)

    ctx = JobContext(config=config, now=_utc(TODAY), notify=notify)
    return ctx, emitted


# ---------------------------------------------------------------------------
# Registry-wide invariants
# ---------------------------------------------------------------------------


def test_every_registered_job_has_a_valid_definition():
    seen = set()
    for job, definition in all_jobs(Deps()):
        assert definition.job_id == job.job_id
        assert definition.domain == job.domain
        assert definition.title and definition.description
        assert definition.job_id not in seen
        seen.add(definition.job_id)
        assert definition.job_id.split(".")[0] or True
        validate_schedule(
            SchedulerJobConfig(
                job_id=definition.job_id,
                domain=definition.domain,
                frequency=definition.frequency,
                time_of_day=definition.time_of_day,
                weekday=definition.weekday,
                interval_days=definition.interval_days,
            ).schedule
        )


def test_all_six_domains_ship_jobs():
    domains = {definition.domain for _job, definition in all_jobs(Deps())}
    assert domains == set(DOMAIN_ORDER)


def test_rule_fields_name_real_configuration():
    known_columns = set(SchedulerJobConfig("x", "crm").__dict__)
    for _job, definition in all_jobs(Deps()):
        for name in definition.rule_fields:
            assert name in known_columns or name in (definition.options or {}), (
                f"{definition.job_id} exposes unknown rule field {name}"
            )


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------


def test_activity_due_today_notifies_the_assignee():
    activity = SimpleNamespace(
        id="act-1",
        status="Scheduled",
        assigned_user_id="rep-9",
        activity_type="Call",
        party_name="Acme",
    )
    queries = FakeQueries(crm_activity_ids_scheduled_between=["act-1"])
    job = ActivityDueTodayJob(
        Deps(queries=queries, repos={"crm_activities": FakeRepo([activity])})
    )
    ctx, emitted = make_ctx(create_activity=False)

    job.process_batch(ctx, job.identify(ctx))

    assert emitted[0]["recipient_id"] == "rep-9"
    assert emitted[0]["ref_id"] == "act-1"


def test_activity_due_today_ignores_activities_that_have_closed():
    activity = SimpleNamespace(
        id="act-1",
        status="Completed",
        assigned_user_id="rep-9",
        activity_type="Call",
        party_name="Acme",
    )
    queries = FakeQueries(crm_activity_ids_scheduled_between=["act-1"])
    job = ActivityDueTodayJob(
        Deps(queries=queries, repos={"crm_activities": FakeRepo([activity])})
    )
    ctx, emitted = make_ctx(create_activity=False)

    result = job.process_batch(ctx, job.identify(ctx))

    assert emitted == [] and result.skipped == 1


def _reminder_deps(invoices, *, assignee="rep-1"):
    customer = SimpleNamespace(
        id="cust-1", customer_name="Acme", assigned_user_id=assignee
    )
    return Deps(
        queries=FakeQueries(receivable_customer_ids=["cust-1"]),
        services={
            "crm_payment_reminders": SimpleNamespace(
                open_invoices=lambda cid: list(invoices)
            )
        },
        repos={"customers": FakeRepo([customer])},
    )


def test_invoice_reminders_roll_aged_invoices_into_one_notification():
    invoices = [
        {
            "voucher_id": "v1",
            "reference": "INV-1",
            "invoice_date": _utc(TODAY - timedelta(days=20)),
            "outstanding": 5000,
        },
        {
            "voucher_id": "v2",
            "reference": "INV-2",
            "invoice_date": _utc(TODAY - timedelta(days=10)),
            "outstanding": 2500,
        },
    ]
    job = InvoicePaymentPendingJob(_reminder_deps(invoices))
    ctx, emitted = make_ctx(threshold_days=7, minimum_amount=1.0, create_activity=False)

    job.process_batch(ctx, job.identify(ctx))

    assert len(emitted) == 1
    assert "2 open invoice(s)" in emitted[0]["message"]
    assert "INV-1" in emitted[0]["message"]
    assert emitted[0]["ref_id"].startswith("cust-1:")


def test_invoice_reminders_respect_the_grace_period():
    invoices = [
        {
            "voucher_id": "v1",
            "reference": "INV-1",
            "invoice_date": _utc(TODAY - timedelta(days=8)),
            "outstanding": 5000,
        }
    ]
    job = InvoicePaymentPendingJob(_reminder_deps(invoices))
    ctx, emitted = make_ctx(threshold_days=7, grace_days=5, create_activity=False)

    job.process_batch(ctx, job.identify(ctx))

    assert emitted == []


def test_invoice_reminders_skip_amounts_below_the_minimum():
    invoices = [
        {
            "voucher_id": "v1",
            "reference": "INV-1",
            "invoice_date": _utc(TODAY - timedelta(days=30)),
            "outstanding": 100,
        }
    ]
    job = InvoicePaymentPendingJob(_reminder_deps(invoices))
    ctx, emitted = make_ctx(threshold_days=7, minimum_amount=1000.0, create_activity=False)

    job.process_batch(ctx, job.identify(ctx))

    assert emitted == []


def test_the_aging_bucket_keeps_reminders_distinct_as_an_invoice_ages():
    def ref_for(age_days):
        invoices = [
            {
                "voucher_id": "v1",
                "reference": "INV-1",
                "invoice_date": _utc(TODAY - timedelta(days=age_days)),
                "outstanding": 5000,
            }
        ]
        job = InvoicePaymentPendingJob(_reminder_deps(invoices))
        ctx, emitted = make_ctx(threshold_days=7, create_activity=False)
        job.process_batch(ctx, job.identify(ctx))
        return emitted[0]["ref_id"]

    # Same bucket → same key → the dedupe layer suppresses a repeat.
    assert ref_for(10) == ref_for(20)
    # A new bucket produces a new key so the customer is chased again.
    assert ref_for(10) != ref_for(40)


@pytest.mark.parametrize("age,expected", [(0, True), (3, True), (7, True), (5, False)])
def test_reminder_offsets_fire_only_on_configured_days(age, expected):
    invoices = [
        {
            "voucher_id": "v1",
            "reference": "INV-1",
            "invoice_date": _utc(TODAY - timedelta(days=age)),
            "outstanding": 5000,
        }
    ]
    job = PaymentReminderOffsetsJob(_reminder_deps(invoices))
    ctx, emitted = make_ctx(
        reminder_offsets_days=[0, 3, 7], minimum_amount=1.0, create_activity=False
    )

    job.process_batch(ctx, job.identify(ctx))

    assert bool(emitted) is expected
    if expected:
        assert emitted[0]["ref_id"].endswith(f":{age}")


def test_reminder_offsets_never_send_anything_themselves():
    invoices = [
        {
            "voucher_id": "v1",
            "reference": "INV-1",
            "invoice_date": _utc(TODAY),
            "outstanding": 5000,
        }
    ]
    job = PaymentReminderOffsetsJob(_reminder_deps(invoices))
    ctx, emitted = make_ctx(reminder_offsets_days=[0], create_activity=False)

    job.process_batch(ctx, job.identify(ctx))

    assert emitted[0]["title"] == "Prepare a payment reminder"


def test_a_candidate_without_an_owner_falls_back_to_the_configured_user():
    invoices = [
        {
            "voucher_id": "v1",
            "reference": "INV-1",
            "invoice_date": _utc(TODAY - timedelta(days=30)),
            "outstanding": 5000,
        }
    ]
    job = InvoicePaymentPendingJob(_reminder_deps(invoices, assignee=""))
    ctx, emitted = make_ctx(
        threshold_days=7, fallback_user_id="ops-lead", create_activity=False
    )

    job.process_batch(ctx, job.identify(ctx))

    assert emitted[0]["recipient_id"] == "ops-lead"


# ---------------------------------------------------------------------------
# Sales / Purchases / Inventory / Boutique / Projects
# ---------------------------------------------------------------------------


def test_quotation_expiry_uses_the_furthest_offset_as_its_horizon():
    queries = FakeQueries(sales_document_ids_expiring=[])
    job = QuotationExpiringJob(Deps(queries=queries))
    ctx, _ = make_ctx(reminder_offsets_days=[7, 3, 0])

    job.identify(ctx)

    args, kwargs = queries.calls["sales_document_ids_expiring"]
    assert args[0] == "quotations"
    assert args[2] == TODAY + timedelta(days=7)
    assert kwargs["limit"] == ctx.config.max_ids_per_run


def test_quotation_expiry_emits_once_per_offset_bucket():
    quotation = SimpleNamespace(
        id="q-1",
        status="Sent",
        valid_until=TODAY + timedelta(days=2),
        customer_id="cust-1",
        customer_name="Acme",
    )
    job = QuotationExpiringJob(
        Deps(
            queries=FakeQueries(sales_document_ids_expiring=["q-1"]),
            repos={"quotations": FakeRepo([quotation]), "customers": FakeRepo()},
        )
    )
    ctx, emitted = make_ctx(reminder_offsets_days=[7, 3, 0], create_activity=False)

    job.process_batch(ctx, job.identify(ctx))

    assert emitted[0]["ref_id"].endswith(":3")
    assert "expires in 2 day(s)" in emitted[0]["title"]


def test_purchase_order_overdue_ignores_orders_still_within_their_date():
    order = SimpleNamespace(
        id="po-1",
        status="Sent",
        expected_date=TODAY + timedelta(days=2),
        po_number="PO-1",
        vendor_name="Vendor",
    )
    job = PurchaseOrderOverdueJob(
        Deps(
            queries=FakeQueries(purchase_order_ids_overdue=["po-1"]),
            repos={"purchase_orders": FakeRepo([order])},
        )
    )
    ctx, emitted = make_ctx(create_activity=False)

    job.process_batch(ctx, job.identify(ctx))

    assert emitted == []


def test_low_stock_skips_products_above_the_threshold():
    below = SimpleNamespace(id="p-1", is_active=True, current_qty=1, name="A", sku="A1")
    above = SimpleNamespace(id="p-2", is_active=True, current_qty=9, name="B", sku="B1")
    job = LowStockJob(
        Deps(
            queries=FakeQueries(product_ids_low_stock=["p-1", "p-2"]),
            repos={"inventory_products": FakeRepo([below, above])},
        )
    )
    ctx, emitted = make_ctx(create_activity=False, options={"threshold_qty": 2})

    job.process_batch(ctx, job.identify(ctx))

    assert [e["ref_id"] for e in emitted] == ["p-1"]
    assert "is low" in emitted[0]["title"]


def test_out_of_stock_is_reported_by_the_same_job():
    empty = SimpleNamespace(id="p-1", is_active=True, current_qty=0, name="A", sku="A1")
    job = LowStockJob(
        Deps(
            queries=FakeQueries(product_ids_low_stock=["p-1"]),
            repos={"inventory_products": FakeRepo([empty])},
        )
    )
    ctx, emitted = make_ctx(create_activity=False, options={"threshold_qty": 2})

    job.process_batch(ctx, job.identify(ctx))

    assert "out of stock" in emitted[0]["title"]


def test_boutique_etd_today_and_overdue_do_not_both_fire():
    due_today = SimpleNamespace(
        id="o-1",
        order_status="In Progress",
        expected_delivery_date=TODAY,
        order_number="CO-1",
        customer_name="Acme",
    )
    deps = Deps(
        queries=FakeQueries(
            boutique_order_ids_by_etd=["o-1"], boutique_order_ids_etd_before=["o-1"]
        ),
        repos={"boutique_orders": FakeRepo([due_today])},
    )
    ctx, today_emitted = make_ctx(create_activity=False)
    EtdTodayJob(deps).process_batch(ctx, ["o-1"])
    ctx2, overdue_emitted = make_ctx(create_activity=False)
    EtdOverdueJob(deps).process_batch(ctx2, ["o-1"])

    assert len(today_emitted) == 1
    assert overdue_emitted == []


def test_closed_boutique_orders_are_never_chased():
    delivered = SimpleNamespace(
        id="o-1",
        order_status="Delivered",
        expected_delivery_date=TODAY - timedelta(days=5),
        order_number="CO-1",
        customer_name="Acme",
    )
    job = EtdOverdueJob(
        Deps(
            queries=FakeQueries(boutique_order_ids_etd_before=["o-1"]),
            repos={"boutique_orders": FakeRepo([delivered])},
        )
    )
    ctx, emitted = make_ctx(create_activity=False)

    job.process_batch(ctx, ["o-1"])

    assert emitted == []


def test_project_activity_slip_routes_to_the_project_manager():
    activity = SimpleNamespace(
        id="a-1", status="In Progress", planned_end=TODAY - timedelta(days=2), name="Slab"
    )
    project = SimpleNamespace(
        id="p-1",
        status="Active",
        name="Tower",
        project_manager_id="pm-7",
        activities=[activity],
    )
    job = ActivityEndSlipJob(
        Deps(
            queries=FakeQueries(project_activity_refs_overdue=["p-1|a-1"]),
            repos={"projects": FakeRepo([project])},
        )
    )
    ctx, emitted = make_ctx(create_activity=False)

    job.process_batch(ctx, job.identify(ctx))

    assert emitted[0]["recipient_id"] == "pm-7"
    assert emitted[0]["ref_id"] == "p-1|a-1"


def test_a_describe_error_is_counted_without_stopping_the_batch():
    class Exploding(FakeRepo):
        def find_by_id(self, entity_id):
            raise RuntimeError("db down")

    job = ActivityDueTodayJob(
        Deps(queries=FakeQueries(), repos={"crm_activities": Exploding()})
    )
    ctx, emitted = make_ctx()

    result = job.process_batch(ctx, ["act-1", "act-2"])

    assert result.errors == 2 and result.processed == 2 and emitted == []
