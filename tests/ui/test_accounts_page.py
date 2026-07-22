
def test_accounts_page_lists_all_accounts():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.application.finance.accounting.service import AccountingAppService
        from vaybooks.bms.domain.finance.accounting.entities import Account
        from vaybooks.bms.domain.shared.enums import AccountType
        from vaybooks.bms.ui.pages import accounts
        from tests.conftest import (
            FakeAccountRepository,
            FakeCounterRepository,
            FakeVoucherRepository,
        )

        account_repo = FakeAccountRepository()
        account_repo.save(
            Account(
                id="acc-cash",
                account_name="Cash Drawer",
                account_type=AccountType.ASSET,
                is_store_account=True,
            )
        )
        account_repo.save(
            Account(
                id="acc-salary",
                account_name="Salary Payable",
                account_type=AccountType.LIABILITY,
                is_salary_account=True,
            )
        )
        accounting = AccountingAppService(
            account_repo, FakeVoucherRepository(), FakeCounterRepository()
        )
        services = {
            "accounting": accounting,
            "vendors": MagicMock(list_all_vendors=MagicMock(return_value=[])),
            "vendor_services": MagicMock(list_services=MagicMock(return_value=[])),
        }
        accounts.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("subheader")
        + at.get("caption") + at.get("info")
    )
    # All accounts (including system ones) appear in the filterable list.
    assert "Cash Drawer" in rendered
    assert "Salary Payable" in rendered


def test_vouchers_route_shows_voucher():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        from vaybooks.bms.application.finance.accounting.service import AccountingAppService
        from vaybooks.bms.domain.finance.accounting.entities import Voucher, VoucherLine
        from vaybooks.bms.domain.shared.enums import VoucherType
        from vaybooks.bms.ui.pages.finance import vouchers
        from tests.conftest import (
            FakeAccountRepository,
            FakeCounterRepository,
            FakeVoucherRepository,
        )

        voucher_repo = FakeVoucherRepository()
        account_repo = FakeAccountRepository()
        counter_repo = FakeCounterRepository()
        voucher_repo.save(
            Voucher(
                voucher_number="VCH-0001",
                voucher_type=VoucherType.JOURNAL,
                voucher_date=datetime(2024, 6, 30),
                description="Zahcci month-end adjustment",
                lines=[
                    VoucherLine("a1", "Expense", debit_amount=15000),
                    VoucherLine("a2", "Cash", credit_amount=15000),
                ],
            )
        )
        accounting = AccountingAppService(account_repo, voucher_repo, counter_repo)
        services = {
            "accounting": accounting,
            "vendors": MagicMock(list_all_vendors=MagicMock(return_value=[])),
            "vendor_services": MagicMock(list_services=MagicMock(return_value=[])),
        }
        vouchers.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("info")
    )
    assert "Voucher" in rendered
    assert "VCH-0001" in rendered


def test_trial_balance_route_shows_balance_status():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        from vaybooks.bms.application.finance.accounting.service import AccountingAppService
        from vaybooks.bms.domain.finance.accounting.entities import Account, Voucher, VoucherLine
        from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
        from vaybooks.bms.ui.pages.finance import trial_balance
        from tests.conftest import (
            FakeAccountRepository,
            FakeCounterRepository,
            FakeVoucherRepository,
        )

        account_repo = FakeAccountRepository()
        account_repo.save(Account(id="a1", account_name="Expense",
                                  account_type=AccountType.EXPENSE))
        account_repo.save(Account(id="a2", account_name="Cash",
                                  account_type=AccountType.ASSET))
        voucher_repo = FakeVoucherRepository()
        voucher_repo.save(
            Voucher(
                voucher_number="JRN-0001",
                voucher_type=VoucherType.JOURNAL,
                voucher_date=datetime(2024, 6, 30),
                description="Balanced journal",
                lines=[
                    VoucherLine("a1", "Expense", debit_amount=15000),
                    VoucherLine("a2", "Cash", credit_amount=15000),
                ],
            )
        )
        accounting = AccountingAppService(
            account_repo, voucher_repo, FakeCounterRepository()
        )
        services = {
            "accounting": accounting,
            "vendors": MagicMock(list_all_vendors=MagicMock(return_value=[])),
            "vendor_services": MagicMock(list_services=MagicMock(return_value=[])),
        }
        trial_balance.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("metric")
        + at.get("header") + at.get("info")
    )
    assert "Balanced" in rendered


