"""Schedulers (Settings) and domain Scheduled reports UI smoke tests."""

import pytest

SCHEDULER_PAGES = [
    "vaybooks.bms.ui.pages.schedulers.crm",
    "vaybooks.bms.ui.pages.schedulers.sales",
    "vaybooks.bms.ui.pages.schedulers.purchases",
    "vaybooks.bms.ui.pages.schedulers.inventory",
    "vaybooks.bms.ui.pages.schedulers.boutique",
    "vaybooks.bms.ui.pages.schedulers.projects",
]

PAGE_TITLES = {
    "vaybooks.bms.ui.pages.schedulers.crm": "CRM Schedulers",
    "vaybooks.bms.ui.pages.schedulers.sales": "Sales Schedulers",
    "vaybooks.bms.ui.pages.schedulers.purchases": "Purchases Schedulers",
    "vaybooks.bms.ui.pages.schedulers.inventory": "Inventory Schedulers",
    "vaybooks.bms.ui.pages.schedulers.boutique": "Boutique Schedulers",
    "vaybooks.bms.ui.pages.schedulers.projects": "Projects Schedulers",
}

SCHEDULED_REPORT_PAGES = [
    "vaybooks.bms.ui.pages.crm.scheduled_reports",
    "vaybooks.bms.ui.pages.sales.scheduled_reports",
    "vaybooks.bms.ui.pages.purchases.scheduled_reports",
    "vaybooks.bms.ui.pages.inventory.scheduled_reports",
    "vaybooks.bms.ui.pages.boutique.scheduled_reports",
    "vaybooks.bms.ui.pages.projects.scheduled_reports",
]

SCHEDULED_REPORT_TITLES = {
    "vaybooks.bms.ui.pages.crm.scheduled_reports": "CRM Scheduled reports",
    "vaybooks.bms.ui.pages.sales.scheduled_reports": "Sales Scheduled reports",
    "vaybooks.bms.ui.pages.purchases.scheduled_reports": "Purchases Scheduled reports",
    "vaybooks.bms.ui.pages.inventory.scheduled_reports": "Inventory Scheduled reports",
    "vaybooks.bms.ui.pages.boutique.scheduled_reports": "Boutique Scheduled reports",
    "vaybooks.bms.ui.pages.projects.scheduled_reports": "Projects Scheduled reports",
}


def _text(at) -> str:
    return " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown")
        + at.get("header")
        + at.get("title")
        + at.get("subheader")
        + at.get("caption")
        + at.get("info")
        + at.get("warning")
        + at.get("error")
    )


def _empty_page(path):
    import importlib

    importlib.import_module(path).render({})


def _jobs_page():
    import streamlit as st

    from tests.ui.scheduler_page_fixtures import job_service
    from vaybooks.bms.ui.pages.schedulers import crm

    if "svc" not in st.session_state:
        st.session_state["svc"], st.session_state["job"] = job_service()
    crm.render({"schedulers": st.session_state["svc"]})
    st.session_state["batches"] = list(st.session_state["job"].batches)


def _viewer_page():
    from tests.ui.scheduler_page_fixtures import job_service
    from vaybooks.bms.ui.pages.schedulers import crm

    service, _job = job_service()
    crm.render({"schedulers": service})


def _reports_page():
    from tests.ui.scheduler_page_fixtures import report_service
    from vaybooks.bms.ui.pages.crm import scheduled_reports

    scheduled_reports.render({"schedulers": report_service()})


def _reports_page_with_history():
    import streamlit as st

    from tests.ui.scheduler_page_fixtures import report_service_with_a_completed_run
    from vaybooks.bms.ui.pages.crm import scheduled_reports

    if "svc" not in st.session_state:
        st.session_state["svc"] = report_service_with_a_completed_run()
    scheduled_reports.render({"schedulers": st.session_state["svc"]})


def _run(fn, *args):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(fn, args=args)
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


@pytest.mark.parametrize("module_path", SCHEDULER_PAGES)
def test_scheduler_pages_render_an_empty_state_without_the_service(module_path):
    at = _run(_empty_page, module_path)
    body = _text(at)
    assert PAGE_TITLES[module_path] in body
    assert "scheduler service is not available" in body


