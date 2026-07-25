"""Source-of-truth feature, permission, plan, and system-role catalogs."""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Set, Tuple

# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------

MODULE_CORE = "core"
MODULE_PARTIES = "parties"
MODULE_BOUTIQUE = "boutique"
MODULE_PROJECTS = "projects"
MODULE_SALES = "sales"
MODULE_PURCHASES = "purchases"
MODULE_INVENTORY = "inventory"
MODULE_FINANCE = "finance"
MODULE_MIGRATION = "migration"
MODULE_SETTINGS = "settings"
MODULE_SYSTEM = "system"

ALL_MODULES: Tuple[str, ...] = (
    MODULE_CORE,
    MODULE_PARTIES,
    MODULE_BOUTIQUE,
    MODULE_PROJECTS,
    MODULE_SALES,
    MODULE_PURCHASES,
    MODULE_INVENTORY,
    MODULE_FINANCE,
    MODULE_MIGRATION,
    MODULE_SETTINGS,
    MODULE_SYSTEM,
)

MODULE_KEYS: Tuple[str, ...] = tuple(f"module.{m}" for m in ALL_MODULES)

MODULE_LABELS: Dict[str, str] = {
    MODULE_CORE: "Core",
    MODULE_PARTIES: "Parties",
    MODULE_BOUTIQUE: "Boutique",
    MODULE_PROJECTS: "Projects",
    MODULE_SALES: "Sales",
    MODULE_PURCHASES: "Purchases",
    MODULE_INVENTORY: "Inventory",
    MODULE_FINANCE: "Finance",
    MODULE_MIGRATION: "Migration",
    MODULE_SETTINGS: "Settings",
    MODULE_SYSTEM: "System",
}


def module_key(module: str) -> str:
    return f"module.{module}"


def permission_module(permission: str) -> str:
    if permission.startswith("module."):
        return permission.split(".", 1)[1]
    return permission.split(".", 1)[0]


# ---------------------------------------------------------------------------
# Permissions (concrete)
# ---------------------------------------------------------------------------

def _expand(base: str, actions: Iterable[str]) -> List[str]:
    return [f"{base}.{a}" for a in actions]


PERMISSIONS: Tuple[str, ...] = tuple(
    [
        # Core
        "core.dashboard.view",
        "core.mtd.view",
        # Parties
        *_expand("parties.customers", ("view", "create", "edit")),
        *_expand("parties.vendors", ("view", "create", "edit")),
        *_expand("parties.employees", ("view", "create", "edit")),
        *_expand("parties.segments", ("view", "edit")),
        # Boutique
        "boutique.overview.view",
        *_expand("boutique.orders", ("view", "create", "edit")),
        *_expand("boutique.measurements", ("view", "edit")),
        *_expand("boutique.items", ("view", "edit")),
        *_expand("boutique.tasks", ("view", "edit")),
        "boutique.calendar.view",
        "boutique.reports.view",
        # Projects
        "projects.overview.view",
        *_expand("projects.enquiries", ("view", "create", "edit")),
        *_expand("projects.projects", ("view", "create", "edit")),
        *_expand("projects.measurements", ("view", "edit")),
        *_expand("projects.ra_bills", ("view", "create", "approve")),
        "projects.reports.view",
        *_expand("projects.settings", ("view", "edit")),
        "projects.cost.view_internal",
        "projects.commercial.approve",
        "projects.site_mobile.view",
        "projects.portal.manage",
        # Sales
        "sales.overview.view",
        *_expand("sales.estimates", ("view", "create", "edit")),
        *_expand("sales.quotations", ("view", "create", "edit", "approve")),
        *_expand("sales.orders", ("view", "create", "edit")),
        *_expand("sales.delivery_notes", ("view", "create", "edit")),
        *_expand("sales.invoices", ("view", "create", "edit")),
        *_expand("sales.returns", ("view", "create", "edit")),
        "sales.reports.view",
        # Purchases
        "purchases.overview.view",
        *_expand("purchases.orders", ("view", "create", "edit")),
        *_expand("purchases.grn", ("view", "create", "edit")),
        *_expand("purchases.bills", ("view", "create", "edit")),
        *_expand("purchases.returns", ("view", "create", "edit")),
        "purchases.reports.view",
        # Inventory
        "inventory.overview.view",
        *_expand("inventory.categories", ("view", "edit")),
        *_expand("inventory.warehouses", ("view", "edit")),
        *_expand("inventory.products", ("view", "create", "edit")),
        "inventory.stock.view",
        "inventory.stock_ledger.view",
        *_expand("inventory.movements", ("view", "create")),
        *_expand("inventory.customer_prices", ("view", "edit")),
        *_expand("inventory.transfers", ("view", "create")),
        "inventory.reports.view",
        # Finance
        "finance.overview.view",
        *_expand("finance.accounts", ("view", "edit")),
        *_expand("finance.vouchers", ("view", "create", "edit")),
        *_expand("finance.receipts", ("view", "create", "edit")),
        *_expand("finance.payments", ("view", "create", "edit")),
        *_expand("finance.credit_notes", ("view", "create", "edit")),
        *_expand("finance.debit_notes", ("view", "create", "edit")),
        *_expand("finance.accounting_invoices", ("view", "create", "edit")),
        *_expand("finance.journal", ("view", "create")),
        "finance.trial_balance.view",
        "finance.reports.view",
        "finance.export.view",
        # Migration
        "migration.run",
        # Settings
        *_expand("settings.business", ("view", "edit")),
        *_expand("settings.print", ("view", "edit")),
        *_expand("settings.keyboard", ("view", "edit")),
        *_expand("settings.customization_activities", ("view", "edit")),
        *_expand("settings.project_activities", ("view", "edit")),
        *_expand("settings.measurement_specs", ("view", "edit")),
        *_expand("settings.services", ("view", "edit")),
        *_expand("settings.users", ("view", "manage")),
        *_expand("settings.roles", ("view", "manage")),
        "settings.permissions.view",
        "settings.audit.view",
        *_expand("settings.feature_flags", ("view", "manage")),
        *_expand("settings.plans", ("view", "manage")),
        # System
        *_expand("system.settings", ("view", "edit")),
        "system.updates.view",
        "system.logs.view",
    ]
)

