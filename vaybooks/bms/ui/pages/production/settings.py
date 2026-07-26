import streamlit as st

from vaybooks.bms.domain.shared.enums import ProductionCostAllocationMethod


def render(services: dict) -> None:
    st.header("Production Settings")
    service = services.get("production")
    accounting = services.get("accounting")
    if not service or not accounting:
        st.error("Production or accounting service is unavailable.")
        return
    settings = service.get_settings()
    accounts = accounting.list_accounts(active_only=True)
    options = {"Not configured": ""}
    options.update({f"{account.account_name} ({account.account_type.value})": account.id for account in accounts})
    reverse = {value: key for key, value in options.items()}

    def account_select(label: str, account_id: str) -> str:
        current = reverse.get(account_id, "Not configured")
        selected = st.selectbox(label, list(options), index=list(options).index(current))
        return options[selected]

    with st.form("production_settings_form"):
        settings.raw_material_account_id = account_select(
            "Raw material stock account", settings.raw_material_account_id
        )
        settings.wip_account_id = account_select("WIP account", settings.wip_account_id)
        settings.finished_goods_account_id = account_select(
            "Finished goods stock account", settings.finished_goods_account_id
        )
        settings.expense_clearing_account_id = account_select(
            "Expense clearing / payable account",
            settings.expense_clearing_account_id,
        )
        settings.manufacturing_overhead_account_id = account_select(
            "Manufacturing overhead account",
            settings.manufacturing_overhead_account_id,
        )
        settings.scrap_account_id = account_select(
            "Scrap recovery account", settings.scrap_account_id
        )
        methods = [item.value for item in ProductionCostAllocationMethod]
        method = st.selectbox(
            "Default allocation method",
            methods,
            index=methods.index(settings.default_allocation_method.value),
        )
        settings.default_allocation_method = ProductionCostAllocationMethod(method)
        if st.form_submit_button("Save settings", type="primary"):
            service.save_settings(settings)
            st.success("Production settings saved.")
