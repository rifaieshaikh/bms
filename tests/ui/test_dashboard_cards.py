
def test_dashboard_open_sets_detail_id():
    def _page():
        from datetime import date

        from vaybooks.bms.ui.components.home.dashboard_cards import order_action_cards

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

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    open_btn = next(el for el in at.button if el.label == "Open →")
    open_btn.click().run(timeout=15)
    assert not at.exception
    # go_to_detail seeds a session fallback id even when the route is unregistered.
    assert at.session_state["_detail_id_order_detail"] == "ord-dash-1"
