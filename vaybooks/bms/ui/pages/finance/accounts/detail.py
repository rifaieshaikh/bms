"""Account detail route."""

from vaybooks.bms.ui.pages.finance.accounts.list import render_account_detail


def render(services: dict):
    render_account_detail(services)
