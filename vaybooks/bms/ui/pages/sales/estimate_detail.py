from vaybooks.bms.ui.pages.sales.priced_documents import render_detail


def render(services: dict) -> None:
    render_detail(services, "estimate")
