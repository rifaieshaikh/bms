import streamlit as st

from vaybooks.bms.version import __version__
from vaybooks.bms.infrastructure.config.runtime import is_desktop
from vaybooks.bms.infrastructure.logging.setup import setup_logging
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.bootstrap import get_services
from vaybooks.bms.ui.styles import inject_global_css
from vaybooks.bms.ui.pages.finance.accounts import list as accounts
from vaybooks.bms.ui.pages.settings.services import list as vendor_services
from vaybooks.bms.ui.pages.home.dashboard import list as dashboard
from vaybooks.bms.ui.pages.finance.export_backup import list as export_backup
from vaybooks.bms.ui.pages.finance.reports import list as reports
from vaybooks.bms.ui.pages.finance import overview as finance_overview_mod
from vaybooks.bms.ui.pages.parties.customers import list as customers
from vaybooks.bms.ui.pages.parties.customers import detail as customer_detail
from vaybooks.bms.ui.pages.parties.vendors import list as vendors
from vaybooks.bms.ui.pages.parties.vendors import detail as vendor_detail
from vaybooks.bms.ui.pages.parties.workers import list as workers
from vaybooks.bms.ui.pages.parties.segments import list as party_segments
from vaybooks.bms.ui.pages.settings.customization_activities import list as activities
from vaybooks.bms.ui.pages.settings.project_activities import list as project_activities_mod
from vaybooks.bms.ui.pages.boutique import overview as boutique_overview_mod
from vaybooks.bms.ui.pages.boutique import reports as boutique_reports_mod
from vaybooks.bms.ui.pages.boutique.orders import list as customization_orders_list
from vaybooks.bms.ui.pages.boutique.orders import detail as customization_order_detail
from vaybooks.bms.ui.pages.boutique.orders import orders as customization_orders
from vaybooks.bms.ui.pages.boutique.orders import workspace as order_workspace
from vaybooks.bms.ui.pages.boutique.items import list as customization_items
from vaybooks.bms.ui.pages.boutique.items import detail as customization_item_detail
from vaybooks.bms.ui.pages.boutique.measurements import list as measurements
from vaybooks.bms.ui.pages.boutique.measurements import detail as measurement_detail
from vaybooks.bms.ui.pages.boutique.time_log import list as time_tracking
from vaybooks.bms.ui.pages.boutique.calendar import list as boutique_calendar
from vaybooks.bms.ui.pages.finance.accounts import detail as account_detail
from vaybooks.bms.ui.pages.home.period_dashboard import list as mtd_dashboard
from vaybooks.bms.ui.pages.sales.invoices import detail as sales_detail
from vaybooks.bms.ui.pages.settings.measurement_specs import list as measurement_specs
from vaybooks.bms.ui.pages.sales.delivery_notes import detail as sales_delivery_note_detail_mod
from vaybooks.bms.ui.pages.sales.delivery_notes import list as sales_delivery_notes_mod
from vaybooks.bms.ui.pages.sales.estimates import detail as sales_estimate_detail_mod
from vaybooks.bms.ui.pages.sales.estimates import list as sales_estimates_mod
from vaybooks.bms.ui.pages.sales.invoices import list as sales_invoices_mod
from vaybooks.bms.ui.pages.sales.quotations import detail as sales_quotation_detail_mod
from vaybooks.bms.ui.pages.sales.quotations import list as sales_quotations_mod
from vaybooks.bms.ui.pages.sales.returns import detail as sales_return_detail_mod
from vaybooks.bms.ui.pages.sales.returns import list as sales_returns_mod
from vaybooks.bms.ui.pages.sales.orders import detail as sales_order_detail_mod
from vaybooks.bms.ui.pages.sales.orders import list as sales_orders_mod
from vaybooks.bms.ui.pages.sales import overview as sales_overview_mod
from vaybooks.bms.ui.pages.sales import reports as sales_reports_mod
from vaybooks.bms.ui.pages.inventory.categories import list as inventory_categories
from vaybooks.bms.ui.pages.inventory.warehouses import list as inventory_warehouses
from vaybooks.bms.ui.pages.inventory.customer_prices import list as inventory_customer_prices
from vaybooks.bms.ui.pages.inventory.movements import list as inventory_movements
from vaybooks.bms.ui.pages.inventory import overview as inventory_overview_mod
from vaybooks.bms.ui.pages.inventory.products import detail as inventory_product_detail
from vaybooks.bms.ui.pages.inventory.products import list as inventory_products
from vaybooks.bms.ui.pages.inventory import reports as inventory_reports_mod
from vaybooks.bms.ui.pages.inventory.stock_ledger import list as inventory_stock_ledger
from vaybooks.bms.ui.pages.inventory.stock_on_hand import list as inventory_stock_on_hand
from vaybooks.bms.ui.pages.inventory.transfers import list as inventory_transfers
from vaybooks.bms.ui.pages.inventory.transfers import detail as inventory_transfer_detail
from vaybooks.bms.ui.pages.settings.locations import list as settings_locations
from vaybooks.bms.ui.pages.purchases.bills import list as purchase_bills_mod
from vaybooks.bms.ui.pages.purchases.goods_receipt import list as purchase_goods_receipt_mod
from vaybooks.bms.ui.pages.purchases.goods_receipt import detail as purchase_grn_detail_mod
from vaybooks.bms.ui.pages.purchases.bills import detail as purchase_bill_detail_mod
from vaybooks.bms.ui.pages.purchases.orders import detail as purchase_order_detail_mod
from vaybooks.bms.ui.pages.purchases.orders import list as purchase_orders_mod
from vaybooks.bms.ui.pages.purchases import overview as purchases_overview_mod
from vaybooks.bms.ui.pages.purchases import reports as purchases_reports_mod
from vaybooks.bms.ui.pages.purchases.returns import detail as purchase_return_detail_mod
from vaybooks.bms.ui.pages.purchases.returns import list as purchase_returns_mod
from vaybooks.bms.ui.pages.system.settings import list as system_settings
from vaybooks.bms.ui.pages.system.logs import list as system_logs
from vaybooks.bms.ui.pages.system.updates import list as system_updates
from vaybooks.bms.ui.pages.settings.business import list as business_settings
from vaybooks.bms.ui.pages.settings.print import list as print_settings
from vaybooks.bms.ui.pages.settings.keyboard import list as keyboard_shortcuts
from vaybooks.bms.ui.pages.access.users import list as users_settings
from vaybooks.bms.ui.pages.access.roles import list as roles_settings
from vaybooks.bms.ui.pages.access.permissions import list as permissions_settings
from vaybooks.bms.ui.pages.access.audit_logs import list as audit_logs
from vaybooks.bms.ui.pages.access.feature_flags import list as feature_flags_settings
from vaybooks.bms.ui.pages.access.plans import list as plans_settings
from vaybooks.bms.ui.auth.session import (
    can_see_page,
    is_authenticated,
    sync_entitlement_cache,
    try_restore_session,
)
from vaybooks.bms.ui.auth.dialogs import open_sign_in_dialog_if_needed
from vaybooks.bms.ui.components.common.app_header import render_app_header
from vaybooks.bms.ui.auth.guard import require_page_access
from vaybooks.bms.ui.pages.migration import hub as data_migration
from vaybooks.bms.ui.keyboard.resolve import resolve_pressed_shortcuts
from vaybooks.bms.ui.keyboard.defaults import ensure_defaults_loaded
from vaybooks.bms.ui.pages.finance.accounting_invoices import list as accounting_invoices
from vaybooks.bms.ui.pages.finance.credit_notes import list as finance_credit_notes
from vaybooks.bms.ui.pages.finance.debit_notes import list as finance_debit_notes
from vaybooks.bms.ui.pages.finance.journal import list as finance_journal
from vaybooks.bms.ui.pages.finance.payments import list as finance_payments
from vaybooks.bms.ui.pages.finance.receipts import list as finance_receipts
from vaybooks.bms.ui.pages.finance.trial_balance import list as trial_balance
from vaybooks.bms.ui.pages.finance.vouchers import list as finance_vouchers
from vaybooks.bms.ui.pages.projects import (
    dashboard as projects_dashboard_mod,
    enquiries_list as project_enquiries_list_mod,
    enquiry_workspace as project_enquiry_workspace_mod,
    measurements_list as project_measurements_list_mod,
    portal as project_portal_mod,
    project_detail as project_detail_mod,
    project_workspace as project_workspace_mod,
    projects_list as projects_list_mod,
    ra_bills_list as project_ra_bills_list_mod,
    reports as projects_reports_mod,
    settings as projects_settings_mod,
    site_mobile as project_site_mobile_mod,
)