def test_accounts_page_shows_delete_and_deactivate_for_non_protected_account():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.application.finance.accounting.service import AccountingAppService
        from vaybooks.bms.domain.finance.accounting.entities import Account
        from vaybooks.bms.domain.shared.enums import AccountType
        from vaybooks.bms.ui.pages import accounts
        from tests.conftest import (
            FakeAccountRepository,
            FakeCounterRepository,
            FakeVoucherRepository,
        )

        account_repo = FakeAccountRepository()
        account_repo.save(
            Account(
                id="acc-misc",
                account_name="Misc Expense",
                account_type=AccountType.EXPENSE,
            )
        )
        accounting = AccountingAppService(
            account_repo, FakeVoucherRepository(), FakeCounterRepository()
        )
        services = {
            "accounting": accounting,
            "vendors": MagicMock(list_all_vendors=MagicMock(return_value=[])),
            "vendor_services": MagicMock(list_services=MagicMock(return_value=[])),
        }
        accounts.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    button_text = "".join(getattr(el, "label", "") or "" for el in at.get("button"))
    assert "DeleteDisable" in button_text


def test_accounts_page_hides_delete_for_protected_store_account():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.application.finance.accounting.service import AccountingAppService
        from vaybooks.bms.domain.finance.accounting.entities import Account
        from vaybooks.bms.domain.shared.enums import AccountType
        from vaybooks.bms.ui.pages import accounts
        from tests.conftest import (
            FakeAccountRepository,
            FakeCounterRepository,
            FakeVoucherRepository,
        )

        account_repo = FakeAccountRepository()
        account_repo.save(
            Account(
                id="acc-cash",
                account_name="Cash Drawer",
                account_type=AccountType.ASSET,
                is_store_account=True,
            )
        )
        accounting = AccountingAppService(
            account_repo, FakeVoucherRepository(), FakeCounterRepository()
        )
        services = {
            "accounting": accounting,
            "vendors": MagicMock(list_all_vendors=MagicMock(return_value=[])),
            "vendor_services": MagicMock(list_services=MagicMock(return_value=[])),
        }
        accounts.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    labels = [getattr(el, "label", "") or "" for el in at.get("button")]
    assert "Delete" not in labels
    assert "Disable" in labels


def test_account_detail_route_renders_ledger_for_account():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        import streamlit as st

        from vaybooks.bms.application.finance.accounting.service import AccountingAppService
        from vaybooks.bms.domain.finance.accounting.entities import Account, Voucher, VoucherLine
        from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
        from vaybooks.bms.ui.pages import account_detail
        from tests.conftest import (
            FakeAccountRepository,
            FakeCounterRepository,
            FakeVoucherRepository,
        )

        account_repo = FakeAccountRepository()
        account_repo.save(
            Account(
                id="acc-cash",
                account_name="Cash Drawer",
                account_type=AccountType.ASSET,
                is_store_account=True,
            )
        )
        voucher_repo = FakeVoucherRepository()
        voucher_repo.save(
            Voucher(
                voucher_number="JRN-0001",
                voucher_type=VoucherType.JOURNAL,
                voucher_date=datetime(2024, 6, 30),
                description="Balanced journal",
                lines=[
                    VoucherLine("acc-cash", "Cash Drawer", debit_amount=15000),
                    VoucherLine("acc-other", "Other", credit_amount=15000),
                ],
            )
        )
        accounting = AccountingAppService(
            account_repo, voucher_repo, FakeCounterRepository()
        )
        st.query_params["id"] = "acc-cash"
        services = {
            "accounting": accounting,
            "vendors": MagicMock(list_all_vendors=MagicMock(return_value=[])),
            "vendor_services": MagicMock(list_services=MagicMock(return_value=[])),
        }
        account_detail.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("title") + at.get("markdown") + at.get("caption")
    )
    assert "Cash Drawer" in rendered