@pytest.mark.parametrize("module_path", SCHEDULED_REPORT_PAGES)
def test_scheduled_report_pages_render_an_empty_state_without_the_service(module_path):
    at = _run(_empty_page, module_path)
    body = _text(at)
    assert SCHEDULED_REPORT_TITLES[module_path] in body
    assert "scheduler service is not available" in body


def test_the_jobs_section_shows_the_schedule_in_plain_language():
    at = _run(_jobs_page)
    body = _text(at)
    assert "Demo scheduler" in at.get("selectbox")[0].options
    assert "Runs every day at 6:00 am" in body
    assert "cron" not in body.lower()


def test_the_schedule_editor_offers_frequencies_not_cron_fields():
    at = _run(_jobs_page)
    how_often = next(box for box in at.get("selectbox") if box.label == "How often")
    assert how_often.options == [
        "Daily",
        "Weekdays (Mon-Fri)",
        "Weekly",
        "Every N days",
    ]


def test_the_job_editor_exposes_every_manual_trigger():
    at = _run(_jobs_page)
    labels = [b.label for b in at.get("button")]
    assert "Run now" in labels
    assert "Dry run" in labels
    assert "Run all in this domain" in labels
    assert "Run all schedulers" in labels


def test_pressing_run_now_executes_the_job():
    at = _run(_jobs_page)
    run_now = next(b for b in at.get("button") if b.label == "Run now")
    run_now.click().run(timeout=60)

    assert not at.exception
    assert at.session_state["batches"] == [["a"]]


def test_a_dry_run_leaves_the_job_untouched():
    at = _run(_jobs_page)
    dry_run = next(b for b in at.get("button") if b.label == "Dry run")
    dry_run.click().run(timeout=60)

    assert not at.exception
    assert at.session_state["batches"] == []


def test_rule_and_batch_settings_render_for_jobs_that_declare_them():
    at = _run(_jobs_page)
    labels = [w.label for w in at.get("number_input")]
    assert "Threshold (days)" in labels
    assert "Batch size" in labels
    assert "Pause between batches (ms)" in labels


def test_a_viewer_without_run_or_edit_sees_disabled_controls(monkeypatch):
    import vaybooks.bms.ui.pages.schedulers._common as common

    monkeypatch.setattr(common, "can", lambda services, permission: False)
    at = _run(_viewer_page)
    by_label = {b.label: b for b in at.get("button")}
    assert by_label["Run now"].disabled is True
    assert by_label["Save"].disabled is True


def test_scheduled_reports_lists_the_domain_catalog():
    at = _run(_reports_page)
    options = [o for box in at.get("selectbox") for o in box.options]
    assert "Lead Funnel (Pipeline)" in options


def test_scheduled_reports_has_report_and_execution_status_tabs():
    at = _run(_reports_page)
    assert [t.label for t in at.get("tab")] == ["Report", "Execution status"]


def test_scheduled_reports_exposes_configure_and_run_actions():
    at = _run(_reports_page)
    labels = [b.label for b in at.get("button")]
    assert "Configure" in labels
    assert "Run now" in labels
    assert "Dry run" in labels


def test_configure_lives_in_a_dialog_not_on_the_report_tab():
    """Date range / schedule knobs belong in Configure, not the result tab."""
    at = _run(_reports_page)
    assert not any(box.label == "Date range" for box in at.get("selectbox"))
    assert not any(box.label == "How often" for box in at.get("selectbox"))


def test_report_tab_shows_the_execution_result():
    at = _run(_reports_page_with_history)
    body = _text(at)
    assert "Showing run from" in body or "stage" in body.lower()
    assert any(b.label == "Download CSV" for b in at.get("download_button"))


def test_execution_status_shows_recent_runs():
    at = _run(_reports_page_with_history)
    assert any(s.value == "Recent runs" for s in at.get("subheader"))
    assert not any(m.label == "Status" for m in at.get("metric"))
