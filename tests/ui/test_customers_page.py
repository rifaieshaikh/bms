
def _text(at):
    return " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("title")
        + at.get("subheader") + at.get("caption") + at.get("info")
    )


def test_customers_list_route_renders():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.ui.pages.parties.customers import list as customers

        services = {
            "customers": MagicMock(list_all_customers=MagicMock(return_value=[])),
            "orders": MagicMock(order_counts_by_customer=MagicMock(return_value={})),
            "accounting": MagicMock(
                customer_balances_by_customer=MagicMock(return_value={})
            ),
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

        from vaybooks.bms.domain.parties.customers.entities import Customer
        from vaybooks.bms.ui.pages.parties.customers import detail as customer_detail

        customer = Customer(
            id="cust-1",
            customer_name="Ananya Rao",
            phone_number="9000000001",
            created_at=datetime(2026, 6, 1),
        )
        st.query_params["id"] = "cust-1"
        account = MagicMock(id="acc-1", current_balance=0.0)
        sales = MagicMock(
            related_document_counts=MagicMock(
                return_value={
                    "estimates": 3,
                    "quotations": 2,
                    "sales_orders": 7,
                    "delivery_notes": 1,
                    "sales_returns": 0,
                    "sales_invoices": 12,
                    "receipts": 8,
                }
            )
        )
        services = {
            "customers": MagicMock(
                get_customer_detail=MagicMock(return_value=customer)
            ),
            "orders": MagicMock(
                order_counts_by_customer=MagicMock(return_value={"cust-1": 2}),
                get_customer_summary=MagicMock(
                    return_value={
                        "order_count": 2,
                        "active_count": 1,
                        "total_invoiced": 0.0,
                    }
                ),
                list_recent_by_customer=MagicMock(return_value=[]),
            ),
            "measurements": MagicMock(list_by_customer=MagicMock(return_value=[])),
            "accounting": MagicMock(
                get_customer_account=MagicMock(return_value=account)
            ),
            "sales": sales,
        }
        customer_detail.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception
    assert "Ananya Rao" in _text(at)
    buttons = " ".join(getattr(el, "label", "") or "" for el in at.button)
    assert "Back to customers" in buttons
    assert "Edit Customer" in buttons
    assert "View" in buttons
    assert "Related Transactions" in _text(at)
    assert "Quick Actions" in _text(at)
    assert "Sales Order" in buttons
    assert "Invoice" in buttons
    assert "Record Receipt" in buttons
    assert "Measurements" in _text(at)
    assert "Customization Orders" in _text(at)
    assert "Customer Ledger" in _text(at)
    assert "Recent Customization Orders" in _text(at)
    assert "No customization orders yet" in _text(at)
    assert "Settled" in _text(at) or "₹0.00" in _text(at)