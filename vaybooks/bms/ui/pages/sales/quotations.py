from vaybooks.bms.ui.pages.sales.priced_documents import render_list


def render(services: dict) -> None:
    render_list(services, "quotation")
