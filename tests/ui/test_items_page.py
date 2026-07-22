
def _text(at):
    return " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("title")
        + at.get("subheader") + at.get("caption") + at.get("info")
    )


def test_items_list_route_renders():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.ui.pages.boutique.items import list as customization_items

        services = {
            "orders": MagicMock(
                list_all_customization_items=MagicMock(return_value=[])
            ),
        }
        customization_items.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception
    assert "Customization Items" in _text(at)
