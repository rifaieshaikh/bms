
def _text(at):
    return " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("title")
        + at.get("subheader") + at.get("caption") + at.get("info")
    )


def test_customers_list_route_renders():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.ui.pages import customers

        services = {
            "customers": MagicMock(list_all_customers=MagicMock(return_value=[])),
            "orders": MagicMock(order_counts_by_customer=MagicMock(return_value={})),
        }
        customers.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception
    assert "Customers" in _text(at)


def test_customer_detail_route_renders_from_query_id():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        import streamlit as st

        from vaybooks.bms.domain.customers.entities import Customer
        from vaybooks.bms.ui.pages import customer_detail

        customer = Customer(
            id="cust-1",
            customer_name="Ananya Rao",
            phone_number="9000000001",
            created_at=datetime(2026, 6, 1),
        )
        st.query_params["id"] = "cust-1"
        services = {
            "customers": MagicMock(
                get_customer_detail=MagicMock(return_value=customer)
            ),
            "orders": MagicMock(
                order_counts_by_customer=MagicMock(return_value={"cust-1": 2}),
                list_by_customer=MagicMock(return_value=[]),
            ),
        }
        customer_detail.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception
    assert "Ananya Rao" in _text(at)
    buttons = " ".join(getattr(el, "label", "") or "" for el in at.button)
    assert "Back to customers" in buttons
