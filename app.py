import streamlit as st

from vaybooks.bms import __version__
from vaybooks.bms.infrastructure.config.runtime import is_desktop
from vaybooks.bms.infrastructure.logging.setup import setup_logging
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.bootstrap import get_services
from vaybooks.bms.ui.styles import inject_global_css
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
from vaybooks.bms.ui.pages import customization_orders_list, customization_order_detail
from vaybooks.bms.ui.pages import customization_item_detail, customer_detail, vendor_detail
from vaybooks.bms.ui.pages import account_detail
from vaybooks.bms.ui.pages import mtd_dashboard, time_tracking
from vaybooks.bms.ui.pages import workers
from vaybooks.bms.ui.pages import system_settings, system_logs, system_updates
from vaybooks.bms.ui.pages.finance import (
    accounting_invoices,
    journal as finance_journal,
    payments as finance_payments,
    receipts as finance_receipts,
    trial_balance,
    vouchers as finance_vouchers,
)

setup_logging()

st.set_page_config(
    page_title="Zahcci Customization Orders",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="auto",
)

inject_global_css()


def _page(module):
    """Wrap a page module so st.navigation can call it."""

    def render_page():
        module.render(get_services())

    render_page.__name__ = module.__name__.rsplit(".", 1)[-1]
    return render_page


# --- Visible routes (rendered in the sidebar) --------------------------------
dashboard_page = st.Page(
    _page(dashboard), title="Dashboard", icon=":material/dashboard:",
    url_path="dashboard", default=True,
)
customers_page = st.Page(
    _page(customers), title="Customers", icon=":material/group:", url_path="customers",
)
vendors_page = st.Page(
    _page(vendors), title="Vendors", icon=":material/local_shipping:",
    url_path="vendors",
)
orders_list_page = st.Page(
    _page(customization_orders_list), title="Customization Orders",
    icon=":material/shopping_bag:", url_path="orders",
)
items_page = st.Page(
    _page(customization_items), title="Customization Items",
    icon=":material/inventory_2:", url_path="items",
)
time_page = st.Page(
    _page(time_tracking), title="Time Log", icon=":material/schedule:",
    url_path="time",
)
accounts_page = st.Page(
    _page(accounts), title="Accounts", icon=":material/account_balance:",
    url_path="accounts",
)
vouchers_page = st.Page(
    _page(finance_vouchers), title="Vouchers", icon=":material/receipt_long:",
    url_path="vouchers",
)
receipts_page = st.Page(
    _page(finance_receipts), title="Receipts", icon=":material/payments:",
    url_path="receipts",
)
payments_page = st.Page(
    _page(finance_payments), title="Payments", icon=":material/send_money:",
    url_path="payments",
)
accounting_invoices_page = st.Page(
    _page(accounting_invoices), title="Accounting Invoices",
    icon=":material/request_quote:", url_path="accounting-invoices",
)
journal_page = st.Page(
    _page(finance_journal), title="Journal", icon=":material/menu_book:",
    url_path="journal",
)
trial_balance_page = st.Page(
    _page(trial_balance), title="Trial Balance", icon=":material/balance:",
    url_path="trial-balance",
)
mtd_page = st.Page(
    _page(mtd_dashboard), title="Period Dashboard", icon=":material/calendar_month:",
    url_path="mtd-dashboard",
)
reports_page = st.Page(
    _page(reports), title="Reports", icon=":material/analytics:", url_path="reports",
)
export_page = st.Page(
    _page(export_backup), title="Export / Backup", icon=":material/download:",
    url_path="export-backup",
)
activities_page = st.Page(
    _page(activities), title="Activity Configuration", icon=":material/checklist:",
    url_path="activities",
)
services_page = st.Page(
    _page(vendor_services), title="Service Configuration", icon=":material/category:",
    url_path="services",
)
workers_page = st.Page(
    _page(workers), title="Workers", icon=":material/badge:", url_path="workers",
)

system_settings_page = st.Page(
    _page(system_settings), title="Settings", icon=":material/settings:",
    url_path="system-settings",
)
system_updates_page = st.Page(
    _page(system_updates), title="Updates", icon=":material/system_update:",
    url_path="system-updates",
)
system_logs_page = st.Page(
    _page(system_logs), title="Logs", icon=":material/article:",
    url_path="system-logs",
)

# --- Hidden detail routes (deep-linkable, not in sidebar) --------------------
order_detail_page = st.Page(
    _page(customization_order_detail), title="Order Detail", url_path="order-detail",
)
item_detail_page = st.Page(
    _page(customization_item_detail), title="Item Detail", url_path="item-detail",
)
customer_detail_page = st.Page(
    _page(customer_detail), title="Customer Detail", url_path="customer-detail",
)
vendor_detail_page = st.Page(
    _page(vendor_detail), title="Vendor Detail", url_path="vendor-detail",
)
account_detail_page = st.Page(
    _page(account_detail), title="Account Detail", url_path="account-detail",
)

# --- Navigation registry (used by go_to_detail / go_back_to_list) ------------
navigation.register("dashboard", dashboard_page)
navigation.register("customers_list", customers_page)
navigation.register("vendors_list", vendors_page)
navigation.register("orders_list", orders_list_page)
navigation.register("order_detail", order_detail_page)
navigation.register("items_list", items_page)
navigation.register("item_detail", item_detail_page)
navigation.register("customer_detail", customer_detail_page)
navigation.register("vendor_detail", vendor_detail_page)
navigation.register("time_list", time_page)
navigation.register("accounts_list", accounts_page)
navigation.register("account_detail", account_detail_page)
navigation.register("vouchers_list", vouchers_page)
navigation.register("receipts_list", receipts_page)
navigation.register("payments_list", payments_page)
navigation.register("accounting_invoices_list", accounting_invoices_page)
navigation.register("journal_list", journal_page)
navigation.register("trial_balance_list", trial_balance_page)
navigation.register("reports", reports_page)
navigation.register("activities_list", activities_page)
navigation.register("services_list", services_page)
navigation.register("workers_list", workers_page)

page_groups = {
    "": [dashboard_page, mtd_page],
    "Operations": [
        customers_page,
        vendors_page,
        orders_list_page,
        items_page,
        time_page,
    ],
    "Finance": [
        accounts_page,
        vouchers_page,
        receipts_page,
        payments_page,
        accounting_invoices_page,
        journal_page,
        trial_balance_page,
        reports_page,
        export_page,
    ],
    "Settings": [
        activities_page,
        services_page,
        workers_page,
    ],
}

if is_desktop():
    page_groups["System"] = [
        system_settings_page,
        system_updates_page,
        system_logs_page,
    ]

hidden_pages = [
    order_detail_page,
    item_detail_page,
    customer_detail_page,
    vendor_detail_page,
    account_detail_page,
]

# All pages must be registered with st.navigation for routing to work.
nav_pages = {group: list(pages) for group, pages in page_groups.items()}
nav_pages["_hidden"] = hidden_pages

# Hide the built-in menu (Streamlit pins it to the very top of the sidebar) and
# draw our own below the branding so "VayBooks" sits on top.
nav = st.navigation(nav_pages, position="hidden")

with st.sidebar:
    st.markdown("## VayBooks")
    st.caption("Boutique Management")
    st.divider()
    for header, pages in page_groups.items():
        if header:
            st.caption(header)
        for page in pages:
            st.page_link(page)
    st.divider()
    st.caption(f"v{__version__}")

nav.run()