ALL_FEATURE_KEYS: FrozenSet[str] = frozenset(MODULE_KEYS) | frozenset(PERMISSIONS)


def permissions_for_module(module: str) -> FrozenSet[str]:
    return frozenset(p for p in PERMISSIONS if permission_module(p) == module)


def expand_modules(modules: Iterable[str]) -> FrozenSet[str]:
    """Module ids → module.* keys + all concrete permissions under those modules."""
    out: Set[str] = set()
    for m in modules:
        m = (m or "").strip()
        if not m:
            continue
        out.add(module_key(m))
        out.update(permissions_for_module(m))
    return frozenset(out)


def match_prefix(keys: Iterable[str], pattern: str) -> FrozenSet[str]:
    """Expand patterns like ``core.*`` or ``sales.quotations.*`` against ALL permissions."""
    if pattern.endswith(".*"):
        prefix = pattern[:-1]  # keep trailing dot
        return frozenset(k for k in keys if k.startswith(prefix) or k == pattern[:-2])
    return frozenset([pattern]) if pattern in set(keys) else frozenset()


def resolve_permission_patterns(patterns: Iterable[str]) -> FrozenSet[str]:
    resolved: Set[str] = set()
    for pat in patterns:
        if pat.endswith(".*"):
            resolved.update(match_prefix(PERMISSIONS, pat))
        elif pat in ALL_FEATURE_KEYS:
            resolved.add(pat)
    return frozenset(resolved)


# ---------------------------------------------------------------------------
# Page → permission
# ---------------------------------------------------------------------------

