from vaybooks.bms.ui.pages.sales._shared.priced_documents import render_list


def render(services: dict) -> None:
    render_list(services, "quotation")