setup_logging()

st.set_page_config(
    page_title="VayBooks",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()
ensure_defaults_loaded(force=True)


def _page(module, *, url_path: str = "", require_auth: bool = True):
    """Wrap a page module so st.navigation can call it."""

    def render_page():
        services = get_services()
        if require_auth and url_path:
            if not require_page_access(services, url_path):
                return
        module.render(services)

    render_page.__name__ = module.__name__.rsplit(".", 1)[-1]
    return render_page


# --- Visible routes (rendered in the sidebar) --------------------------------
dashboard_page = st.Page(
    _page(dashboard, url_path="dashboard"), title="Dashboard", icon=":material/dashboard:",
    url_path="dashboard", default=True,
)
customers_page = st.Page(
    _page(customers, url_path="customers"), title="Customers", icon=":material/group:", url_path="customers",
)
vendors_page = st.Page(
    _page(vendors, url_path="vendors"), title="Vendors", icon=":material/local_shipping:",
    url_path="vendors",
)
boutique_overview_page = st.Page(
    _page(boutique_overview_mod, url_path="boutique-overview"), title="Overview",
    icon=":material/dashboard:", url_path="boutique-overview",
)
orders_list_page = st.Page(
    _page(customization_orders_list, url_path="customizationOrders"), title="Customization Orders",
    icon=":material/shopping_bag:", url_path="customizationOrders",
)
items_page = st.Page(
    _page(customization_items, url_path="customizationItems"), title="Customization Items",
    icon=":material/inventory_2:", url_path="customizationItems",
)
measurements_page = st.Page(
    _page(measurements, url_path="measurements"), title="Measurements",
    icon=":material/straighten:", url_path="measurements",
)
time_page = st.Page(
    _page(time_tracking, url_path="time"), title="Tasks", icon=":material/schedule:",
    url_path="time",
)
calendar_page = st.Page(
    _page(boutique_calendar, url_path="calendar"), title="Calendar", icon=":material/calendar_month:",
    url_path="calendar",
)
boutique_reports_page = st.Page(
    _page(boutique_reports_mod, url_path="boutique-reports"), title="Reports", icon=":material/analytics:",
    url_path="boutique-reports",
)
accounts_page = st.Page(
    _page(accounts, url_path="accounts"), title="Accounts", icon=":material/account_balance:",
    url_path="accounts",
)
finance_overview_page = st.Page(
    _page(finance_overview_mod, url_path="finance-overview"),
    title="Overview",
    icon=":material/dashboard:",
    url_path="finance-overview",
)
vouchers_page = st.Page(
    _page(finance_vouchers, url_path="vouchers"), title="Vouchers", icon=":material/receipt_long:",
    url_path="vouchers",
)
receipts_page = st.Page(
    _page(finance_receipts, url_path="receipts"), title="Receipts", icon=":material/payments:",
    url_path="receipts",
)
payments_page = st.Page(
    _page(finance_payments, url_path="payments"), title="Payments", icon=":material/send_money:",
    url_path="payments",
)
credit_notes_page = st.Page(
    _page(finance_credit_notes, url_path="credit-notes"), title="Credit Notes", icon=":material/credit_card:",
    url_path="credit-notes",
)
debit_notes_page = st.Page(
    _page(finance_debit_notes, url_path="debit-notes"), title="Debit Notes", icon=":material/receipt:",
    url_path="debit-notes",
)
accounting_invoices_page = st.Page(
    _page(accounting_invoices, url_path="accounting-invoices"), title="Accounting Invoices",
    icon=":material/request_quote:", url_path="accounting-invoices",
)
journal_page = st.Page(
    _page(finance_journal, url_path="journal"), title="Journal", icon=":material/menu_book:",
    url_path="journal",
)
trial_balance_page = st.Page(
    _page(trial_balance, url_path="trial-balance"), title="Trial Balance", icon=":material/balance:",
    url_path="trial-balance",
)
mtd_page = st.Page(
    _page(mtd_dashboard, url_path="mtd-dashboard"), title="Period Dashboard", icon=":material/calendar_month:",
    url_path="mtd-dashboard",
)
sales_overview_page = st.Page(
    _page(sales_overview_mod, url_path="sales-overview"),
    title="Overview",
    icon=":material/dashboard:",
    url_path="sales-overview",
)
sales_estimates_page = st.Page(
    _page(sales_estimates_mod, url_path="estimates"), title="Estimates", icon=":material/request_quote:",
    url_path="estimates",
)
sales_quotations_page = st.Page(
    _page(sales_quotations_mod, url_path="quotations"), title="Quotations", icon=":material/description:",
    url_path="quotations",
)
sales_orders_page = st.Page(
    _page(sales_orders_mod, url_path="sales-orders"), title="Sales Orders", icon=":material/assignment:",
    url_path="sales-orders",
)
sales_delivery_notes_page = st.Page(
    _page(sales_delivery_notes_mod, url_path="delivery-notes"), title="Delivery Notes", icon=":material/local_shipping:",
    url_path="delivery-notes",
)
sales_invoices_page = st.Page(
    _page(sales_invoices_mod, url_path="sales"), title="Sales Invoices", icon=":material/point_of_sale:",
    url_path="sales",
)
sales_returns_page = st.Page(
    _page(sales_returns_mod, url_path="sales-returns"), title="Sales Returns", icon=":material/undo:",
    url_path="sales-returns",
)
sales_reports_page = st.Page(
    _page(sales_reports_mod, url_path="sales-reports"),
    title="Reports",
    icon=":material/analytics:",
    url_path="sales-reports",
)
purchases_overview_page = st.Page(
    _page(purchases_overview_mod, url_path="purchases-overview"),
    title="Overview",
    icon=":material/dashboard:",
    url_path="purchases-overview",
)
purchase_orders_page = st.Page(
    _page(purchase_orders_mod, url_path="purchase-orders"), title="Purchase Orders", icon=":material/shopping_cart:",
    url_path="purchase-orders",
)
purchase_grn_page = st.Page(
    _page(purchase_goods_receipt_mod, url_path="goods-receipt"), title="Goods Receipt", icon=":material/inventory:",
    url_path="goods-receipt",
)
purchase_bills_page = st.Page(
    _page(purchase_bills_mod, url_path="purchases"), title="Purchase Bills", icon=":material/receipt:",
    url_path="purchases",
)
purchase_returns_page = st.Page(
    _page(purchase_returns_mod, url_path="purchase-returns"), title="Returns", icon=":material/undo:",
    url_path="purchase-returns",
)
purchases_reports_page = st.Page(
    _page(purchases_reports_mod, url_path="purchases-reports"),
    title="Reports",
    icon=":material/analytics:",
    url_path="purchases-reports",
)
reports_page = st.Page(
    _page(reports, url_path="reports"), title="Reports", icon=":material/analytics:", url_path="reports",
)
export_page = st.Page(
    _page(export_backup, url_path="export-backup"), title="Export / Backup", icon=":material/download:",
    url_path="export-backup",
)
data_migration_page = st.Page(
    _page(data_migration, url_path="data-migration"), title="Data Migration", icon=":material/upload_file:",
    url_path="data-migration",
)
activities_page = st.Page(
    _page(activities, url_path="customization-activities"), title="Customization Activities", icon=":material/checklist:",
    url_path="customization-activities",
)
project_activities_page = st.Page(
    _page(project_activities_mod, url_path="project-activities"), title="Project Activities", icon=":material/checklist:",
    url_path="project-activities",
)
measurement_specs_page = st.Page(
    _page(measurement_specs, url_path="measurement-specs"), title="Measurement Specs", icon=":material/straighten:",
    url_path="measurement-specs",
)
order_workspace_page = st.Page(
    _page(order_workspace, url_path="order-workspace"), title="Order Workspace", icon=":material/edit_note:",
    url_path="order-workspace",
)
services_page = st.Page(
    _page(vendor_services, url_path="services"), title="Service Configuration", icon=":material/category:",
    url_path="services",
)
workers_page = st.Page(
    _page(workers, url_path="employees"), title="Employees", icon=":material/badge:", url_path="employees",
)
party_segments_page = st.Page(
    _page(party_segments, url_path="party-segments"), title="Segments", icon=":material/label:",
    url_path="party-segments",
)
projects_dashboard_page = st.Page(
    _page(projects_dashboard_mod, url_path="projects-dashboard"), title="Overview", icon=":material/dashboard:",
    url_path="projects-dashboard",
)
projects_list_page = st.Page(
    _page(projects_list_mod, url_path="projects"), title="Projects", icon=":material/apartment:",
    url_path="projects",
)
project_enquiries_list_page = st.Page(
    _page(project_enquiries_list_mod, url_path="project-enquiries"), title="Enquiries",
    icon=":material/contact_mail:", url_path="project-enquiries",
)
project_measurements_list_page = st.Page(
    _page(project_measurements_list_mod, url_path="project-measurements"), title="Measurements",
    icon=":material/straighten:", url_path="project-measurements",
)
project_ra_bills_list_page = st.Page(
    _page(project_ra_bills_list_mod, url_path="project-ra-bills"), title="RA Bills",
    icon=":material/receipt_long:", url_path="project-ra-bills",
)
project_enquiry_workspace_page = st.Page(
    _page(project_enquiry_workspace_mod, url_path="project-enquiry-workspace"), title="Enquiry Workspace",
    icon=":material/edit_note:", url_path="project-enquiry-workspace",
)
projects_reports_page = st.Page(
    _page(projects_reports_mod, url_path="projects-reports"), title="Reports", icon=":material/analytics:",
    url_path="projects-reports",
)
projects_settings_page = st.Page(
    _page(projects_settings_mod, url_path="projects-settings"), title="Settings", icon=":material/settings:",
    url_path="projects-settings",
)
project_workspace_page = st.Page(
    _page(project_workspace_mod, url_path="project-workspace"), title="Project Workspace", icon=":material/edit_note:",
    url_path="project-workspace",
)
project_detail_page = st.Page(
    _page(project_detail_mod, url_path="project-detail"), title="Project Detail", url_path="project-detail",
)
project_site_mobile_page = st.Page(
    _page(project_site_mobile_mod, url_path="project-site-mobile"),
    title="Site Mobile",
    url_path="project-site-mobile",
)
project_portal_page = st.Page(
    _page(project_portal_mod, url_path="project-portal"), title="Project Portal", url_path="project-portal",
)
inventory_overview_page = st.Page(
    _page(inventory_overview_mod, url_path="inventory-overview"),
    title="Overview",
    icon=":material/analytics:",
    url_path="inventory-overview",
)
inventory_categories_page = st.Page(
    _page(inventory_categories, url_path="inventory-categories"), title="Categories", icon=":material/category:",
    url_path="inventory-categories",
)
inventory_warehouses_page = st.Page(
    _page(inventory_warehouses, url_path="inventory-warehouses"), title="Warehouses", icon=":material/warehouse:",
    url_path="inventory-warehouses",
)
inventory_products_page = st.Page(
    _page(inventory_products, url_path="inventory-products"), title="Products", icon=":material/inventory:",
    url_path="inventory-products",
)
inventory_stock_page = st.Page(
    _page(inventory_stock_on_hand, url_path="inventory-stock"), title="Stock on Hand",
    icon=":material/warehouse:", url_path="inventory-stock",
)
inventory_stock_ledger_page = st.Page(
    _page(inventory_stock_ledger, url_path="inventory-stock-ledger"), title="Stock Ledger",
    icon=":material/receipt_long:", url_path="inventory-stock-ledger",
)
inventory_movements_page = st.Page(
    _page(inventory_movements, url_path="inventory-movements"), title="Movements", icon=":material/swap_horiz:",
    url_path="inventory-movements",
)
inventory_customer_prices_page = st.Page(
    _page(inventory_customer_prices, url_path="inventory-customer-prices"), title="Customer Prices",
    icon=":material/sell:", url_path="inventory-customer-prices",
)
inventory_transfers_page = st.Page(
    _page(inventory_transfers, url_path="inventory-transfers"), title="Transfers",
    icon=":material/sync_alt:", url_path="inventory-transfers",
)
inventory_transfer_detail_page = st.Page(
    _page(inventory_transfer_detail, url_path="inventory-transfer-detail"), title="Transfer Detail",
    url_path="inventory-transfer-detail",
)
settings_locations_page = st.Page(
    _page(settings_locations, url_path="settings-locations"), title="Locations",
    icon=":material/store:", url_path="settings-locations",
)
inventory_reports_page = st.Page(
    _page(inventory_reports_mod, url_path="inventory-reports"),
    title="Reports",
    icon=":material/assessment:",
    url_path="inventory-reports",
)
purchase_order_detail_page = st.Page(
    _page(purchase_order_detail_mod, url_path="purchase-order-detail"), title="PO Detail", url_path="purchase-order-detail",
)
purchase_grn_detail_page = st.Page(
    _page(purchase_grn_detail_mod, url_path="grn-detail"), title="GRN Detail", url_path="grn-detail",
)
purchase_detail_page = st.Page(
    _page(purchase_bill_detail_mod, url_path="purchase-detail"), title="Purchase Detail", url_path="purchase-detail",
)
purchase_return_detail_page = st.Page(
    _page(purchase_return_detail_mod, url_path="purchase-return-detail"),
    title="Purchase Return Detail",
    url_path="purchase-return-detail",
)

system_settings_page = st.Page(
    _page(system_settings, url_path="system-settings"), title="System", icon=":material/settings:",
    url_path="system-settings",
)
business_settings_page = st.Page(
    _page(business_settings, url_path="business-settings"), title="Business", icon=":material/store:",
    url_path="business-settings",
)
print_settings_page = st.Page(
    _page(print_settings, url_path="print-settings"), title="Print Settings", icon=":material/print:",
    url_path="print-settings",
)
keyboard_shortcuts_page = st.Page(
    _page(keyboard_shortcuts, url_path="keyboard-shortcuts"), title="Keyboard Shortcuts",
    icon=":material/keyboard:", url_path="keyboard-shortcuts",
)
users_settings_page = st.Page(
    _page(users_settings, url_path="users-settings"), title="Users",
    icon=":material/manage_accounts:", url_path="users-settings",
)
roles_settings_page = st.Page(
    _page(roles_settings, url_path="roles-settings"), title="Roles",
    icon=":material/badge:", url_path="roles-settings",
)
permissions_settings_page = st.Page(
    _page(permissions_settings, url_path="permissions-settings"), title="Permissions",
    icon=":material/lock_person:", url_path="permissions-settings",
)
audit_logs_page = st.Page(
    _page(audit_logs, url_path="audit-logs"), title="Audit Logs",
    icon=":material/history:", url_path="audit-logs",
)
feature_flags_settings_page = st.Page(
    _page(feature_flags_settings, url_path="feature-flags-settings"), title="Feature Flags",
    icon=":material/toggle_on:", url_path="feature-flags-settings",
)
plans_settings_page = st.Page(
    _page(plans_settings, url_path="plans-settings"), title="Plans",
    icon=":material/workspace_premium:", url_path="plans-settings",
)
system_updates_page = st.Page(
    _page(system_updates, url_path="system-updates"), title="Updates", icon=":material/system_update:",
    url_path="system-updates",
)
system_logs_page = st.Page(
    _page(system_logs, url_path="system-logs"), title="Logs", icon=":material/article:",
    url_path="system-logs",
)

# --- Hidden detail routes (deep-linkable, not in sidebar) --------------------
order_detail_page = st.Page(
    _page(customization_order_detail, url_path="order-detail"), title="Order Detail", url_path="order-detail",
)
item_detail_page = st.Page(
    _page(customization_item_detail, url_path="item-detail"), title="Item Detail", url_path="item-detail",
)
measurement_detail_page = st.Page(
    _page(measurement_detail, url_path="measurement-detail"), title="Measurement Detail",
    url_path="measurement-detail",
)
customer_detail_page = st.Page(
    _page(customer_detail, url_path="customer-detail"), title="Customer Detail", url_path="customer-detail",
)
vendor_detail_page = st.Page(
    _page(vendor_detail, url_path="vendor-detail"), title="Vendor Detail", url_path="vendor-detail",
)
account_detail_page = st.Page(
    _page(account_detail, url_path="account-detail"), title="Account Detail", url_path="account-detail",
)
sales_detail_page = st.Page(
    _page(sales_detail, url_path="sales-detail"), title="Sale Detail", url_path="sales-detail",
)
sales_order_detail_page = st.Page(
    _page(sales_order_detail_mod, url_path="sales-order-detail"), title="SO Detail", url_path="sales-order-detail",
)
sales_estimate_detail_page = st.Page(
    _page(sales_estimate_detail_mod, url_path="estimate-detail"), title="Estimate Detail",
    url_path="estimate-detail",
)
sales_quotation_detail_page = st.Page(
    _page(sales_quotation_detail_mod, url_path="quotation-detail"), title="Quotation Detail",
    url_path="quotation-detail",
)
sales_delivery_note_detail_page = st.Page(
    _page(sales_delivery_note_detail_mod, url_path="delivery-note-detail"), title="DN Detail", url_path="delivery-note-detail",
)
sales_return_detail_page = st.Page(
    _page(sales_return_detail_mod, url_path="sales-return-detail"), title="Sales Return Detail",
    url_path="sales-return-detail",
)
inventory_product_detail_page = st.Page(
    _page(inventory_product_detail, url_path="inventory-product-detail"), title="Product Detail",
    url_path="inventory-product-detail",
)

# --- Navigation registry (used by go_to_detail / go_back_to_list) ------------
navigation.register("dashboard", dashboard_page)
navigation.register("customers_list", customers_page)
navigation.register("vendors_list", vendors_page)
navigation.register("boutique_overview", boutique_overview_page)
navigation.register("boutique_reports", boutique_reports_page)
navigation.register("orders_list", orders_list_page)
navigation.register("order_detail", order_detail_page)
navigation.register("items_list", items_page)
navigation.register("item_detail", item_detail_page)
navigation.register("measurements_list", measurements_page)
navigation.register("measurement_detail", measurement_detail_page)
navigation.register("customer_detail", customer_detail_page)
navigation.register("vendor_detail", vendor_detail_page)
navigation.register("time_list", time_page)
navigation.register("calendar_list", calendar_page)
navigation.register("finance_overview", finance_overview_page)
navigation.register("accounts_list", accounts_page)
navigation.register("account_detail", account_detail_page)
navigation.register("vouchers_list", vouchers_page)
navigation.register("receipts_list", receipts_page)
navigation.register("payments_list", payments_page)
navigation.register("credit_notes_list", credit_notes_page)
navigation.register("debit_notes_list", debit_notes_page)
navigation.register("accounting_invoices_list", accounting_invoices_page)
navigation.register("journal_list", journal_page)
navigation.register("trial_balance_list", trial_balance_page)
navigation.register("mtd_dashboard", mtd_page)
navigation.register("sales_overview", sales_overview_page)
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
navigation.register("sales_reports", sales_reports_page)
navigation.register("purchases_overview", purchases_overview_page)
navigation.register("purchase_orders_list", purchase_orders_page)
navigation.register("purchase_order_detail", purchase_order_detail_page)
navigation.register("goods_receipt_list", purchase_grn_page)
navigation.register("grn_detail", purchase_grn_detail_page)
navigation.register("purchases_list", purchase_bills_page)
navigation.register("purchase_detail", purchase_detail_page)
navigation.register("purchase_returns_list", purchase_returns_page)
navigation.register("purchase_return_detail", purchase_return_detail_page)
navigation.register("purchases_reports", purchases_reports_page)
navigation.register("reports", reports_page)
navigation.register("customization_activities_list", activities_page)
navigation.register("activities_list", activities_page)  # legacy alias
navigation.register("project_activities_list", project_activities_page)
navigation.register("measurement_specs", measurement_specs_page)
navigation.register("order_workspace", order_workspace_page)
navigation.register("services_list", services_page)
navigation.register("workers_list", workers_page)
navigation.register("segments_list", party_segments_page)
navigation.register("projects_dashboard", projects_dashboard_page)
navigation.register("projects_list", projects_list_page)
navigation.register("project_enquiries_list", project_enquiries_list_page)
navigation.register("project_measurements_list", project_measurements_list_page)
navigation.register("project_ra_bills_list", project_ra_bills_list_page)
navigation.register("project_enquiry_workspace", project_enquiry_workspace_page)
navigation.register("projects_reports", projects_reports_page)
navigation.register("projects_settings", projects_settings_page)
navigation.register("project_workspace", project_workspace_page)
navigation.register("project_detail", project_detail_page)
navigation.register("project_site_mobile", project_site_mobile_page)
navigation.register("project_portal", project_portal_page)
navigation.register("inventory_overview", inventory_overview_page)
navigation.register("inventory_categories_list", inventory_categories_page)
navigation.register("inventory_warehouses_list", inventory_warehouses_page)
navigation.register("inventory_products_list", inventory_products_page)
navigation.register("inventory_stock_list", inventory_stock_page)
navigation.register("inventory_stock_ledger_list", inventory_stock_ledger_page)
navigation.register("inventory_movements_list", inventory_movements_page)
navigation.register("inventory_customer_prices_list", inventory_customer_prices_page)
navigation.register("inventory_transfers_list", inventory_transfers_page)
navigation.register("inventory_transfer_detail", inventory_transfer_detail_page)
navigation.register("inventory_reports", inventory_reports_page)
navigation.register("inventory_product_detail", inventory_product_detail_page)
navigation.register("settings_locations_list", settings_locations_page)
navigation.register("export_backup", export_page)
navigation.register("business_settings", business_settings_page)
navigation.register("print_settings", print_settings_page)
navigation.register("keyboard_shortcuts", keyboard_shortcuts_page)
navigation.register("users_settings", users_settings_page)
navigation.register("roles_settings", roles_settings_page)
navigation.register("permissions_settings", permissions_settings_page)
navigation.register("audit_logs", audit_logs_page)
navigation.register("feature_flags_settings", feature_flags_settings_page)
navigation.register("plans_settings", plans_settings_page)
navigation.register("system_settings", system_settings_page)
navigation.register("system_updates", system_updates_page)
navigation.register("system_logs", system_logs_page)
navigation.register("data_migration", data_migration_page)

page_groups = {
    "": [dashboard_page, mtd_page],
    "Parties": [
        customers_page,
        vendors_page,
        workers_page,
        party_segments_page,
    ],
    "Boutique": [
        boutique_overview_page,
        orders_list_page,
        measurements_page,
        items_page,
        time_page,
        calendar_page,
        boutique_reports_page,
    ],
    "Projects": [
        projects_dashboard_page,
        project_enquiries_list_page,
        projects_list_page,
        project_measurements_list_page,
        project_ra_bills_list_page,
        projects_reports_page,
        projects_settings_page,
    ],
    "Sales": [
        sales_overview_page,
        sales_estimates_page,
        sales_quotations_page,
        sales_orders_page,
        sales_delivery_notes_page,
        sales_invoices_page,
        sales_returns_page,
        sales_reports_page,
    ],
    "Purchases": [
        purchases_overview_page,
        purchase_orders_page,
        purchase_grn_page,
        purchase_bills_page,
        purchase_returns_page,
        purchases_reports_page,
    ],
    "Inventory": [
        inventory_overview_page,
        inventory_categories_page,
        inventory_products_page,
        inventory_stock_page,
        inventory_stock_ledger_page,
        inventory_movements_page,
        inventory_transfers_page,
        inventory_customer_prices_page,
        inventory_reports_page,
    ],
    "Finance": [
        finance_overview_page,
        accounts_page,
        vouchers_page,
        receipts_page,
        payments_page,
        credit_notes_page,
        debit_notes_page,
        accounting_invoices_page,
        journal_page,
        trial_balance_page,
        reports_page,
        export_page,
    ],
    "Migration": [
        data_migration_page,
    ],
    "Access": [
        users_settings_page,
        roles_settings_page,
        permissions_settings_page,
        audit_logs_page,
        plans_settings_page,
        feature_flags_settings_page,
    ],
    "Settings": [
        business_settings_page,
        settings_locations_page,
        print_settings_page,
        keyboard_shortcuts_page,
        activities_page,
        project_activities_page,
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
    project_detail_page,
    project_workspace_page,
    project_enquiry_workspace_page,
    project_site_mobile_page,
    project_portal_page,
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
    inventory_transfer_detail_page,
    inventory_warehouses_page,
    purchase_order_detail_page,
    purchase_grn_detail_page,
    purchase_detail_page,
    purchase_return_detail_page,
]

# All pages must be registered with st.navigation for routing to work.
_services = get_services()
try_restore_session(_services)
sync_entitlement_cache(_services)

if not is_authenticated():
    with st.sidebar:
        st.markdown("## VayBooks")
        st.divider()
        st.caption("Sign in to continue")
        st.caption(f"v{__version__}")
    st.markdown("## Welcome to VayBooks")
    st.caption("Please sign in to continue.")
    if st.button("Sign in", type="primary"):
        st.session_state["signin_dialog_open"] = True
    open_sign_in_dialog_if_needed(_services)
else:
    # Settings / Access / Migration stay registered with st.navigation (deep
    # links keep working) but are surfaced from the header gear popover.
    visible_groups = {}
    for group, pages in page_groups.items():
        if group in ("Settings", "Access", "Migration"):
            continue
        visible = [
            p
            for p in pages
            if can_see_page(_services, getattr(p, "url_path", "") or "")
        ]
        if visible:
            visible_groups[group] = visible

    nav_pages = {group: list(pages) for group, pages in page_groups.items()}
    nav_pages["_hidden"] = list(hidden_pages)

    # Hide the built-in menu (Streamlit pins it to the very top of the sidebar) and
    # draw our own below the branding so "VayBooks" sits on top.
    nav = st.navigation(nav_pages, position="hidden")

    with st.sidebar:
        st.markdown("## VayBooks")
        st.divider()
        for header, pages in visible_groups.items():
            if header:
                st.caption(header)
            for page in pages:
                st.page_link(page)
        st.divider()
        st.caption(f"v{__version__}")

    render_app_header(
        _services,
        settings_pages=page_groups["Settings"],
        access_pages=page_groups["Access"],
        migration_pages=page_groups["Migration"],
    )

    # Parents navigate here; action chords only set session flags for page render.
    resolve_pressed_shortcuts()
    nav.run()
