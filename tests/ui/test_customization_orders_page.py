
def test_customization_orders_list_page_renders():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.ui.pages import customization_orders_list

        services = {
            "orders": MagicMock(
                search_customization_orders=MagicMock(return_value=[]),
                list_by_customer=MagicMock(return_value=[]),
            ),
            "customers": MagicMock(list_all_customers=MagicMock(return_value=[])),
        }
        customization_orders_list.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("title") + at.get("info")
    )
    assert "Customization Orders" in rendered


def test_order_detail_route_renders_from_query_id():
    def _page():
        from datetime import date
        from unittest.mock import MagicMock

        import streamlit as st

        from vaybooks.bms.domain.boutique.orders.entities import CustomizationItem, CustomizationOrder
        from vaybooks.bms.domain.shared.enums import OrderStatus
        from vaybooks.bms.ui.pages import customization_order_detail

        order = CustomizationOrder(
            id="ord-test-1",
            order_number="O-TEST-001",
            customer_id="cust-1",
            customer_name="QA Customer",
            phone_number="9000000001",
            order_date=date(2024, 6, 1),
            expected_delivery_date=date(2024, 7, 1),
            customization_items=[
                CustomizationItem(bill_number="ZB001", description="Test item"),
            ],
            order_status=OrderStatus.IN_PROGRESS,
        )
        st.query_params["id"] = order.id

        order_service = MagicMock()
        order_service.get_order_detail.return_value = order
        order_service.get_activity_statuses.return_value = ["Created", "Completed"]
        activity = MagicMock()
        activity.list_activities.return_value = []
        activity.get_activity.return_value = None
        services = {
            "orders": order_service,
            "invoices": MagicMock(list_invoices_by_order=MagicMock(return_value=[])),
            "deliveries": MagicMock(list_by_order=MagicMock(return_value=[])),
            "time_tracking": MagicMock(get_entries_by_order=MagicMock(return_value=[])),
            "expenses": MagicMock(
                get_order_totals=MagicMock(return_value={}),
                get_expenses_by_bill=MagicMock(return_value=[]),
            ),
            "accounting": MagicMock(
                list_vouchers_by_order=MagicMock(return_value=[]),
                get_order_total_received=MagicMock(return_value=0.0),
                get_store_accounts=MagicMock(return_value=[]),
                list_vendor_payments=MagicMock(return_value=[]),
            ),
            "activities": activity,
            "customers": MagicMock(),
            "vendors": MagicMock(list_vendors=MagicMock(return_value=[])),
            "vendor_services": MagicMock(list_services=MagicMock(return_value=[])),
            "measurements": MagicMock(
                list_by_customer=MagicMock(return_value=[]),
                get_record=MagicMock(return_value=None),
            ),
        }
        customization_order_detail.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    at.run(timeout=15)
    assert not at.exception

    buttons = " ".join(getattr(el, "label", "") or "" for el in at.button)
    assert "Back to orders" in buttons
