"""Navigation helpers pass query params into st.switch_page for visible URLs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vaybooks.bms.ui import navigation


def test_go_to_detail_passes_id_query_params():
    target = object()
    navigation.register("test_detail", target)
    try:
        with patch("vaybooks.bms.ui.navigation.st") as mock_st:
            mock_st.session_state = {}
            mock_st.switch_page = MagicMock()
            navigation.go_to_detail(
                "test_detail", "res-123", order_id="ord-9"
            )
            mock_st.switch_page.assert_called_once_with(
                target,
                query_params={"id": "res-123", "order_id": "ord-9"},
            )
            assert mock_st.session_state["_detail_id_test_detail"] == "res-123"
            assert (
                mock_st.session_state["_detail_param_test_detail_order_id"]
                == "ord-9"
            )
    finally:
        navigation._pages.pop("test_detail", None)


def test_go_to_list_passes_deep_link_query_params():
    target = object()
    navigation.register("test_list", target)
    try:
        with patch("vaybooks.bms.ui.navigation.st") as mock_st:
            mock_st.session_state = {}
            mock_st.switch_page = MagicMock()
            navigation.go_to_list("test_list", customer="cust-1")
            mock_st.switch_page.assert_called_once_with(
                target, query_params={"customer": "cust-1"}
            )
    finally:
        navigation._pages.pop("test_list", None)


def test_go_back_to_list_clears_query_params():
    target = object()
    navigation.register("test_list", target)
    try:
        with patch("vaybooks.bms.ui.navigation.st") as mock_st:
            mock_st.session_state = {"_detail_id_test_list": "old"}
            mock_st.switch_page = MagicMock()
            with patch(
                "vaybooks.bms.ui.navigation.clear_list_state"
            ) as clear:
                navigation.go_back_to_list("orders", "test_list")
                clear.assert_called_once_with("orders")
            mock_st.switch_page.assert_called_once_with(
                target, query_params={}
            )
    finally:
        navigation._pages.pop("test_list", None)
