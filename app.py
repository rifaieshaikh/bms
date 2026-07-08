import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.bootstrap import get_services
from vaybooks.bms.ui.pages import (
    accounts,
    customers,
    vendors,
    vendor_services,
    dashboard,
    export_backup,
    reports,
)
from vaybooks.bms.ui.pages import activities, customization_items, customization_orders
from vaybooks.bms.ui.pages import mtd_dashboard, time_tracking

st.set_page_config(
    page_title="Zahcci Customization Orders",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _page(module):
    """Wrap a page module so st.navigation can call it."""

    def render_page():
        module.render(get_services())

    render_page.__name__ = module.__name__.rsplit(".", 1)[-1]
    return render_page


navigation.customization_orders_page = st.Page(
    _page(customization_orders),
    title="Customization Orders",
    icon=":material/shopping_bag:",
)

page_groups = {
    "": [
        st.Page(
            _page(dashboard),
            title="Dashboard",
            icon=":material/dashboard:",
            default=True,
        ),
    ],
    "Operations": [
        st.Page(
            _page(customers),
            title="Customers",
            icon=":material/group:",
        ),
        st.Page(
            _page(vendors),
            title="Vendors",
            icon=":material/local_shipping:",
        ),
        navigation.customization_orders_page,
        st.Page(
            _page(customization_items),
            title="Customization Items",
            icon=":material/inventory_2:",
        ),
        st.Page(
            _page(time_tracking),
            title="Time Tracking",
            icon=":material/schedule:",
        ),
    ],
    "Finance": [
        st.Page(
            _page(accounts),
            title="Accounts",
            icon=":material/account_balance:",
        ),
        st.Page(
            _page(mtd_dashboard),
            title="MTD Dashboard",
            icon=":material/calendar_month:",
        ),
        st.Page(
            _page(reports),
            title="Reports",
            icon=":material/analytics:",
        ),
        st.Page(
            _page(export_backup),
            title="Export / Backup",
            icon=":material/download:",
        ),
    ],
    "Settings": [
        st.Page(
            _page(activities),
            title="Activity Configuration",
            icon=":material/checklist:",
        ),
        st.Page(
            _page(vendor_services),
            title="Service Configuration",
            icon=":material/category:",
        ),
    ],
}

# Hide the built-in menu (Streamlit pins it to the very top of the sidebar) and
# draw our own below the branding so "VayBooks" sits on top.
nav = st.navigation(page_groups, position="hidden")

with st.sidebar:
    st.markdown("## VayBooks")
    st.caption("Boutique Management")
    st.divider()
    for header, pages in page_groups.items():
        if header:
            st.caption(header)
        for page in pages:
            st.page_link(page)

nav.run()
