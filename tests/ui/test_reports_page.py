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
    tab_labels = " ".join(getattr(el, "label", "") or "" for el in at.get("tab"))
    return f"{rendered} {labels} {tab_labels}"


def _services_dict():
    from unittest.mock import MagicMock

    empty = MagicMock(return_value=[])
    summary = MagicMock(
        return_value={"order_count": 3, "invoiced": 12000, "expenses": 4500}
    )
    business = MagicMock(
        period_financial_summary=empty,
        top_customers_by_revenue=empty,
        top_customers_by_margin=empty,
        customer_outstanding_report=empty,
        vendor_payables_report=empty,
        cash_movement_report=empty,
        expense_by_source_report=empty,
        customer_segments_report=empty,
        expense_detail_report=empty,
        get_period_summary=summary,
    )
    profitability = MagicMock(
        item_profitability_report=empty,
        mph_report=empty,
    )
    operations = MagicMock(
        order_pipeline_report=empty,
        bills_pending_invoice_report=empty,
        activity_bottleneck_report=empty,
        delivery_performance_report=empty,
        activity_pending_report=empty,
        overdue_order_report=empty,
        completed_order_report=empty,
    )
    labor = MagicMock(
        time_tracking_report=empty,
        worker_productivity_report=empty,
        labor_vs_mph_report=empty,
    )
    customers = MagicMock(customer_order_history=empty)
    inventory = MagicMock(
        list_categories=MagicMock(return_value=[]),
        list_products=MagicMock(return_value=[]),
    )
    reports_inventory = MagicMock(
        stock_on_hand_report=empty,
        low_stock_report=empty,
        stock_movements_report=empty,
        inventory_valuation_report=empty,
    )
    reports_purchases = MagicMock(
        purchase_orders_pipeline_report=empty,
        grn_pending_report=empty,
        purchases_by_vendor_report=empty,
        purchase_returns_summary_report=empty,
    )
    return {
        "reports": MagicMock(get_period_summary=summary),
        "reports_business": business,
        "reports_profitability": profitability,
        "reports_operations": operations,
        "reports_labor": labor,
        "reports_customers": customers,
        "reports_inventory": reports_inventory,
        "reports_purchases": reports_purchases,
        "inventory": inventory,
        "customers": MagicMock(),
        "activities": MagicMock(list_activities=MagicMock(return_value=[])),
    }


def test_reports_page_renders_category_tabs():
    def _page(services=None):
        from vaybooks.bms.ui.pages.finance.reports import list as reports

        reports.render(services or _services_dict())

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page, args=(_services_dict(),))
    at.run(timeout=15)
    assert not at.exception
    page_text = _page_text(at).lower()
    assert "profitability" in page_text
    assert "operations" in page_text
    assert "inventory" in page_text


def test_reports_page_shows_aggregated_mph_marker():
    def _page(services=None):
        from vaybooks.bms.ui.pages.finance.reports import list as reports

        reports.render(services or _services_dict())

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page, args=(_services_dict(),))
    at.run(timeout=15)
    profitability_tab = next(
        tab for tab in at.tabs if tab.label == "Profitability"
    )
    profitability_tab.selectbox[0].set_value("Margin Per Hour (MPH)").run(timeout=15)
    assert not at.exception

    page_text = _page_text(at).lower()
    assert "aggregated" in page_text


def test_reports_page_shows_aggregated_period_summary_for_mtd():
    def _page(services=None):
        from vaybooks.bms.ui.pages.finance.reports import list as reports

        reports.render(services or _services_dict())

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page, args=(_services_dict(),))
    at.run(timeout=15)
    profitability_tab = next(
        tab for tab in at.tabs if tab.label == "Profitability"
    )
    profitability_tab.selectbox[0].set_value("Margin Per Hour (MPH)").run(timeout=15)
    assert not at.exception

    page_text = _page_text(at).lower()
    assert "aggregated totals for period" in page_text
    assert "aggregated" in page_text
