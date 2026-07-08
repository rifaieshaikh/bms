"""Account detail route (`?id=<account_id>`): per-account ledger."""

from vaybooks.bms.ui.pages.accounts import render_account_detail


def render(services: dict):
    render_account_detail(services)
