import streamlit as st

from vaybooks.bms.version import __version__
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
from vaybooks.bms.ui.pages import mtd_dashboard, sales_detail, time_tracking
from vaybooks.bms.ui.pages import (
    measurement_detail,
    measurement_specs,
    measurements,
    order_workspace,
)
from vaybooks.bms.ui.pages.sales import (
    delivery_note_detail as sales_delivery_note_detail_mod,
    delivery_notes as sales_delivery_notes_mod,
    estimate_detail as sales_estimate_detail_mod,
    estimates as sales_estimates_mod,
    invoices as sales_invoices_mod,
    quotation_detail as sales_quotation_detail_mod,
    quotations as sales_quotations_mod,
    return_detail as sales_return_detail_mod,
    returns as sales_returns_mod,
    sales_order_detail as sales_order_detail_mod,
    sales_orders as sales_orders_mod,
)
from vaybooks.bms.ui.pages.inventory import (
    categories as inventory_categories,
    customer_prices as inventory_customer_prices,
    movements as inventory_movements,
    product_detail as inventory_product_detail,
    products as inventory_products,
    stock_ledger as inventory_stock_ledger,
    stock_on_hand as inventory_stock_on_hand,
)
from vaybooks.bms.ui.pages.purchases import (
    bills as purchase_bills_mod,
    goods_receipt as purchase_goods_receipt_mod,
    grn_detail as purchase_grn_detail_mod,
    purchase_detail as purchase_bill_detail_mod,
    purchase_order_detail as purchase_order_detail_mod,
    purchase_orders as purchase_orders_mod,
    return_detail as purchase_return_detail_mod,
    returns as purchase_returns_mod,
)
from vaybooks.bms.ui.pages import workers
from vaybooks.bms.ui.pages import (
    system_settings,
    system_logs,
    system_updates,
    business_settings,
    print_settings,
    keyboard_shortcuts,
)
from vaybooks.bms.ui.pages.migration import (
    categories as migration_categories,
    customers as migration_customers,
    products as migration_products,
    vendors as migration_vendors,
)
from vaybooks.bms.ui.keyboard.resolve import resolve_pressed_shortcuts
from vaybooks.bms.ui.keyboard.defaults import ensure_defaults_loaded
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
    page_title="VayBooks",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="auto",
)

