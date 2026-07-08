
def test_dashboard_open_sets_view_order_id():
    def _page():
        from datetime import date

        from vaybooks.bms.ui import navigation
        from vaybooks.bms.ui.components.dashboard_cards import order_action_cards

        navigation.customization_orders_page = None
        order_action_cards(
            "In Progress",
            [
                {
                    "id": "ord-dash-1",
                    "order_number": "O-1001",
                    "customer_name": "QA Customer",
                    "order_status": "In Progress",
                    "expected_delivery_date": date(2024, 7, 1),
                }
            ],
            "progress",
        )

    from streamlit.testing.v1 import AppTest

    from vaybooks.bms.ui.session_keys import VIEW_ORDER_ID

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    open_btn = next(el for el in at.button if el.label == "Open →")
    open_btn.click().run(timeout=15)
    assert not at.exception
    assert at.session_state[VIEW_ORDER_ID] == "ord-dash-1"
