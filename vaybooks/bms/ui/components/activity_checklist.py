import streamlit as st

from vaybooks.bms.application.order_app_service import OrderAppService
from vaybooks.bms.domain.orders.entities import CustomizationOrder
from vaybooks.bms.domain.shared.enums import ActivityStatus
from vaybooks.bms.ui.session_keys import ACTIVITY_SKIP_NOTICE


def activity_checklist(
    services: dict,
    order: CustomizationOrder,
    bill_id: str | None = None,
    on_complete_key: str = "complete_activity",
):
    order_service: OrderAppService = services["orders"]

    for activity in order.order_activities:
        if not activity.is_required:
            continue
        if bill_id and activity.bill_id != bill_id:
            continue

        cols = st.columns([3, 2, 1, 1])
        cols[0].write(f"**{activity.activity_name}**")
        cols[1].write(activity.activity_status.value)

        if activity.activity_status in (
            ActivityStatus.PENDING,
            ActivityStatus.IN_PROGRESS,
        ):
            key_suffix = f"{activity.order_activity_id}_{bill_id or 'all'}"
            if cols[2].button("Complete", key=f"comp_{key_suffix}"):
                try:
                    result = order_service.prepare_complete_activity(
                        activity.order_activity_id
                    )
                    st.session_state[on_complete_key] = result
                    st.session_state["complete_order_id"] = order.id
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            if cols[3].button("Skip", key=f"skip_{key_suffix}"):
                try:
                    order_service.skip_activity(activity.order_activity_id, "Staff")
                    st.session_state[ACTIVITY_SKIP_NOTICE] = (
                        f"Activity {activity.activity_name} skipped"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
