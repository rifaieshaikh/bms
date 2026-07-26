"""Production schedulers page."""

from vaybooks.bms.domain.schedulers.entities import DOMAIN_PRODUCTION
from vaybooks.bms.ui.pages.schedulers._common import render_page

PAGE_KEY = "schedulers-production"


def render(services: dict) -> None:
    render_page(services, domain=DOMAIN_PRODUCTION)
