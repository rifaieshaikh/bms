
def _text(at):
    return " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("title")
        + at.get("subheader") + at.get("caption") + at.get("info")
    )


def test_vendors_list_route_renders():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.ui.pages.parties.vendors import list as vendors

        services = {
            "vendors": MagicMock(list_all_vendors=MagicMock(return_value=[])),
            "accounting": MagicMock(
                get_vendor_account=MagicMock(return_value=None)
            ),
        }
        vendors.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception
    assert "Vendors" in _text(at)


def test_vendor_form_module_exports_render():
    from vaybooks.bms.ui.components.parties.vendor_form import render_vendor_form

    assert callable(render_vendor_form)


def test_vendor_balance_status_labels():
    from vaybooks.bms.ui.pages.parties.vendors.detail import _balance_status

    assert _balance_status(0.0) == ("Settled", "gray")
    assert _balance_status(0.005) == ("Settled", "gray")
    assert _balance_status(120.0) == ("Amount Payable", "red")
    assert _balance_status(-50.0) == ("Vendor Advance", "green")


def test_related_transactions_order_is_purchase_workflow():
    from vaybooks.bms.ui.pages.parties.vendors import detail as vendor_detail

    source = open(vendor_detail.__file__, encoding="utf-8").read()
    po = source.index('"Purchase Orders"')
    grn = source.index('"Goods Receipts"')
    bills = source.index('"Purchase Bills"')
    returns = source.index('"Purchase Returns"')
    assert po < grn < bills < returns


def test_vendor_detail_route_renders_from_query_id():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        import streamlit as st

        from vaybooks.bms.domain.parties.vendors.entities import Vendor
        from vaybooks.bms.ui.pages.parties.vendors import detail as vendor_detail

        vendor = Vendor(
            id="vend-1",
            vendor_name="Acme Supplies",
            phone_number="9000000002",
            created_at=datetime(2026, 6, 1),
        )
        st.query_params["id"] = "vend-1"
        account = MagicMock(
            id="vacc-1",
            account_name="Acme Supplies Payable",
            current_balance=0.0,
        )
        purchases = MagicMock(
            get_vendor_summary=MagicMock(
                return_value={
                    "po_count": 2,
                    "open_count": 1,
                    "total_billed": 1500.0,
                }
            ),
            related_document_counts=MagicMock(
                return_value={
                    "purchase_orders": 2,
                    "goods_receipts": 1,
                    "purchase_bills": 3,
                    "purchase_returns": 0,
                }
            ),
            list_recent_purchase_orders_by_vendor=MagicMock(return_value=[]),
            list_purchase_bills=MagicMock(return_value=[]),
        )
        services = {
            "vendors": MagicMock(get_vendor_detail=MagicMock(return_value=vendor)),
            "accounting": MagicMock(
                get_vendor_account=MagicMock(return_value=account),
                list_vendor_payments=MagicMock(return_value=[]),
            ),
            "purchases": purchases,
            "vendor_services": MagicMock(
                list_services=MagicMock(return_value=[])
            ),
        }
        vendor_detail.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception
    text = _text(at)
    buttons = " ".join(getattr(el, "label", "") or "" for el in at.button)

    assert "Acme Supplies" in text
    assert "Back to vendors" in buttons
    assert "Edit Vendor" in buttons
    assert "Purchase Order" in buttons
    assert "Purchase Bill" in buttons
    assert "Record Payment" in buttons
    assert "View All" in buttons
    assert "Quick Actions" in text
    assert "Related Transactions" in text
    assert "Purchase Orders" in text
    assert "Goods Receipts" in text
    assert "Purchase Bills" in text
    assert "Purchase Returns" in text
    metric_labels = " ".join(getattr(m, "label", "") or "" for m in at.metric)
    assert "Total Billed Amount" in metric_labels
    assert "Total Purchase Billed" not in metric_labels
    assert "Total Purchase Orders" in metric_labels
    assert "Open Purchase Orders" in metric_labels
    assert "Payable Balance" in text  # custom card, not st.metric
    assert "Recent Purchase Orders" in text
    assert "No purchase orders yet" in text
    assert "Recent Payments" in text
    assert "No payments recorded yet" in text
    assert "View All Payments" in buttons
    assert "Outsourced service" not in text
    assert "Settled" in text
    assert "Vendor Detail" not in text

    # Related Transactions order in rendered text.
    assert text.index("Purchase Orders") < text.index("Goods Receipts")
    assert text.index("Goods Receipts") < text.index("Purchase Bills")
    assert text.index("Purchase Bills") < text.index("Purchase Returns")


def test_vendor_detail_amount_payable_badge():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        import streamlit as st

        from vaybooks.bms.domain.parties.vendors.entities import Vendor
        from vaybooks.bms.ui.pages.parties.vendors import detail as vendor_detail

        vendor = Vendor(
            id="vend-2",
            vendor_name="Owed Vendor",
            phone_number="9000000003",
            created_at=datetime(2026, 6, 1),
        )
        st.query_params["id"] = "vend-2"
        account = MagicMock(
            id="vacc-2",
            account_name="Owed Vendor Payable",
            current_balance=2500.0,
        )
        services = {
            "vendors": MagicMock(get_vendor_detail=MagicMock(return_value=vendor)),
            "accounting": MagicMock(
                get_vendor_account=MagicMock(return_value=account),
                list_vendor_payments=MagicMock(return_value=[]),
            ),
            "purchases": MagicMock(
                get_vendor_summary=MagicMock(
                    return_value={
                        "po_count": 0,
                        "open_count": 0,
                        "total_billed": 0.0,
                    }
                ),
                related_document_counts=MagicMock(return_value={}),
                list_recent_purchase_orders_by_vendor=MagicMock(return_value=[]),
                list_purchase_bills=MagicMock(return_value=[]),
            ),
            "vendor_services": MagicMock(list_services=MagicMock(return_value=[])),
        }
        vendor_detail.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception
    assert "Amount Payable" in _text(at)


def test_vendor_detail_vendor_advance_badge():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        import streamlit as st

        from vaybooks.bms.domain.parties.vendors.entities import Vendor
        from vaybooks.bms.ui.pages.parties.vendors import detail as vendor_detail

        vendor = Vendor(
            id="vend-3",
            vendor_name="Advance Vendor",
            phone_number="9000000004",
            created_at=datetime(2026, 6, 1),
        )
        st.query_params["id"] = "vend-3"
        account = MagicMock(
            id="vacc-3",
            account_name="Advance Vendor Payable",
            current_balance=-800.0,
        )
        services = {
            "vendors": MagicMock(get_vendor_detail=MagicMock(return_value=vendor)),
            "accounting": MagicMock(
                get_vendor_account=MagicMock(return_value=account),
                list_vendor_payments=MagicMock(return_value=[]),
            ),
            "purchases": MagicMock(
                get_vendor_summary=MagicMock(
                    return_value={
                        "po_count": 0,
                        "open_count": 0,
                        "total_billed": 0.0,
                    }
                ),
                related_document_counts=MagicMock(return_value={}),
                list_recent_purchase_orders_by_vendor=MagicMock(return_value=[]),
                list_purchase_bills=MagicMock(return_value=[]),
            ),
            "vendor_services": MagicMock(list_services=MagicMock(return_value=[])),
        }
        vendor_detail.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception
    assert "Vendor Advance" in _text(at)
