"""Projects schedulers page."""

from __future__ import annotations

from vaybooks.bms.domain.schedulers.entities import DOMAIN_PROJECTS
from vaybooks.bms.ui.pages.schedulers._common import render_page

PAGE_KEY = "schedulers-projects"


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.context import set_current_page

    set_current_page(PAGE_KEY)
    render_page(services, domain=DOMAIN_PROJECTS)
