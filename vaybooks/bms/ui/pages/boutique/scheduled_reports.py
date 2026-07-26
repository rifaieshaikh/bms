"""Boutique scheduled reports page."""

from __future__ import annotations

from vaybooks.bms.domain.schedulers.entities import DOMAIN_BOUTIQUE
from vaybooks.bms.ui.pages.schedulers._scheduled_reports import (
    render_scheduled_reports_page,
)

PAGE_KEY = "boutique-scheduled-reports"


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.context import set_current_page

    set_current_page(PAGE_KEY)
    render_scheduled_reports_page(services, domain=DOMAIN_BOUTIQUE)