PAGE_PERMISSIONS: Dict[str, str] = {
    "dashboard": "core.dashboard.view",
    "mtd-dashboard": "core.mtd.view",
    "customers": "parties.customers.view",
    "customer-detail": "parties.customers.view",
    "vendors": "parties.vendors.view",
    "vendor-detail": "parties.vendors.view",
    "employees": "parties.employees.view",
    "party-segments": "parties.segments.view",
    "boutique-overview": "boutique.overview.view",
    "customizationOrders": "boutique.orders.view",
    "order-detail": "boutique.orders.view",
    "order-workspace": "boutique.orders.view",
    "measurements": "boutique.measurements.view",
    "measurement-detail": "boutique.measurements.view",
    "customizationItems": "boutique.items.view",
    "item-detail": "boutique.items.view",
    "time": "boutique.tasks.view",
    "calendar": "boutique.calendar.view",
    "boutique-reports": "boutique.reports.view",
    "projects-dashboard": "projects.overview.view",
    "project-enquiries": "projects.enquiries.view",
    "project-enquiry-workspace": "projects.enquiries.view",
    "projects": "projects.projects.view",
    "project-detail": "projects.projects.view",
    "project-workspace": "projects.projects.view",
    "project-measurements": "projects.measurements.view",
    "project-ra-bills": "projects.ra_bills.view",
    "projects-reports": "projects.reports.view",
    "projects-settings": "projects.settings.view",
    "project-site-mobile": "projects.site_mobile.view",
    "project-portal": "projects.portal.manage",
    "sales-overview": "sales.overview.view",
    "estimates": "sales.estimates.view",
    "estimate-detail": "sales.estimates.view",
    "quotations": "sales.quotations.view",
    "quotation-detail": "sales.quotations.view",
    "sales-orders": "sales.orders.view",
    "sales-order-detail": "sales.orders.view",
    "delivery-notes": "sales.delivery_notes.view",
    "delivery-note-detail": "sales.delivery_notes.view",
    "sales": "sales.invoices.view",
    "sales-detail": "sales.invoices.view",
    "sales-returns": "sales.returns.view",
    "sales-return-detail": "sales.returns.view",
    "sales-reports": "sales.reports.view",
    "purchases-overview": "purchases.overview.view",
    "purchase-orders": "purchases.orders.view",
    "purchase-order-detail": "purchases.orders.view",
    "goods-receipt": "purchases.grn.view",
    "grn-detail": "purchases.grn.view",
    "purchases": "purchases.bills.view",
    "purchase-detail": "purchases.bills.view",
    "purchase-returns": "purchases.returns.view",
    "purchase-return-detail": "purchases.returns.view",
    "purchases-reports": "purchases.reports.view",
    "inventory-overview": "inventory.overview.view",
    "inventory-categories": "inventory.categories.view",
    "inventory-warehouses": "inventory.warehouses.view",
    "inventory-products": "inventory.products.view",
    "inventory-product-detail": "inventory.products.view",
    "inventory-stock": "inventory.stock.view",
    "inventory-stock-ledger": "inventory.stock_ledger.view",
    "inventory-movements": "inventory.movements.view",
    "inventory-customer-prices": "inventory.customer_prices.view",
    "inventory-transfers": "inventory.transfers.view",
    "inventory-transfer-detail": "inventory.transfers.view",
    "inventory-reports": "inventory.reports.view",
    "settings-locations": "inventory.warehouses.view",
    "finance-overview": "finance.overview.view",
    "accounts": "finance.accounts.view",
    "account-detail": "finance.accounts.view",
    "vouchers": "finance.vouchers.view",
    "receipts": "finance.receipts.view",
    "payments": "finance.payments.view",
    "credit-notes": "finance.credit_notes.view",
    "debit-notes": "finance.debit_notes.view",
    "accounting-invoices": "finance.accounting_invoices.view",
    "journal": "finance.journal.view",
    "trial-balance": "finance.trial_balance.view",
    "reports": "finance.reports.view",
    "export-backup": "finance.export.view",
    "data-migration": "migration.run",
    "migration-categories": "migration.run",
    "migration-products": "migration.run",
    "migration-customers": "migration.run",
    "migration-vendors": "migration.run",
    "business-settings": "settings.business.view",
    "print-settings": "settings.print.view",
    "keyboard-shortcuts": "settings.keyboard.view",
    "customization-activities": "settings.customization_activities.view",
    "project-activities": "settings.project_activities.view",
    "measurement-specs": "settings.measurement_specs.view",
    "services": "settings.services.view",
    "users-settings": "settings.users.view",
    "roles-settings": "settings.roles.view",
    "permissions-settings": "settings.permissions.view",
    "audit-logs": "settings.audit.view",
    "feature-flags-settings": "settings.feature_flags.view",
    "plans-settings": "settings.plans.view",
    "system-settings": "system.settings.view",
    "system-updates": "system.updates.view",
    "system-logs": "system.logs.view",
}


def permission_for_page(url_path: str) -> str:
    return PAGE_PERMISSIONS.get((url_path or "").strip(), "")


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

PLAN_STARTER = "starter"
PLAN_GROWTH = "growth"
PLAN_ENTERPRISE = "enterprise"

_STARTER_MODULES = (
    MODULE_CORE,
    MODULE_PARTIES,
    MODULE_SALES,
    MODULE_PURCHASES,
    MODULE_INVENTORY,
    MODULE_FINANCE,
    MODULE_SETTINGS,
)

