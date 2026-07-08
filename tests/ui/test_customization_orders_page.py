
def test_customization_orders_page_shows_preview_item_mph_while_marker():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.ui.pages import customization_orders

        order_repo = MagicMock(list_all=MagicMock(return_value=[]))
        services = {
            "orders": MagicMock(
                search_customization_orders=MagicMock(return_value=[]),
                list_by_customer=MagicMock(return_value=[]),
            ),
            "order_repo": order_repo,
            "customers": MagicMock(),
        }
        customization_orders.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("info")
    )
    assert "while" in rendered.lower()
    assert "preview_item_mph" in rendered
    assert "ZB013" in rendered
