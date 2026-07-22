from vaybooks.bms.ui.pages.sales._shared.priced_documents import render_detail


def render(services: dict) -> None:
    render_detail(services, "estimate")