_STARTER_EXCLUDE_PREFIXES = (
    "settings.feature_flags.",
    "settings.plans.",
)
_STARTER_EXCLUDE_SUFFIXES = (".approve",)


def _starter_feature_keys() -> FrozenSet[str]:
    keys = set(expand_modules(_STARTER_MODULES))
    keys = {
        k
        for k in keys
        if not any(k.startswith(p) for p in _STARTER_EXCLUDE_PREFIXES)
        and not any(k.endswith(s) for s in _STARTER_EXCLUDE_SUFFIXES)
    }
    return frozenset(keys)


def _growth_feature_keys() -> FrozenSet[str]:
    keys = set(_starter_feature_keys())
    keys.update(expand_modules([MODULE_BOUTIQUE, MODULE_MIGRATION]))
    keys.add("sales.quotations.approve")
    keys.add("migration.run")
    keys.add(module_key(MODULE_MIGRATION))
    return frozenset(keys)


def _enterprise_feature_keys() -> FrozenSet[str]:
    return ALL_FEATURE_KEYS


PLAN_DEFINITIONS: Dict[str, Dict] = {
    PLAN_STARTER: {
        "id": PLAN_STARTER,
        "name": "Starter",
        "description": "Core trading modules without boutique, projects, or admin entitlements.",
        "feature_keys": sorted(_starter_feature_keys()),
    },
    PLAN_GROWTH: {
        "id": PLAN_GROWTH,
        "name": "Growth",
        "description": "Starter plus boutique, migration, and quotation approval.",
        "feature_keys": sorted(_growth_feature_keys()),
    },
    PLAN_ENTERPRISE: {
        "id": PLAN_ENTERPRISE,
        "name": "Enterprise",
        "description": "All modules and permissions.",
        "feature_keys": sorted(_enterprise_feature_keys()),
    },
}


# ---------------------------------------------------------------------------
# System roles
# ---------------------------------------------------------------------------

ROLE_OWNER = "role_owner"
ROLE_ESTIMATOR = "role_estimator"
ROLE_COMMERCIAL_APPROVER = "role_commercial_approver"
ROLE_PROJECT_MANAGER = "role_project_manager"
ROLE_SITE_ENGINEER = "role_site_engineer"
ROLE_PROCUREMENT = "role_procurement"
ROLE_STOREKEEPER = "role_storekeeper"
ROLE_ACCOUNTANT = "role_accountant"
ROLE_SUBCONTRACT_MANAGER = "role_subcontract_manager"
ROLE_AUDITOR = "role_auditor"
ROLE_SALES = "role_sales"
ROLE_BOUTIQUE_OPS = "role_boutique_ops"
ROLE_WAREHOUSE_MANAGER = "role_warehouse_manager"
ROLE_STORE_MANAGER = "role_store_manager"
ROLE_STORE_ASSOCIATE = "role_store_associate"
ROLE_SETTINGS_ADMIN = "role_settings_admin"

# ProjectAppRole.value → system role id
PROJECT_APP_ROLE_TO_ROLE_ID: Dict[str, str] = {
    "Owner": ROLE_OWNER,
    "Estimator": ROLE_ESTIMATOR,
    "Commercial Approver": ROLE_COMMERCIAL_APPROVER,
    "Project Manager": ROLE_PROJECT_MANAGER,
    "Site Engineer": ROLE_SITE_ENGINEER,
    "Procurement": ROLE_PROCUREMENT,
    "Storekeeper": ROLE_STOREKEEPER,
    "Accountant": ROLE_ACCOUNTANT,
    "Subcontract Manager": ROLE_SUBCONTRACT_MANAGER,
    "Auditor": ROLE_AUDITOR,
}


def _all_view_permissions() -> FrozenSet[str]:
    return frozenset(p for p in PERMISSIONS if p.endswith(".view") or p.endswith(".view_internal"))


def _role_perms(*patterns: str) -> List[str]:
    return sorted(resolve_permission_patterns(patterns))


