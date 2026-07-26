"""CRM route smoke tests: empty states plus a wired leads list."""

import pytest


def _text(at) -> str:
    return " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown")
        + at.get("header")
        + at.get("title")
        + at.get("subheader")
        + at.get("caption")
        + at.get("info")
        + at.get("error")
    )


CRM_PAGES = [
    "vaybooks.bms.ui.pages.crm.dashboard",
    "vaybooks.bms.ui.pages.crm.leads.list",
    "vaybooks.bms.ui.pages.crm.enquiries.list",
    "vaybooks.bms.ui.pages.crm.activities.list",
    "vaybooks.bms.ui.pages.crm.calendar.list",
    "vaybooks.bms.ui.pages.crm.reports",
    "vaybooks.bms.ui.pages.crm.settings",
]


@pytest.mark.parametrize("module_path", CRM_PAGES)
def test_crm_pages_render_empty_state_without_services(module_path):
    def _page(path):
        import importlib

        importlib.import_module(path).render({})

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page, args=(module_path,))
    at.run(timeout=30)
    assert not at.exception
    assert "CRM module is not available yet" in _text(at)


def test_settings_page_shows_sections_without_a_roles_tab():
    def _page():
        from vaybooks.bms.domain.crm.entities import CrmSettings
        from vaybooks.bms.ui.pages.crm import settings

        class Settings:
            def get_settings(self):
                return CrmSettings()

        settings.render({"crm_settings": Settings()})

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=30)
    assert not at.exception
    body = _text(at)
    assert "CRM roles are assigned under Access" in body
    assert "Lists & statuses" in body
    assert "Roles & Permissions" not in body


def test_leads_list_renders_cards_from_a_stub_service():
    def _page():
        from vaybooks.bms.domain.crm.entities import CrmLead
        from vaybooks.bms.ui.pages.crm.leads import list as leads

        class Leads:
            def list_leads(self, **_kwargs):
                return [CrmLead(name="Asha Traders", phone="9876543210", id="l1")]

        leads.render({"crm_leads": Leads()})

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=30)
    assert not at.exception
    body = _text(at)
    assert "Asha Traders" in body
    assert "1 leads" in body


def test_leads_list_shows_the_no_match_state_for_an_empty_backend():
    def _page():
        from vaybooks.bms.ui.pages.crm.leads import list as leads

        class Leads:
            def list_leads(self, **_kwargs):
                return []

        leads.render({"crm_leads": Leads()})

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=30)
    assert not at.exception
    assert "No leads match these filters." in _text(at)


def test_lead_detail_renders_from_the_query_id():
    def _page():
        import streamlit as st

        from vaybooks.bms.domain.crm.entities import CrmLead
        from vaybooks.bms.ui.pages.crm.leads import detail

        class Leads:
            def get_lead(self, lead_id):
                return CrmLead(name="Asha Traders", phone="9876543210", id=lead_id)

        st.query_params["id"] = "l1"
        detail.render({"crm_leads": Leads()})

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=30)
    assert not at.exception
    body = _text(at)
    assert "Asha Traders" in body
    assert "No activity recorded for this lead yet." in body


def test_lead_detail_reports_a_missing_record():
    def _page():
        import streamlit as st

        from vaybooks.bms.ui.pages.crm.leads import detail

        class Leads:
            def get_lead(self, _lead_id):
                return None

        st.query_params["id"] = "missing"
        detail.render({"crm_leads": Leads()})

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=30)
    assert not at.exception
    assert "Lead not found." in _text(at)


def test_customer_detail_shows_the_crm_section_when_services_exist():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        import streamlit as st

        from vaybooks.bms.domain.crm.entities import CrmActivity
        from vaybooks.bms.domain.parties.customers.entities import Customer
        from vaybooks.bms.ui.pages.parties.customers import detail

        class Activities:
            def list_activities(self, **_kwargs):
                return [
                    CrmActivity(
                        activity_type="Called",
                        customer_id="c1",
                        party_name="Asha Traders",
                        activity_at=datetime(2026, 5, 1, 10, 0),
                    )
                ]

        customer = Customer(
            customer_name="Asha Traders",
            phone_number="9876543210",
            id="c1",
            created_at=datetime(2026, 1, 1),
        )
        st.query_params["id"] = "c1"
        detail.render(
            {
                "customers": MagicMock(
                    get_customer_detail=MagicMock(return_value=customer)
                ),
                "orders": MagicMock(
                    get_customer_summary=MagicMock(return_value={}),
                    list_recent_by_customer=MagicMock(return_value=[]),
                ),
                "crm_activities": Activities(),
            }
        )

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=30)
    assert not at.exception
    body = _text(at)
    assert "Activity timeline" in body
    assert "Called" in body


def test_customer_detail_hides_crm_section_without_crm_services():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        import streamlit as st

        from vaybooks.bms.domain.parties.customers.entities import Customer
        from vaybooks.bms.ui.pages.parties.customers import detail

        customer = Customer(
            customer_name="Asha Traders",
            phone_number="9876543210",
            id="c1",
            created_at=datetime(2026, 1, 1),
        )
        st.query_params["id"] = "c1"
        services = {
            "customers": MagicMock(
                get_customer_detail=MagicMock(return_value=customer)
            ),
            "orders": MagicMock(
                get_customer_summary=MagicMock(return_value={}),
                list_recent_by_customer=MagicMock(return_value=[]),
            ),
        }
        detail.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=30)
    assert not at.exception
    body = _text(at)
    assert "Asha Traders" in body
    assert "Activity timeline" not in body
