"""Global header: notification gating/cache, settings filtering, sign-out."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common import app_header


class FakeNotificationService:
    def __init__(self, items):
        self.items = list(items)
        self.calls = 0

    def list_pending_approvals(self, user_id):
        self.calls += 1
        return list(self.items)


def _item(kind, project_id="prj-1", title="Pending"):
    return SimpleNamespace(
        kind=kind, title=title, project_id=project_id, id=f"{kind}-{project_id}"
    )


def _services(svc):
    return {"project_notifications": svc}


def test_notifications_hidden_without_permission(monkeypatch):
    svc = FakeNotificationService([_item("quotation_approval")])
    monkeypatch.setattr(app_header, "can_permission", lambda s, k: False)
    with patch.object(app_header, "st") as mock_st:
        mock_st.session_state = {}
        assert app_header._load_pending_approvals(_services(svc)) == []
    assert svc.calls == 0, "service must not be queried without approve permission"


def test_notifications_filtered_by_kind_permission(monkeypatch):
    svc = FakeNotificationService(
        [_item("quotation_approval"), _item("ra_approval")]
    )
    monkeypatch.setattr(
        app_header,
        "can_permission",
        lambda s, key: key == "projects.commercial.approve",
    )
    monkeypatch.setattr(app_header, "current_user_id", lambda: "u1")
    with patch.object(app_header, "st") as mock_st:
        mock_st.session_state = {}
        items = app_header._load_pending_approvals(_services(svc))
    assert [i.kind for i in items] == ["quotation_approval"]


def test_notifications_cached_within_ttl(monkeypatch):
    svc = FakeNotificationService([_item("ra_approval")])
    monkeypatch.setattr(app_header, "can_permission", lambda s, k: True)
    monkeypatch.setattr(app_header, "current_user_id", lambda: "u1")
    with patch.object(app_header, "st") as mock_st:
        mock_st.session_state = {}
        first = app_header._load_pending_approvals(_services(svc))
        second = app_header._load_pending_approvals(_services(svc))
    assert svc.calls == 1
    assert len(first) == len(second) == 1


def test_notifications_refresh_invalidates_cache(monkeypatch):
    svc = FakeNotificationService([_item("ra_approval")])
    monkeypatch.setattr(app_header, "can_permission", lambda s, k: True)
    monkeypatch.setattr(app_header, "current_user_id", lambda: "u1")
    with patch.object(app_header, "st") as mock_st:
        state = {}
        mock_st.session_state = state
        app_header._load_pending_approvals(_services(svc))

        # invalidate_notification_cache pops via the real st module; emulate
        # it against the same dict the mocked module used.
        state.pop(app_header.NOTIF_CACHE, None)
        state.pop(app_header.NOTIF_CACHE_AT, None)
        app_header._load_pending_approvals(_services(svc))
    assert svc.calls == 2


def test_notifications_cache_expires_after_ttl(monkeypatch):
    svc = FakeNotificationService([_item("quotation_approval")])
    monkeypatch.setattr(app_header, "can_permission", lambda s, k: True)
    monkeypatch.setattr(app_header, "current_user_id", lambda: "u1")
    now = [1_000_000.0]
    monkeypatch.setattr(app_header.time, "time", lambda: now[0])
    with patch.object(app_header, "st") as mock_st:
        mock_st.session_state = {}
        app_header._load_pending_approvals(_services(svc))
        now[0] += app_header.NOTIF_TTL_SECONDS + 1
        app_header._load_pending_approvals(_services(svc))
    assert svc.calls == 2


def test_visible_settings_pages_filters_by_permission(monkeypatch):
    pages = [
        SimpleNamespace(url_path="business-settings"),
        SimpleNamespace(url_path="print-settings"),
        SimpleNamespace(url_path="services-settings"),
    ]
    monkeypatch.setattr(
        app_header,
        "can_see_page",
        lambda services, url: url != "print-settings",
    )
    visible = app_header.visible_settings_pages({}, pages)
    assert [p.url_path for p in visible] == [
        "business-settings",
        "services-settings",
    ]


def test_account_popover_dispatches_sign_out():
    with patch.object(app_header, "st") as mock_st, patch(
        "vaybooks.bms.ui.auth.dialogs.sign_out_dialog"
    ) as dialog:
        mock_st.session_state = {}
        mock_st.button.return_value = True
        with patch.object(app_header, "current_user_name", lambda: "Admin"):
            app_header._render_account({"users": object()})
    dialog.assert_called_once()


def test_account_popover_without_click_does_not_sign_out():
    with patch.object(app_header, "st") as mock_st, patch(
        "vaybooks.bms.ui.auth.dialogs.sign_out_dialog"
    ) as dialog:
        mock_st.session_state = {}
        mock_st.button.return_value = False
        with patch.object(app_header, "current_user_name", lambda: "Admin"):
            app_header._render_account({"users": object()})
    dialog.assert_not_called()


def test_notification_open_navigates_to_project_workspace():
    """The workspace route consumes the ``project`` query param the header sends."""
    target = object()
    previous = navigation._pages.get("project_workspace")
    navigation.register("project_workspace", target)
    try:
        with patch("vaybooks.bms.ui.navigation.st") as mock_st:
            mock_st.session_state = {}
            mock_st.switch_page = MagicMock()
            navigation.go_to_list("project_workspace", project="prj-77")
            mock_st.switch_page.assert_called_once_with(
                target, query_params={"project": "prj-77"}
            )
    finally:
        if previous is not None:
            navigation._pages["project_workspace"] = previous
        else:
            navigation._pages.pop("project_workspace", None)