SYSTEM_ROLE_DEFINITIONS: Dict[str, Dict] = {
    ROLE_OWNER: {
        "id": ROLE_OWNER,
        "name": "Owner",
        "description": "Full access to configuration, permissions, and all modules.",
        "permission_keys": sorted(PERMISSIONS),
    },
    ROLE_ESTIMATOR: {
        "id": ROLE_ESTIMATOR,
        "name": "Estimator",
        "description": "Requirements, BOQ, costing and quotation preparation.",
        "permission_keys": _role_perms(
            "core.*",
            "parties.customers.view",
            "projects.enquiries.*",
            "projects.projects.view",
            "projects.projects.create",
            "projects.projects.edit",
            "projects.measurements.*",
            "projects.reports.view",
            "projects.cost.view_internal",
            "sales.estimates.*",
            "sales.quotations.view",
            "sales.quotations.create",
            "sales.quotations.edit",
        ),
    },
    ROLE_COMMERCIAL_APPROVER: {
        "id": ROLE_COMMERCIAL_APPROVER,
        "name": "Commercial Approver",
        "description": "Commercial document and RA bill approvals.",
        "permission_keys": _role_perms(
            "core.*",
            "parties.customers.view",
            "projects.enquiries.view",
            "projects.projects.view",
            "projects.ra_bills.view",
            "projects.ra_bills.approve",
            "projects.cost.view_internal",
            "projects.commercial.approve",
            "sales.quotations.view",
            "sales.quotations.approve",
            "sales.orders.view",
            "sales.invoices.view",
        ),
    },
    ROLE_PROJECT_MANAGER: {
        "id": ROLE_PROJECT_MANAGER,
        "name": "Project Manager",
        "description": "Plan, execute, monitor progress, cost and forecast.",
        "permission_keys": _role_perms(
            "core.*",
            "parties.customers.view",
            "parties.vendors.view",
            "parties.employees.view",
            "parties.segments.view",
            "projects.overview.view",
            "projects.enquiries.*",
            "projects.projects.*",
            "projects.measurements.*",
            "projects.ra_bills.*",
            "projects.reports.view",
            "projects.settings.view",
            "projects.cost.view_internal",
            "projects.commercial.approve",
            "projects.site_mobile.view",
            "projects.portal.manage",
            "purchases.overview.view",
            "purchases.orders.*",
            "purchases.grn.*",
            "purchases.bills.*",
            "purchases.returns.*",
            "purchases.reports.view",
            "inventory.overview.view",
            "inventory.categories.view",
            "inventory.warehouses.view",
            "inventory.products.view",
            "inventory.stock.view",
            "inventory.stock_ledger.view",
            "inventory.movements.view",
            "inventory.customer_prices.view",
            "inventory.transfers.view",
            "inventory.reports.view",
            "sales.overview.view",
            "sales.estimates.view",
            "sales.quotations.view",
            "sales.orders.view",
            "sales.delivery_notes.view",
            "sales.invoices.view",
            "sales.returns.view",
            "sales.reports.view",
        ),
    },
    ROLE_SITE_ENGINEER: {
        "id": ROLE_SITE_ENGINEER,
        "name": "Site Engineer",
        "description": "Daily progress, measurement, material and labour recording.",
        "permission_keys": _role_perms(
            "core.dashboard.view",
            "projects.overview.view",
            "projects.projects.view",
            "projects.measurements.view",
            "projects.measurements.edit",
            "projects.site_mobile.view",
            "inventory.stock.view",
            "inventory.movements.view",
            "inventory.movements.create",
        ),
    },
    ROLE_PROCUREMENT: {
        "id": ROLE_PROCUREMENT,
        "name": "Procurement",
        "description": "Requests, RFQs, comparison, POs and supplier coordination.",
        "permission_keys": _role_perms(
            "core.*",
            "parties.vendors.*",
            "purchases.*",
            "inventory.products.view",
            "inventory.stock.view",
            "inventory.movements.view",
            "projects.projects.view",
        ),
    },
    ROLE_STOREKEEPER: {
        "id": ROLE_STOREKEEPER,
        "name": "Storekeeper",
        "description": "Receipts, issues, returns, transfers and site stock.",
        "permission_keys": _role_perms(
            "core.dashboard.view",
            "inventory.*",
            "purchases.grn.*",
            "parties.vendors.view",
        ),
    },
    ROLE_ACCOUNTANT: {
        "id": ROLE_ACCOUNTANT,
        "name": "Accountant",
        "description": "Bills, invoices, receipts, payments, taxes, journals.",
        "permission_keys": _role_perms(
            "core.*",
            "finance.*",
            "parties.customers.view",
            "parties.vendors.view",
            "sales.invoices.view",
            "sales.returns.view",
            "purchases.bills.view",
            "purchases.returns.view",
            "projects.ra_bills.view",
            "projects.cost.view_internal",
        ),
    },
    ROLE_SUBCONTRACT_MANAGER: {
        "id": ROLE_SUBCONTRACT_MANAGER,
        "name": "Subcontract Manager",
        "description": "Subcontractor coordination and related purchasing.",
        "permission_keys": _role_perms(
            "core.*",
            "parties.vendors.*",
            "projects.projects.view",
            "projects.measurements.view",
            "projects.ra_bills.view",
            "purchases.orders.*",
            "purchases.bills.view",
        ),
    },
    ROLE_AUDITOR: {
        "id": ROLE_AUDITOR,
        "name": "Auditor",
        "description": "Read-only access across modules including internal cost.",
        "permission_keys": sorted(
            set(_all_view_permissions())
            | {"projects.cost.view_internal", "finance.export.view"}
        ),
    },
    ROLE_SALES: {
        "id": ROLE_SALES,
        "name": "Sales",
        "description": "Customer and sales document operations.",
        "permission_keys": _role_perms(
            "core.*",
            "parties.customers.*",
            "parties.segments.view",
            "sales.overview.view",
            "sales.estimates.*",
            "sales.quotations.view",
            "sales.quotations.create",
            "sales.quotations.edit",
            "sales.orders.*",
            "sales.delivery_notes.*",
            "sales.invoices.*",
            "sales.returns.*",
            "sales.reports.view",
            "inventory.products.view",
            "inventory.stock.view",
            "inventory.customer_prices.view",
        ),
    },
    ROLE_BOUTIQUE_OPS: {
        "id": ROLE_BOUTIQUE_OPS,
        "name": "Boutique Ops",
        "description": "Boutique order and workshop operations.",
        "permission_keys": _role_perms(
            "core.*",
            "parties.customers.*",
            "parties.employees.view",
            "boutique.*",
        ),
    },
    ROLE_WAREHOUSE_MANAGER: {
        "id": ROLE_WAREHOUSE_MANAGER,
        "name": "Warehouse Manager",
        "description": "Full inventory, warehouses, goods receipt, movements and stock control.",
        "permission_keys": _role_perms(
            "core.dashboard.view",
            "inventory.*",
            "purchases.overview.view",
            "purchases.orders.view",
            "purchases.grn.*",
            "purchases.returns.*",
            "purchases.reports.view",
            "parties.vendors.view",
            "sales.delivery_notes.view",
        ),
    },
    ROLE_STORE_MANAGER: {
        "id": ROLE_STORE_MANAGER,
        "name": "Store Manager",
        "description": "Retail store operations: sales, customers, stock visibility and collections.",
        "permission_keys": _role_perms(
            "core.*",
            "parties.customers.*",
            "parties.segments.view",
            "parties.employees.view",
            "sales.*",
            "inventory.overview.view",
            "inventory.products.view",
            "inventory.stock.view",
            "inventory.customer_prices.*",
            "inventory.reports.view",
            "finance.overview.view",
            "finance.receipts.*",
        ),
    },
    ROLE_STORE_ASSOCIATE: {
        "id": ROLE_STORE_ASSOCIATE,
        "name": "Store Associate",
        "description": "Retail counter: create orders, invoices, returns and collect receipts.",
        "permission_keys": _role_perms(
            "core.dashboard.view",
            "parties.customers.view",
            "parties.customers.create",
            "sales.overview.view",
            "sales.orders.view",
            "sales.orders.create",
            "sales.orders.edit",
            "sales.delivery_notes.view",
            "sales.delivery_notes.create",
            "sales.invoices.view",
            "sales.invoices.create",
            "sales.returns.view",
            "sales.returns.create",
            "inventory.products.view",
            "inventory.stock.view",
            "inventory.customer_prices.view",
            "finance.receipts.view",
            "finance.receipts.create",
        ),
    },
    ROLE_SETTINGS_ADMIN: {
        "id": ROLE_SETTINGS_ADMIN,
        "name": "Settings Admin",
        "description": "Business and module settings without plan/flag control.",
        "permission_keys": sorted(
            p
            for p in resolve_permission_patterns(["core.*", "settings.*"])
            if p
            not in (
                "settings.feature_flags.manage",
                "settings.plans.manage",
            )
        ),
    },
}

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"  # bootstrap only; change after first login
ORG_ENTITLEMENT_ID = "default"
