from vaybooks.bms.domain.schedulers.entities import DOMAIN_PRODUCTION
from vaybooks.bms.ui.pages.schedulers._scheduled_reports import (
    render_scheduled_reports_page,
)

PAGE_KEY = "production-scheduled-reports"


def render(services: dict) -> None:
    render_scheduled_reports_page(services, domain=DOMAIN_PRODUCTION)
