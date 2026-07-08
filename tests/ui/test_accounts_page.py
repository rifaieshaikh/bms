
def test_accounts_page_shows_system_accounts_section():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.application.accounting_app_service import AccountingAppService
        from vaybooks.bms.domain.accounting.entities import Account
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
        for el in at.get("markdown") + at.get("header") + at.get("caption") + at.get("info")
    )
    tab_labels = " ".join(getattr(el, "label", "") or "" for el in at.get("tab"))
    page_text = f"{rendered} {tab_labels}"
    assert "System" in page_text
    assert "displays" in page_text
    assert "message" in page_text
    assert "Store:" in page_text
    assert "Salary:" in page_text
    assert "Cash Drawer" in page_text
    assert "Salary Payable" in page_text


def test_accounts_page_shows_voucher_label():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        from vaybooks.bms.application.accounting_app_service import AccountingAppService
        from vaybooks.bms.domain.accounting.entities import Voucher, VoucherLine
        from vaybooks.bms.domain.shared.enums import VoucherType
        from vaybooks.bms.ui.pages import accounts
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
        accounts.render(services)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page)
    at.run(timeout=15)
    assert not at.exception

    rendered = " ".join(
        getattr(el, "value", "") or ""
        for el in at.get("markdown") + at.get("header") + at.get("info")
    )
    tab_labels = " ".join(getattr(el, "label", "") or "" for el in at.get("tab"))
    page_text = f"{rendered} {tab_labels}"
    assert "Voucher" in page_text
    assert "posts" in page_text
    assert "successfully" in page_text


def test_accounts_page_blocks_unbalanced_journal_message():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.application.accounting_app_service import AccountingAppService
        from vaybooks.bms.ui.pages import accounts
        from tests.conftest import (
            FakeAccountRepository,
            FakeCounterRepository,
            FakeVoucherRepository,
        )

        accounting = AccountingAppService(
            FakeAccountRepository(), FakeVoucherRepository(), FakeCounterRepository()
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
        for el in at.get("markdown") + at.get("header") + at.get("info")
    )
    assert "blocks" in rendered.lower()
    assert "unbalanced" in rendered.lower()


def test_accounts_page_shows_delete_and_deactivate_for_non_protected_account():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.application.accounting_app_service import AccountingAppService
        from vaybooks.bms.domain.accounting.entities import Account
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
    assert "DeleteDeactivate" in button_text


def test_accounts_page_hides_delete_for_protected_store_account():
    def _page():
        from unittest.mock import MagicMock

        from vaybooks.bms.application.accounting_app_service import AccountingAppService
        from vaybooks.bms.domain.accounting.entities import Account
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
    assert "Deactivate" in labels


def test_accounts_page_ledger_tab_renders_ledger_header_with_account():
    def _page():
        from datetime import datetime
        from unittest.mock import MagicMock

        from vaybooks.bms.application.accounting_app_service import AccountingAppService
        from vaybooks.bms.domain.accounting.entities import Account, Voucher, VoucherLine
        from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
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

    tab_labels = " ".join(getattr(el, "label", "") or "" for el in at.get("tab"))
    headers = " ".join(getattr(el, "value", "") or "" for el in at.get("header"))
    page_text = f"{tab_labels} {headers}"
    assert "Ledger" in page_text

    selectboxes = at.get("selectbox")
    account_select = next(
        (el for el in selectboxes if getattr(el, "label", "") == "Account"),
        None,
    )
    assert account_select is not None
    assert account_select.value == "Cash Drawer"
