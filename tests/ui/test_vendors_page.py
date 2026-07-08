
def _text(at):
    return " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("title")
        + at.get("subheader") + at.get("caption") + at.get("info")
    )


def test_vendors_list_route_renders():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.ui.pages import vendors

        services = {
            "vendors": MagicMock(list_all_vendors=MagicMock(return_value=[])),
            "accounting": MagicMock(
                get_vendor_account=MagicMock(return_value=None)
            ),
        }
        vendors.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception
    assert "Vendors" in _text(at)
