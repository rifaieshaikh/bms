
def _page_text(at) -> str:
    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown")
        + at.get("header")
        + at.get("subheader")
        + at.get("info")
        + at.get("caption")
        + at.get("metric")
    )
    labels = " ".join(getattr(el, "label", "") or "" for el in at.get("selectbox"))
    return f"{rendered} {labels}"


def test_reports_page_shows_aggregated_mph_marker():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.ui.pages import reports

        report_service = MagicMock(
            get_period_summary=MagicMock(
                return_value={
                    "order_count": 3,
                    "invoiced": 12000,
                    "expenses": 4500,
                }
            ),
            item_profitability_report=MagicMock(return_value=[]),
            mph_report=MagicMock(return_value=[]),
        )
        services = {
            "reports": report_service,
            "customers": MagicMock(),
            "activities": MagicMock(list_activities=MagicMock(return_value=[])),
        }
        reports.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    page_text = _page_text(at).lower()
    assert "aggregated" in page_text
    assert "bill20242010" in page_text
    assert "exactly" in page_text
    assert "included" in page_text


def test_reports_page_shows_aggregated_period_summary_for_mtd():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.ui.pages import reports

        report_service = MagicMock(
            get_period_summary=MagicMock(
                return_value={
                    "order_count": 1,
                    "invoiced": 8000,
                    "expenses": 2000,
                }
            ),
            item_profitability_report=MagicMock(return_value=[]),
            mph_report=MagicMock(return_value=[]),
        )
        services = {
            "reports": report_service,
            "customers": MagicMock(),
            "activities": MagicMock(list_activities=MagicMock(return_value=[])),
        }
        reports.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    at.selectbox[0].set_value("Margin Per Hour (MPH)").run(timeout=15)
    assert not at.exception

    page_text = _page_text(at).lower()
    assert "aggregated totals for period" in page_text
    assert "aggregated" in page_text
