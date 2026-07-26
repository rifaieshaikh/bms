"""Stub scheduler services for the Schedulers page tests.

AppTest runs each page function in a fresh module namespace, so these builders
live in an importable module rather than the test file itself.
"""

from tests.application.test_scheduler_service import (
    RecordingJob,
    build_service,
    make_config,
)
from vaybooks.bms.application.schedulers.protocol import JobDefinition
from vaybooks.bms.application.schedulers.reports_protocol import (
    ReportDefinition,
    ReportRunResult,
)
from vaybooks.bms.application.schedulers.reports_registry import ReportRegistry
from vaybooks.bms.domain.schedulers.entities import DOMAIN_CRM


def job_service():
    definition = JobDefinition(
        job_id="crm.demo",
        domain=DOMAIN_CRM,
        title="Demo scheduler",
        description="Demo description",
        threshold_days=7,
        rule_fields=["threshold_days"],
    )
    job = RecordingJob(["a"])
    config = make_config("crm.demo", DOMAIN_CRM, title="Demo scheduler")
    config.description = "Demo description"
    return build_service(jobs=[(job, definition)], configs=[config]), job


def report_service():
    registry = ReportRegistry()
    registry.register(
        ReportDefinition(
            domain=DOMAIN_CRM,
            report_id="lead_funnel",
            title="Lead Funnel",
            category="Pipeline",
        ),
        lambda ctx: ReportRunResult(rows=[{"stage": "New", "count": 3}]),
    )
    return build_service(reports=registry)


def report_service_with_a_completed_run():
    service = report_service()
    config = service.get_report_config(DOMAIN_CRM, "lead_funnel")
    config.enabled = True
    service.save_report_config(config, actor_id="u1")
    service.run_report_now(DOMAIN_CRM, "lead_funnel", actor_id="u1")
    return service