inject_global_css()
ensure_defaults_loaded(force=True)


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
    icon=":material/shopping_bag:", url_path="customizationOrders",
)
items_page = st.Page(
    _page(customization_items), title="Customization Items",
    icon=":material/inventory_2:", url_path="customizationItems",
)
measurements_page = st.Page(
    _page(measurements), title="Measurements",
    icon=":material/straighten:", url_path="measurements",
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
sales_orders_page = st.Page(
    _page(sales_orders_mod), title="Sales Orders", icon=":material/assignment:",
    url_path="sales-orders",
)
sales_estimates_page = st.Page(
    _page(sales_estimates_mod), title="Estimates", icon=":material/request_quote:",
    url_path="estimates",
)
sales_quotations_page = st.Page(
    _page(sales_quotations_mod), title="Quotations", icon=":material/description:",
    url_path="quotations",
)
sales_delivery_notes_page = st.Page(
    _page(sales_delivery_notes_mod), title="Delivery Notes", icon=":material/local_shipping:",
    url_path="delivery-notes",
)
sales_invoices_page = st.Page(
    _page(sales_invoices_mod), title="Sales Invoices", icon=":material/point_of_sale:",
    url_path="sales",
)
sales_returns_page = st.Page(
    _page(sales_returns_mod), title="Sales Returns", icon=":material/undo:",
    url_path="sales-returns",
)
purchase_orders_page = st.Page(
    _page(purchase_orders_mod), title="Purchase Orders", icon=":material/shopping_cart:",
    url_path="purchase-orders",
)
purchase_grn_page = st.Page(
    _page(purchase_goods_receipt_mod), title="Goods Receipt", icon=":material/inventory:",
    url_path="goods-receipt",
)
purchase_bills_page = st.Page(
    _page(purchase_bills_mod), title="Purchase Bills", icon=":material/receipt:",
    url_path="purchases",
)
purchase_returns_page = st.Page(
    _page(purchase_returns_mod), title="Returns", icon=":material/undo:",
    url_path="purchase-returns",
)
reports_page = st.Page(
    _page(reports), title="Reports", icon=":material/analytics:", url_path="reports",
)
export_page = st.Page(
    _page(export_backup), title="Export / Backup", icon=":material/download:",
    url_path="export-backup",
)
migration_categories_page = st.Page(
    _page(migration_categories), title="Categories", icon=":material/upload_file:",
    url_path="migration-categories",
)
migration_products_page = st.Page(
    _page(migration_products), title="Products", icon=":material/upload_file:",
    url_path="migration-products",
)
migration_customers_page = st.Page(
    _page(migration_customers), title="Customers", icon=":material/upload_file:",
    url_path="migration-customers",
)
migration_vendors_page = st.Page(
    _page(migration_vendors), title="Vendors", icon=":material/upload_file:",
    url_path="migration-vendors",
)
activities_page = st.Page(
    _page(activities), title="Activity Configuration", icon=":material/checklist:",
    url_path="activities",
)
measurement_specs_page = st.Page(
    _page(measurement_specs), title="Measurement Specs", icon=":material/straighten:",
    url_path="measurement-specs",
)
order_workspace_page = st.Page(
    _page(order_workspace), title="Order Workspace", icon=":material/edit_note:",
    url_path="order-workspace",
)
services_page = st.Page(
    _page(vendor_services), title="Service Configuration", icon=":material/category:",
    url_path="services",
)
workers_page = st.Page(
    _page(workers), title="Employees", icon=":material/badge:", url_path="employees",
)
inventory_categories_page = st.Page(
    _page(inventory_categories), title="Categories", icon=":material/category:",
    url_path="inventory-categories",
)
inventory_products_page = st.Page(
    _page(inventory_products), title="Products", icon=":material/inventory:",
    url_path="inventory-products",
)
inventory_stock_page = st.Page(
    _page(inventory_stock_on_hand), title="Stock on Hand",
    icon=":material/warehouse:", url_path="inventory-stock",
)
inventory_stock_ledger_page = st.Page(
    _page(inventory_stock_ledger), title="Stock Ledger",
    icon=":material/receipt_long:", url_path="inventory-stock-ledger",
)
inventory_movements_page = st.Page(
    _page(inventory_movements), title="Movements", icon=":material/swap_horiz:",
    url_path="inventory-movements",
)
inventory_customer_prices_page = st.Page(
    _page(inventory_customer_prices), title="Customer Prices",
    icon=":material/sell:", url_path="inventory-customer-prices",
)
purchase_order_detail_page = st.Page(
    _page(purchase_order_detail_mod), title="PO Detail", url_path="purchase-order-detail",
)
purchase_grn_detail_page = st.Page(
    _page(purchase_grn_detail_mod), title="GRN Detail", url_path="grn-detail",
)
purchase_detail_page = st.Page(
    _page(purchase_bill_detail_mod), title="Purchase Detail", url_path="purchase-detail",
)
purchase_return_detail_page = st.Page(
    _page(purchase_return_detail_mod),
    title="Purchase Return Detail",
    url_path="purchase-return-detail",
)

system_settings_page = st.Page(
    _page(system_settings), title="System", icon=":material/settings:",
    url_path="system-settings",
)
business_settings_page = st.Page(
    _page(business_settings), title="Business", icon=":material/store:",
    url_path="business-settings",
)
print_settings_page = st.Page(
    _page(print_settings), title="Print Settings", icon=":material/print:",
    url_path="print-settings",
)
keyboard_shortcuts_page = st.Page(
    _page(keyboard_shortcuts), title="Keyboard Shortcuts",
    icon=":material/keyboard:", url_path="keyboard-shortcuts",
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
measurement_detail_page = st.Page(
    _page(measurement_detail), title="Measurement Detail",
    url_path="measurement-detail",
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
sales_detail_page = st.Page(
    _page(sales_detail), title="Sale Detail", url_path="sales-detail",
)
sales_order_detail_page = st.Page(
    _page(sales_order_detail_mod), title="SO Detail", url_path="sales-order-detail",
)
sales_estimate_detail_page = st.Page(
    _page(sales_estimate_detail_mod), title="Estimate Detail",
    url_path="estimate-detail",
)
sales_quotation_detail_page = st.Page(
    _page(sales_quotation_detail_mod), title="Quotation Detail",
    url_path="quotation-detail",
)
sales_delivery_note_detail_page = st.Page(
    _page(sales_delivery_note_detail_mod), title="DN Detail", url_path="delivery-note-detail",
)
sales_return_detail_page = st.Page(
    _page(sales_return_detail_mod), title="Sales Return Detail",
    url_path="sales-return-detail",
)
inventory_product_detail_page = st.Page(
    _page(inventory_product_detail), title="Product Detail",
    url_path="inventory-product-detail",
)

# --- Navigation registry (used by go_to_detail / go_back_to_list) ------------
navigation.register("dashboard", dashboard_page)
navigation.register("customers_list", customers_page)
navigation.register("vendors_list", vendors_page)
navigation.register("orders_list", orders_list_page)
navigation.register("order_detail", order_detail_page)
navigation.register("items_list", items_page)
navigation.register("item_detail", item_detail_page)
navigation.register("measurements_list", measurements_page)
navigation.register("measurement_detail", measurement_detail_page)
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
navigation.register("mtd_dashboard", mtd_page)
navigation.register("sales_orders_list", sales_orders_page)
navigation.register("sales_order_detail", sales_order_detail_page)
navigation.register("estimates_list", sales_estimates_page)
navigation.register("estimate_detail", sales_estimate_detail_page)
navigation.register("quotations_list", sales_quotations_page)
navigation.register("quotation_detail", sales_quotation_detail_page)
navigation.register("delivery_notes_list", sales_delivery_notes_page)
navigation.register("delivery_note_detail", sales_delivery_note_detail_page)
navigation.register("sales_invoices_list", sales_invoices_page)
navigation.register("sales_detail", sales_detail_page)
navigation.register("sales_returns_list", sales_returns_page)
navigation.register("sales_return_detail", sales_return_detail_page)
navigation.register("purchase_orders_list", purchase_orders_page)
navigation.register("purchase_order_detail", purchase_order_detail_page)
navigation.register("goods_receipt_list", purchase_grn_page)
navigation.register("grn_detail", purchase_grn_detail_page)
navigation.register("purchases_list", purchase_bills_page)
navigation.register("purchase_detail", purchase_detail_page)
navigation.register("purchase_returns_list", purchase_returns_page)
navigation.register("purchase_return_detail", purchase_return_detail_page)
navigation.register("reports", reports_page)
navigation.register("activities_list", activities_page)
navigation.register("measurement_specs", measurement_specs_page)
navigation.register("order_workspace", order_workspace_page)
navigation.register("services_list", services_page)
navigation.register("workers_list", workers_page)
navigation.register("inventory_categories_list", inventory_categories_page)
navigation.register("inventory_products_list", inventory_products_page)
navigation.register("inventory_stock_list", inventory_stock_page)
navigation.register("inventory_stock_ledger_list", inventory_stock_ledger_page)
navigation.register("inventory_movements_list", inventory_movements_page)
navigation.register("inventory_customer_prices_list", inventory_customer_prices_page)
navigation.register("inventory_product_detail", inventory_product_detail_page)
navigation.register("export_backup", export_page)
navigation.register("business_settings", business_settings_page)
navigation.register("print_settings", print_settings_page)
navigation.register("keyboard_shortcuts", keyboard_shortcuts_page)
navigation.register("system_settings", system_settings_page)
navigation.register("system_updates", system_updates_page)
navigation.register("system_logs", system_logs_page)
navigation.register("migration_categories", migration_categories_page)
navigation.register("migration_products", migration_products_page)
navigation.register("migration_customers", migration_customers_page)
navigation.register("migration_vendors", migration_vendors_page)

page_groups = {
    "": [dashboard_page, mtd_page],
    "Parties": [
        customers_page,
        vendors_page,
        workers_page,
    ],
    "Boutique": [
        orders_list_page,
        measurements_page,
        items_page,
        time_page,
    ],
    "Sales": [
        sales_estimates_page,
        sales_quotations_page,
        sales_orders_page,
        sales_delivery_notes_page,
        sales_invoices_page,
        sales_returns_page,
    ],
    "Purchases": [
        purchase_orders_page,
        purchase_grn_page,
        purchase_bills_page,
        purchase_returns_page,
    ],
    "Inventory": [
        inventory_categories_page,
        inventory_products_page,
        inventory_stock_page,
        inventory_stock_ledger_page,
        inventory_movements_page,
        inventory_customer_prices_page,
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
    "Migration": [
        migration_categories_page,
        migration_products_page,
        migration_customers_page,
        migration_vendors_page,
    ],
    "Settings": [
        business_settings_page,
        print_settings_page,
        keyboard_shortcuts_page,
        activities_page,
        measurement_specs_page,
        services_page,
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
    order_workspace_page,
    item_detail_page,
    measurement_detail_page,
    customer_detail_page,
    vendor_detail_page,
    account_detail_page,
    sales_detail_page,
    sales_order_detail_page,
    sales_estimate_detail_page,
    sales_quotation_detail_page,
    sales_delivery_note_detail_page,
    sales_return_detail_page,
    inventory_product_detail_page,
    purchase_order_detail_page,
    purchase_grn_detail_page,
    purchase_detail_page,
    purchase_return_detail_page,
]

# All pages must be registered with st.navigation for routing to work.
nav_pages = {group: list(pages) for group, pages in page_groups.items()}
nav_pages["_hidden"] = hidden_pages

# Hide the built-in menu (Streamlit pins it to the very top of the sidebar) and
# draw our own below the branding so "VayBooks" sits on top.
nav = st.navigation(nav_pages, position="hidden")

with st.sidebar:
    st.markdown("## VayBooks")
    st.divider()
    for header, pages in page_groups.items():
        if header:
            st.caption(header)
        for page in pages:
            st.page_link(page)
    st.divider()
    st.caption(f"v{__version__}")

# Parents navigate here; action chords only set session flags for page render.
resolve_pressed_shortcuts()
nav.run()
