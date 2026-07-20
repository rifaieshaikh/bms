from datetime import date, datetime
from typing import List, Optional

from vaybooks.bms.domain.accounting.entities import Account, Voucher, VoucherLine
from vaybooks.bms.domain.accounting.repository import AccountRepository, CounterRepository, VoucherRepository
from vaybooks.bms.domain.accounting.services import (
    ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME,
    AccountingDomainService,
)
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.domain.sales.invoice_lock import assert_invoice_editable
from vaybooks.bms.domain.shared.india import (
    CGST_INPUT_ACCOUNT_NAME,
    CGST_OUTPUT_ACCOUNT_NAME,
    IGST_INPUT_ACCOUNT_NAME,
    IGST_OUTPUT_ACCOUNT_NAME,
    SGST_INPUT_ACCOUNT_NAME,
    SGST_OUTPUT_ACCOUNT_NAME,
    UTGST_INPUT_ACCOUNT_NAME,
    UTGST_OUTPUT_ACCOUNT_NAME,
)


ADVANCE_RELEASE_DESCRIPTION_PREFIX = "Release advance on order"


class AccountingAppService:
    def __init__(
        self,
        account_repo: AccountRepository,
        voucher_repo: VoucherRepository,
        counter_repo: CounterRepository,
    ):
        self._account_repo = account_repo
        self._voucher_repo = voucher_repo
        self._counter_repo = counter_repo
        self._domain = AccountingDomainService(account_repo, voucher_repo)

    def create_account(
        self,
        account_name: str,
        account_type: str,
        opening_balance: float = 0,
        is_store_account: Optional[bool] = None,
        is_salary_account: Optional[bool] = None,
    ) -> Account:
        acc_type = AccountType(account_type)
        if is_store_account is None:
            is_store_account = False
        if is_salary_account is None:
            is_salary_account = False
        account = Account(
            account_name=account_name,
            account_type=acc_type,
            opening_balance=opening_balance,
            current_balance=opening_balance,
            is_store_account=is_store_account,
            is_salary_account=is_salary_account,
        )
        return self._account_repo.save(account)

    def set_store_account(self, account_id: str, is_store_account: bool) -> Account:
        account = self._account_repo.find_by_id(account_id)
        if not account:
            raise ValueError("Account not found")
        account.is_store_account = is_store_account
        return self._account_repo.save(account)

    def set_opening_balance(self, account_id: str, amount: float) -> Account:
        """Set opening and current balance for go-live migration.

        Rejects accounts that already have posted vouchers so migration cannot
        overwrite a live ledger.
        """
        account = self._account_repo.find_by_id(account_id)
        if not account:
            raise ValueError("Account not found")
        if self.get_account_ledger(account_id):
            raise ValueError(
                "Cannot set opening balance on an account that has transactions"
            )
        balance = round(float(amount or 0), 2)
        account.opening_balance = balance
        account.current_balance = balance
        account.updated_at = datetime.utcnow()
        return self._account_repo.save(account)

    # Accounts resolved by name/type elsewhere (invoice & discount posting). Their
    # name and type are locked so renaming/retyping can't silently break posting.
    PROTECTED_ACCOUNT_NAMES = {
        "sales",
        "customization",
        "discount allowed",
        ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME.lower(),
    }

    def is_protected_account(self, account: Account) -> bool:
        if account.is_store_account:
            return True
        return account.account_name.strip().lower() in self.PROTECTED_ACCOUNT_NAMES

    def update_account(
        self,
        account_id: str,
        account_name: str,
        account_type: str,
        is_store_account: bool,
        is_salary_account: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> Account:
        account = self._account_repo.find_by_id(account_id)
        if not account:
            raise ValueError("Account not found")

        name = (account_name or "").strip()
        if not name:
            raise ValueError("Account name is required")
        new_type = AccountType(account_type)

        if self.is_protected_account(account):
            if name.lower() != account.account_name.strip().lower():
                raise ValueError(
                    f'"{account.account_name}" is used by invoice/discount posting '
                    "and cannot be renamed."
                )
            if new_type != account.account_type:
                raise ValueError(
                    f'"{account.account_name}" is used by invoice/discount posting '
                    "and its type cannot be changed."
                )

        account.account_name = name
        account.account_type = new_type
        account.is_store_account = is_store_account
        if is_salary_account is not None:
            account.is_salary_account = is_salary_account
        if is_active is not None:
            account.is_active = is_active
        account.updated_at = datetime.utcnow()
        return self._account_repo.save(account)

    def deactivate_account(self, account_id: str) -> Account:
        account = self._account_repo.find_by_id(account_id)
        if not account:
            raise ValueError("Account not found")
        return self.update_account(
            account_id,
            account.account_name,
            account.account_type.value,
            account.is_store_account,
            account.is_salary_account,
            is_active=False,
        )

    def delete_account(self, account_id: str) -> None:
        account = self._account_repo.find_by_id(account_id)
        if not account:
            raise ValueError("Account not found")
        if self.is_protected_account(account):
            raise ValueError(
                f'"{account.account_name}" is a protected account and cannot be deleted.'
            )
        if self.get_account_ledger(account_id):
            raise ValueError(
                "Cannot delete an account that has transactions. Deactivate it instead."
            )
        delete = getattr(self._account_repo, "delete", None)
        if delete is None:
            raise ValueError("Account deletion is not supported")
        delete(account_id)

    def list_accounts(self, active_only: bool = True) -> List[Account]:
        return self._account_repo.list_all(active_only=active_only)

    def get_account(self, account_id: str) -> Optional[Account]:
        return self._account_repo.find_by_id(account_id)

    def get_account_by_name(self, name: str) -> Optional[Account]:
        return self._account_repo.find_by_name(name)

    def get_gst_input_accounts(self) -> dict:
        mapping = {
            "cgst": CGST_INPUT_ACCOUNT_NAME,
            "sgst": SGST_INPUT_ACCOUNT_NAME,
            "igst": IGST_INPUT_ACCOUNT_NAME,
            "utgst": UTGST_INPUT_ACCOUNT_NAME,
        }
        result = {}
        for key, account_name in mapping.items():
            account = self._account_repo.find_by_name(account_name)
            if account:
                result[key] = {"id": account.id, "name": account.account_name}
        return result

    def get_gst_output_accounts(self) -> dict:
        mapping = {
            "cgst": CGST_OUTPUT_ACCOUNT_NAME,
            "sgst": SGST_OUTPUT_ACCOUNT_NAME,
            "igst": IGST_OUTPUT_ACCOUNT_NAME,
            "utgst": UTGST_OUTPUT_ACCOUNT_NAME,
        }
        result = {}
        for key, account_name in mapping.items():
            account = self._account_repo.find_by_name(account_name)
            if account:
                result[key] = {"id": account.id, "name": account.account_name}
        return result

    def create_advance_receipt(
        self,
        receiving_account_id: str,
        customer_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        receiving = self._account_repo.find_by_id(receiving_account_id)
        customer = self._account_repo.find_by_id(customer_account_id)
        if not receiving or not customer:
            raise ValueError("Receiving or customer account not found")
        advance = self.get_advance_from_customers_account()
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_advance_receipt_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            receiving_account_id=receiving.id,
            receiving_account_name=receiving.account_name,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            advance_account_id=advance.id,
            advance_account_name=advance.account_name,
            amount=amount,
            reference_order_id=reference_order_id,
        )
        return self._domain.save_voucher(voucher)

    def update_advance_receipt(
        self,
        voucher_id: str,
        receiving_account_id: str,
        customer_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old or old.voucher_type != VoucherType.ADVANCE:
            raise ValueError("Advance receipt not found")
        receiving = self._account_repo.find_by_id(receiving_account_id)
        customer = self._account_repo.find_by_id(customer_account_id)
        if not receiving or not customer:
            raise ValueError("Receiving or customer account not found")
        advance = self.get_advance_from_customers_account()
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_advance_receipt_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            receiving_account_id=receiving.id,
            receiving_account_name=receiving.account_name,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            advance_account_id=advance.id,
            advance_account_name=advance.account_name,
            amount=amount,
            reference_order_id=old.reference_order_id,
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def create_customer_payment(
        self,
        receiving_account_id: str,
        customer_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        receiving = self._account_repo.find_by_id(receiving_account_id)
        customer = self._account_repo.find_by_id(customer_account_id)
        if not receiving or not customer:
            raise ValueError("Receiving or customer account not found")
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_customer_payment_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            receiving_account_id=receiving.id,
            receiving_account_name=receiving.account_name,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            amount=amount,
            reference_order_id=reference_order_id,
        )
        return self._domain.save_voucher(voucher)

    def update_customer_payment(
        self,
        voucher_id: str,
        receiving_account_id: str,
        customer_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old or old.voucher_type != VoucherType.RECEIPT:
            raise ValueError("Customer payment not found")
        receiving = self._account_repo.find_by_id(receiving_account_id)
        customer = self._account_repo.find_by_id(customer_account_id)
        if not receiving or not customer:
            raise ValueError("Receiving or customer account not found")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_customer_payment_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            receiving_account_id=receiving.id,
            receiving_account_name=receiving.account_name,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            amount=amount,
            reference_order_id=old.reference_order_id,
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def create_receipt(
        self,
        receiving_account_id: str,
        customer_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        """Alias for customer payment (Accounts page and receipt tab)."""
        return self.create_customer_payment(
            receiving_account_id,
            customer_account_id,
            amount,
            description,
            voucher_date,
            reference_order_id,
        )

    def update_receipt(
        self,
        voucher_id: str,
        receiving_account_id: str,
        customer_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        """Alias for customer payment update."""
        return self.update_customer_payment(
            voucher_id,
            receiving_account_id,
            customer_account_id,
            amount,
            description,
            voucher_date,
        )

    def create_vendor_payment(
        self,
        vendor_account_id: str,
        expense_account_id: str,
        paying_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        service_id: Optional[str] = None,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        vendor = self._account_repo.find_by_id(vendor_account_id)
        expense = self._account_repo.find_by_id(expense_account_id)
        paying = self._account_repo.find_by_id(paying_account_id)
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())

        voucher = self._domain.build_vendor_payment_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            vendor_account_id=vendor.id,
            vendor_account_name=vendor.account_name,
            expense_account_id=expense.id,
            expense_account_name=expense.account_name,
            paying_account_id=paying.id,
            paying_account_name=paying.account_name,
            amount=amount,
            reference_order_id=reference_order_id,
            reference_service_id=service_id,
        )
        return self._domain.save_voucher(voucher)

    def update_vendor_payment(
        self,
        voucher_id: str,
        vendor_account_id: str,
        expense_account_id: str,
        paying_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        service_id: Optional[str] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old:
            raise ValueError("Vendor payment not found")
        vendor = self._account_repo.find_by_id(vendor_account_id)
        expense = self._account_repo.find_by_id(expense_account_id)
        paying = self._account_repo.find_by_id(paying_account_id)
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_vendor_payment_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            vendor_account_id=vendor.id,
            vendor_account_name=vendor.account_name,
            expense_account_id=expense.id,
            expense_account_name=expense.account_name,
            paying_account_id=paying.id,
            paying_account_name=paying.account_name,
            amount=amount,
            reference_order_id=old.reference_order_id,
            reference_service_id=service_id
            if service_id is not None
            else old.reference_service_id,
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def get_salary_accounts(self) -> List[Account]:
        return [a for a in self._account_repo.list_all() if a.is_salary_account]

    def get_salary_expense_account(self) -> Optional[Account]:
        for account in self._account_repo.list_all():
            if account.account_name.strip().lower() == "salary expense":
                return account
        return None

    def create_salary_payment(
        self,
        salary_account_id: str,
        paying_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        salary = self._account_repo.find_by_id(salary_account_id)
        paying = self._account_repo.find_by_id(paying_account_id)
        expense = self.get_salary_expense_account()
        if not expense:
            raise ValueError("Salary Expense account not found")
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())

        voucher = self._domain.build_salary_payment_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            salary_account_id=salary.id,
            salary_account_name=salary.account_name,
            expense_account_id=expense.id,
            expense_account_name=expense.account_name,
            paying_account_id=paying.id,
            paying_account_name=paying.account_name,
            amount=amount,
        )
        return self._domain.save_voucher(voucher)

    def update_salary_payment(
        self,
        voucher_id: str,
        salary_account_id: str,
        paying_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old:
            raise ValueError("Salary payment not found")
        salary = self._account_repo.find_by_id(salary_account_id)
        paying = self._account_repo.find_by_id(paying_account_id)
        expense = self.get_salary_expense_account()
        if not expense:
            raise ValueError("Salary Expense account not found")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_salary_payment_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            salary_account_id=salary.id,
            salary_account_name=salary.account_name,
            expense_account_id=expense.id,
            expense_account_name=expense.account_name,
            paying_account_id=paying.id,
            paying_account_name=paying.account_name,
            amount=amount,
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def get_vendor_account(self, vendor_id: str) -> Optional[Account]:
        return self._account_repo.find_vendor_account(vendor_id)

    def list_vendor_payments(self, vendor_account_id: str) -> List[Voucher]:
        return [
            v
            for v in self._voucher_repo.list_by_account(vendor_account_id)
            if v.voucher_type == VoucherType.VENDOR_PAYMENT
        ]

    def list_order_vendor_payments(self, order_id: str) -> List[Voucher]:
        return [
            v
            for v in self._voucher_repo.list_by_order(order_id)
            if v.voucher_type == VoucherType.VENDOR_PAYMENT
        ]

    def get_voucher(self, voucher_id: str) -> Optional[Voucher]:
        return self._voucher_repo.find_by_id(voucher_id)

    def list_vouchers_by_order(self, order_id: str) -> List[Voucher]:
        return self._voucher_repo.list_by_order(order_id)

    def get_customer_account(self, customer_id: str) -> Optional[Account]:
        return self._account_repo.find_customer_account(customer_id)

    def customer_balances_by_customer(self) -> dict:
        """Map of customer_id -> current_balance for all customers (one query)."""
        return self._account_repo.customer_balances_by_customer()

    def get_expense_accounts(self) -> List[Account]:
        return [
            a
            for a in self._account_repo.list_all()
            if a.account_type == AccountType.EXPENSE
        ]

    def get_income_accounts(self) -> List[Account]:
        return [
            a
            for a in self._account_repo.list_all()
            if a.account_type == AccountType.REVENUE
        ]

    def get_customization_account(self) -> Optional[Account]:
        for account in self._account_repo.list_all():
            if account.account_name.strip().lower() == "customization":
                return account
        return None

    def get_cancellation_charges_account(self) -> Optional[Account]:
        for account in self._account_repo.list_all():
            if account.account_name.strip().lower() == "cancellation charges":
                return account
        return None

    def get_sales_account(self) -> Optional[Account]:
        for account in self._account_repo.list_all():
            if account.account_name.strip().lower() == "sales":
                return account
        return None

    def get_advance_from_customers_account(self) -> Account:
        return self._domain.get_advance_from_customers_account()

    @staticmethod
    def _voucher_cash_amount(voucher: Voucher) -> float:
        return voucher.cash_movement_amount

    def _order_advance_released(self, order_id: str) -> float:
        advance_account = self.get_advance_from_customers_account()
        released = 0.0
        for voucher in self.list_vouchers_by_order(order_id):
            if voucher.voucher_type != VoucherType.JOURNAL:
                continue
            if not voucher.description.startswith(ADVANCE_RELEASE_DESCRIPTION_PREFIX):
                continue
            for line in voucher.lines:
                if line.account_id == advance_account.id and line.debit_amount > 0:
                    released += line.debit_amount
        return round(released, 2)

    def get_order_unapplied_advance(
        self,
        order_id: str,
        exclude_invoice_id: Optional[str] = None,
    ) -> float:
        """Advance pool for an order: ADVANCE receipts minus advance refunds, applied, released."""
        advance_account = self.get_advance_from_customers_account()
        vouchers = self.list_vouchers_by_order(order_id)
        advances = sum(
            self._voucher_cash_amount(v)
            for v in vouchers
            if v.voucher_type == VoucherType.ADVANCE
        )
        advance_refunds = sum(
            self._voucher_cash_amount(v)
            for v in vouchers
            if v.voucher_type == VoucherType.REFUND and v.is_advance_refund
        )
        applied = 0.0
        invoice_types = (VoucherType.SALES_INVOICE, VoucherType.CUSTOMIZATION_INVOICE)
        for voucher in vouchers:
            if voucher.voucher_type not in invoice_types:
                continue
            if exclude_invoice_id and voucher.reference_invoice_id == exclude_invoice_id:
                continue
            for line in voucher.lines:
                if line.account_id == advance_account.id and line.debit_amount > 0:
                    applied += line.debit_amount
        released = self._order_advance_released(order_id)
        return round(advances - advance_refunds - applied - released, 2)

    def get_order_customer_payments(
        self,
        order_id: str,
        exclude_voucher_id: Optional[str] = None,
    ) -> float:
        total = sum(
            self._voucher_cash_amount(v)
            for v in self.list_vouchers_by_order(order_id)
            if v.voucher_type == VoucherType.RECEIPT
            and v.id != exclude_voucher_id
        )
        return round(total, 2)

    def get_order_payment_refunds(
        self,
        order_id: str,
        exclude_voucher_id: Optional[str] = None,
    ) -> float:
        total = sum(
            self._voucher_cash_amount(v)
            for v in self.list_vouchers_by_order(order_id)
            if v.voucher_type == VoucherType.REFUND
            and not v.is_advance_refund
            and v.id != exclude_voucher_id
        )
        return round(total, 2)

    def get_order_refundable_customer_payments(
        self,
        order_id: str,
        exclude_voucher_id: Optional[str] = None,
    ) -> float:
        return round(
            max(
                self.get_order_customer_payments(order_id, exclude_voucher_id)
                - self.get_order_payment_refunds(order_id, exclude_voucher_id),
                0.0,
            ),
            2,
        )

    def get_order_total_received(self, order_id: str) -> float:
        """Net cash in: advances + customer payments minus all refunds."""
        vouchers = self.list_vouchers_by_order(order_id)
        advances = sum(
            self._voucher_cash_amount(v)
            for v in vouchers
            if v.voucher_type == VoucherType.ADVANCE
        )
        payments = sum(
            self._voucher_cash_amount(v)
            for v in vouchers
            if v.voucher_type == VoucherType.RECEIPT
        )
        refunds = sum(
            self._voucher_cash_amount(v)
            for v in vouchers
            if v.voucher_type == VoucherType.REFUND
        )
        return round(advances + payments - refunds, 2)

    def has_advance_release_journal(self, order_id: str) -> bool:
        return any(
            v.voucher_type == VoucherType.JOURNAL
            and v.description.startswith(ADVANCE_RELEASE_DESCRIPTION_PREFIX)
            for v in self.list_vouchers_by_order(order_id)
        )

    def release_order_advance(
        self,
        order_id: str,
        customer_account_id: str,
        order_number: str,
        voucher_date: Optional[date] = None,
    ) -> Optional[Voucher]:
        """Post Dr Advance / Cr Customer for unapplied advance when order closes."""
        if self.has_advance_release_journal(order_id):
            return None
        amount = self.get_order_unapplied_advance(order_id)
        if amount <= 0:
            return None
        customer = self._account_repo.find_by_id(customer_account_id)
        if not customer:
            raise ValueError("Customer account not found")
        advance = self.get_advance_from_customers_account()
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        description = f"{ADVANCE_RELEASE_DESCRIPTION_PREFIX} {order_number}"
        voucher = self._domain.build_release_advance_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            advance_account_id=advance.id,
            advance_account_name=advance.account_name,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            amount=amount,
            reference_order_id=order_id,
        )
        return self._domain.save_voucher(voucher)

    def find_sales_voucher_by_invoice(self, invoice_id: str) -> Optional[Voucher]:
        return self._voucher_repo.find_by_invoice(invoice_id)

    def create_sales_invoice(
        self,
        customer_account_id: str,
        income_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
        reference_invoice_id: Optional[str] = None,
        discount_amount: float = 0.0,
        discount_account_id: Optional[str] = None,
        advance_applied: float = 0.0,
        voucher_type: VoucherType = VoucherType.SALES_INVOICE,
    ) -> Voucher:
        customer = self._account_repo.find_by_id(customer_account_id)
        income = self._account_repo.find_by_id(income_account_id)
        discount = (
            self._account_repo.find_by_id(discount_account_id)
            if discount_account_id
            else None
        )
        advance = self.get_advance_from_customers_account() if advance_applied > 0 else None
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_sales_invoice_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            income_account_id=income.id,
            income_account_name=income.account_name,
            amount=amount,
            reference_order_id=reference_order_id,
            reference_invoice_id=reference_invoice_id,
            discount_amount=discount_amount,
            discount_account_id=discount.id if discount else None,
            discount_account_name=discount.account_name if discount else None,
            advance_account_id=advance.id if advance else None,
            advance_account_name=advance.account_name if advance else None,
            advance_applied=advance_applied,
            voucher_type=voucher_type,
        )
        return self._domain.save_voucher(voucher)

    def update_sales_invoice(
        self,
        voucher_id: str,
        customer_account_id: str,
        income_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        discount_amount: float = 0.0,
        discount_account_id: Optional[str] = None,
        advance_applied: float = 0.0,
        voucher_type: Optional[VoucherType] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old:
            raise ValueError("Sales voucher not found")
        customer = self._account_repo.find_by_id(customer_account_id)
        income = self._account_repo.find_by_id(income_account_id)
        discount = (
            self._account_repo.find_by_id(discount_account_id)
            if discount_account_id
            else None
        )
        advance = self.get_advance_from_customers_account() if advance_applied > 0 else None
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_sales_invoice_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            income_account_id=income.id,
            income_account_name=income.account_name,
            amount=amount,
            reference_order_id=old.reference_order_id,
            reference_invoice_id=old.reference_invoice_id,
            discount_amount=discount_amount,
            discount_account_id=discount.id if discount else None,
            discount_account_name=discount.account_name if discount else None,
            advance_account_id=advance.id if advance else None,
            advance_account_name=advance.account_name if advance else None,
            advance_applied=advance_applied,
            voucher_type=voucher_type or old.voucher_type,
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def create_customization_gst_invoice(
        self,
        customer_account_id: str,
        income_account_id: str,
        invoice: "Invoice",
        description: str,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
        reference_invoice_id: Optional[str] = None,
        advance_applied: float = 0.0,
    ) -> Voucher:
        from vaybooks.bms.domain.invoices.entities import Invoice

        if not isinstance(invoice, Invoice):
            raise ValueError("Invoice entity required")
        customer = self._account_repo.find_by_id(customer_account_id)
        income = self._account_repo.find_by_id(income_account_id)
        if not customer or not income:
            raise ValueError("Customer or income account not found")
        advance = self.get_advance_from_customers_account() if advance_applied > 0 else None
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_customization_gst_invoice_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            income_account_id=income.id,
            income_account_name=income.account_name,
            taxable_amount=invoice.taxable_amount or invoice.net_amount,
            cgst_amount=invoice.cgst_amount,
            sgst_amount=invoice.sgst_amount,
            igst_amount=invoice.igst_amount,
            utgst_amount=invoice.utgst_amount,
            reference_order_id=reference_order_id,
            reference_invoice_id=reference_invoice_id,
            advance_account_id=advance.id if advance else None,
            advance_account_name=advance.account_name if advance else None,
            advance_applied=advance_applied,
            gst_output_accounts=self.get_gst_output_accounts(),
            voucher_type=VoucherType.CUSTOMIZATION_INVOICE,
        )
        return self._domain.save_voucher(voucher)

    def update_customization_gst_invoice(
        self,
        voucher_id: str,
        customer_account_id: str,
        income_account_id: str,
        invoice: "Invoice",
        description: str,
        voucher_date: Optional[date] = None,
        advance_applied: float = 0.0,
    ) -> Voucher:
        from vaybooks.bms.domain.invoices.entities import Invoice

        if not isinstance(invoice, Invoice):
            raise ValueError("Invoice entity required")
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old:
            raise ValueError("Sales voucher not found")
        customer = self._account_repo.find_by_id(customer_account_id)
        income = self._account_repo.find_by_id(income_account_id)
        if not customer or not income:
            raise ValueError("Customer or income account not found")
        advance = self.get_advance_from_customers_account() if advance_applied > 0 else None
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_customization_gst_invoice_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            income_account_id=income.id,
            income_account_name=income.account_name,
            taxable_amount=invoice.taxable_amount or invoice.net_amount,
            cgst_amount=invoice.cgst_amount,
            sgst_amount=invoice.sgst_amount,
            igst_amount=invoice.igst_amount,
            utgst_amount=invoice.utgst_amount,
            reference_order_id=old.reference_order_id,
            reference_invoice_id=old.reference_invoice_id,
            advance_account_id=advance.id if advance else None,
            advance_account_name=advance.account_name if advance else None,
            advance_applied=advance_applied,
            gst_output_accounts=self.get_gst_output_accounts(),
            voucher_type=old.voucher_type,
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def create_cash_sales_invoice(
        self,
        customer_account_id: str,
        store_account_id: str,
        gross_amount: float,
        discount_amount: float,
        amount_received: float,
        store_invoice_number: str,
        line_items_note: str = "",
        voucher_date: Optional[date] = None,
        reference_so_id: Optional[str] = None,
        reference_dn_id: Optional[str] = None,
        sales_lines: Optional[list[dict]] = None,
        gst_output_accounts: Optional[dict] = None,
    ) -> Voucher:
        customer = self._account_repo.find_by_id(customer_account_id)
        store = self._account_repo.find_by_id(store_account_id)
        sales = self.get_sales_account()
        if not customer:
            raise ValueError("Customer account not found")
        if not store:
            raise ValueError("Store account not found")
        if not sales:
            raise ValueError('No "Sales" revenue account found')
        discount_account = (
            self.get_discount_account() if discount_amount > 0 and not sales_lines else None
        )
        number = (store_invoice_number or "").strip()
        if not number:
            raise ValueError("Store invoice number is required")
        description = f"Store invoice {number}"
        if line_items_note.strip():
            description = f"{description}\n{line_items_note.strip()}"
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        if sales_lines and not gst_output_accounts:
            gst_output_accounts = self.get_gst_output_accounts()
        voucher = self._domain.build_cash_sales_invoice_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            sales_account_id=sales.id,
            sales_account_name=sales.account_name,
            store_account_id=store.id,
            store_account_name=store.account_name,
            gross_amount=gross_amount,
            discount_amount=discount_amount,
            amount_received=amount_received,
            discount_account_id=discount_account.id if discount_account else None,
            discount_account_name=discount_account.account_name if discount_account else None,
            reference_so_id=reference_so_id,
            reference_dn_id=reference_dn_id,
            sales_lines=sales_lines,
            gst_output_accounts=gst_output_accounts,
        )
        return self._domain.save_voucher(voucher)

    def update_cash_sales_invoice(
        self,
        voucher_id: str,
        customer_account_id: str,
        store_account_id: str,
        gross_amount: float,
        discount_amount: float,
        amount_received: float,
        store_invoice_number: str,
        line_items_note: str = "",
        voucher_date: Optional[date] = None,
        sales_lines: Optional[list[dict]] = None,
        allow_erp_linked: bool = False,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old or old.voucher_type != VoucherType.SALES_INVOICE:
            raise ValueError("Sales invoice not found")
        assert_invoice_editable(old.voucher_date)
        if old.reference_order_id or old.reference_invoice_id:
            raise ValueError("Order-linked sales invoices cannot be edited here")
        if (old.reference_so_id or old.reference_dn_id) and not allow_erp_linked:
            raise ValueError("ERP-linked sales invoices cannot be edited here")
        assert_invoice_editable(voucher_date or old.voucher_date)
        customer = self._account_repo.find_by_id(customer_account_id)
        store = self._account_repo.find_by_id(store_account_id)
        sales = self.get_sales_account()
        if not customer:
            raise ValueError("Customer account not found")
        if not store:
            raise ValueError("Store account not found")
        if not sales:
            raise ValueError('No "Sales" revenue account found')
        discount_account = (
            self.get_discount_account()
            if discount_amount > 0 and not sales_lines
            else None
        )
        number = (store_invoice_number or "").strip()
        if not number:
            raise ValueError("Store invoice number is required")
        description = f"Store invoice {number}"
        if line_items_note.strip():
            description = f"{description}\n{line_items_note.strip()}"
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_cash_sales_invoice_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            sales_account_id=sales.id,
            sales_account_name=sales.account_name,
            store_account_id=store.id,
            store_account_name=store.account_name,
            gross_amount=gross_amount,
            discount_amount=discount_amount,
            amount_received=amount_received,
            discount_account_id=discount_account.id if discount_account else None,
            discount_account_name=discount_account.account_name if discount_account else None,
            reference_so_id=old.reference_so_id,
            reference_dn_id=old.reference_dn_id,
            sales_lines=sales_lines,
            gst_output_accounts=(
                self.get_gst_output_accounts() if sales_lines else None
            ),
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def create_advance_refund(
        self,
        customer_account_id: str,
        store_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        customer = self._account_repo.find_by_id(customer_account_id)
        store = self._account_repo.find_by_id(store_account_id)
        if not customer or not store:
            raise ValueError("Customer or store account not found")
        if reference_order_id:
            available = self.get_order_unapplied_advance(reference_order_id)
            if amount > available:
                raise ValueError(
                    f"Refund amount exceeds unapplied advance (₹{available:,.2f} available)"
                )
        advance = self.get_advance_from_customers_account()
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_advance_refund_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            advance_account_id=advance.id,
            advance_account_name=advance.account_name,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            store_account_id=store.id,
            store_account_name=store.account_name,
            amount=amount,
            reference_order_id=reference_order_id,
        )
        return self._domain.save_voucher(voucher)

    def update_advance_refund(
        self,
        voucher_id: str,
        customer_account_id: str,
        store_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old or not old.is_advance_refund:
            raise ValueError("Advance refund not found")
        customer = self._account_repo.find_by_id(customer_account_id)
        store = self._account_repo.find_by_id(store_account_id)
        if not customer or not store:
            raise ValueError("Customer or store account not found")
        if old.reference_order_id:
            available = self.get_order_unapplied_advance(old.reference_order_id)
            available += old.cash_movement_amount
            if amount > available:
                raise ValueError(
                    f"Refund amount exceeds unapplied advance (₹{available:,.2f} available)"
                )
        advance = self.get_advance_from_customers_account()
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_advance_refund_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            advance_account_id=advance.id,
            advance_account_name=advance.account_name,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            store_account_id=store.id,
            store_account_name=store.account_name,
            amount=amount,
            reference_order_id=old.reference_order_id,
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def create_customer_payment_refund(
        self,
        customer_account_id: str,
        store_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        customer = self._account_repo.find_by_id(customer_account_id)
        store = self._account_repo.find_by_id(store_account_id)
        if not customer or not store:
            raise ValueError("Customer or store account not found")
        if reference_order_id:
            available = self.get_order_refundable_customer_payments(reference_order_id)
            if amount > available:
                raise ValueError(
                    f"Refund exceeds refundable customer payments (₹{available:,.2f} available)"
                )
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_customer_payment_refund_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            store_account_id=store.id,
            store_account_name=store.account_name,
            amount=amount,
            reference_order_id=reference_order_id,
        )
        return self._domain.save_voucher(voucher)

    def update_customer_payment_refund(
        self,
        voucher_id: str,
        customer_account_id: str,
        store_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old or old.is_advance_refund:
            raise ValueError("Customer payment refund not found")
        customer = self._account_repo.find_by_id(customer_account_id)
        store = self._account_repo.find_by_id(store_account_id)
        if not customer or not store:
            raise ValueError("Customer or store account not found")
        if old.reference_order_id:
            available = self.get_order_refundable_customer_payments(
                old.reference_order_id, exclude_voucher_id=old.id
            )
            if amount > available:
                raise ValueError(
                    f"Refund exceeds refundable customer payments (₹{available:,.2f} available)"
                )
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_customer_payment_refund_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            store_account_id=store.id,
            store_account_name=store.account_name,
            amount=amount,
            reference_order_id=old.reference_order_id,
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def create_refund(
        self,
        customer_account_id: str,
        store_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
        *,
        refund_type: str = "advance",
    ) -> Voucher:
        if refund_type == "payment":
            return self.create_customer_payment_refund(
                customer_account_id,
                store_account_id,
                amount,
                description,
                voucher_date,
                reference_order_id,
            )
        return self.create_advance_refund(
            customer_account_id,
            store_account_id,
            amount,
            description,
            voucher_date,
            reference_order_id,
        )

    def update_refund(
        self,
        voucher_id: str,
        customer_account_id: str,
        store_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        *,
        refund_type: Optional[str] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old:
            raise ValueError("Refund not found")
        is_advance = old.is_advance_refund if refund_type is None else refund_type == "advance"
        if is_advance:
            return self.update_advance_refund(
                voucher_id,
                customer_account_id,
                store_account_id,
                amount,
                description,
                voucher_date,
            )
        return self.update_customer_payment_refund(
            voucher_id,
            customer_account_id,
            store_account_id,
            amount,
            description,
            voucher_date,
        )

    def get_discount_account(self) -> Optional[Account]:
        for account in self._account_repo.list_all():
            if account.account_name.strip().lower() == "discount allowed":
                return account
        return None

    def void_voucher(self, voucher_id: str) -> None:
        voucher = self._voucher_repo.find_by_id(voucher_id)
        if voucher and voucher.voucher_type == VoucherType.SALES_INVOICE:
            assert_invoice_editable(voucher.voucher_date)
        self._domain.reverse_and_delete_voucher(voucher_id)

    def create_journal_entry(
        self,
        description: str,
        lines: List[dict],
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher_lines = [
            VoucherLine(
                account_id=l["account_id"],
                account_name=l["account_name"],
                debit_amount=l.get("debit_amount", 0),
                credit_amount=l.get("credit_amount", 0),
                description=l.get("description", ""),
            )
            for l in lines
        ]
        voucher = self._domain.build_journal_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            lines=voucher_lines,
        )
        return self._domain.save_voucher(voucher)

    def get_account_ledger(self, account_id: str) -> List[dict]:
        vouchers = self._voucher_repo.list_by_account(account_id)
        ledger = []
        for v in vouchers:
            for line in v.lines:
                if line.account_id == account_id:
                    ledger.append(
                        {
                            "voucher_number": v.voucher_number,
                            "voucher_date": v.voucher_date,
                            "description": line.description or v.description,
                            "debit": line.debit_amount,
                            "credit": line.credit_amount,
                        }
                    )
        return ledger

    def get_trial_balance(self) -> List[dict]:
        return self._domain.get_trial_balance()

    def list_vouchers(self) -> List[Voucher]:
        return self._voucher_repo.list_all()

    def list_vouchers_by_type(self, voucher_type: VoucherType) -> List[Voucher]:
        return [
            v for v in self._voucher_repo.list_all() if v.voucher_type == voucher_type
        ]

    def list_vouchers_by_types(self, voucher_types: list[VoucherType]) -> List[Voucher]:
        allowed = set(voucher_types)
        return [v for v in self._voucher_repo.list_all() if v.voucher_type in allowed]

    def create_purchase_bill(
        self,
        vendor_account_id: str,
        expense_lines: list[dict],
        vendor_bill_number: str,
        amount_paid: float = 0.0,
        paying_account_id: Optional[str] = None,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
        reference_service_id: Optional[str] = None,
        reference_po_id: Optional[str] = None,
        reference_grn_id: Optional[str] = None,
        stock_lines: Optional[list[dict]] = None,
        landed_cost_lines: Optional[list[dict]] = None,
        stock_reference_id: Optional[str] = None,
    ) -> Voucher:
        from vaybooks.bms.domain.accounting.purchase_parsing import (
            build_purchase_description,
        )

        vendor = self._account_repo.find_by_id(vendor_account_id)
        if not vendor:
            raise ValueError("Vendor account not found")
        resolved_lines = []
        for raw in expense_lines:
            acct = self._account_repo.find_by_id(str(raw.get("expense_account_id") or ""))
            if not acct:
                raise ValueError("Expense account not found")
            line_total = round(
                float(raw.get("line_total") or raw.get("amount") or 0), 2
            )
            if line_total <= 0:
                continue
            resolved_lines.append(
                {
                    "expense_account_id": acct.id,
                    "expense_account_name": acct.account_name,
                    "amount": line_total,
                    "line_total": line_total,
                    "taxable_amount": round(
                        float(raw.get("taxable_amount") or line_total), 2
                    ),
                    "cgst_amount": round(float(raw.get("cgst_amount") or 0), 2),
                    "sgst_amount": round(float(raw.get("sgst_amount") or 0), 2),
                    "igst_amount": round(float(raw.get("igst_amount") or 0), 2),
                    "utgst_amount": round(float(raw.get("utgst_amount") or 0), 2),
                    "product_id": raw.get("product_id"),
                    "item_type": raw.get("item_type"),
                    "item_id": raw.get("item_id"),
                    "item_name": raw.get("item_name"),
                    "hsn_sac": raw.get("hsn_sac"),
                    "qty": raw.get("qty"),
                    "rate": raw.get("rate"),
                    "landed_cost_alloc": raw.get("landed_cost_alloc"),
                }
            )
        if not resolved_lines:
            raise ValueError("At least one purchase line with amount is required")
        paying = None
        if amount_paid > 0:
            if not paying_account_id:
                raise ValueError("Paying account is required when amount is paid")
            paying = self._account_repo.find_by_id(paying_account_id)
            if not paying:
                raise ValueError("Paying account not found")
        description = build_purchase_description(vendor_bill_number, resolved_lines)
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        gst_input_accounts = self.get_gst_input_accounts()
        voucher = self._domain.build_purchase_bill_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            vendor_account_id=vendor.id,
            vendor_account_name=vendor.account_name,
            expense_lines=resolved_lines,
            amount_paid=amount_paid,
            paying_account_id=paying.id if paying else None,
            paying_account_name=paying.account_name if paying else None,
            reference_order_id=reference_order_id,
            reference_service_id=reference_service_id,
            reference_po_id=reference_po_id,
            reference_grn_id=reference_grn_id,
            gst_input_accounts=gst_input_accounts,
        )
        saved = self._domain.save_voucher(voucher)
        return saved

    def update_purchase_bill(
        self,
        voucher_id: str,
        vendor_account_id: str,
        expense_lines: list[dict],
        vendor_bill_number: str,
        amount_paid: float = 0.0,
        paying_account_id: Optional[str] = None,
        voucher_date: Optional[date] = None,
        reference_service_id: Optional[str] = None,
    ) -> Voucher:
        from vaybooks.bms.domain.accounting.purchase_parsing import (
            build_purchase_description,
        )

        old = self._voucher_repo.find_by_id(voucher_id)
        if not old or old.voucher_type != VoucherType.PURCHASE_BILL:
            raise ValueError("Purchase bill not found")
        vendor = self._account_repo.find_by_id(vendor_account_id)
        if not vendor:
            raise ValueError("Vendor account not found")
        resolved_lines = []
        for raw in expense_lines:
            acct = self._account_repo.find_by_id(str(raw.get("expense_account_id") or ""))
            if not acct:
                raise ValueError("Expense account not found")
            line_total = round(
                float(raw.get("line_total") or raw.get("amount") or 0), 2
            )
            if line_total <= 0:
                continue
            resolved_lines.append(
                {
                    "expense_account_id": acct.id,
                    "expense_account_name": acct.account_name,
                    "amount": line_total,
                    "line_total": line_total,
                    "taxable_amount": round(
                        float(raw.get("taxable_amount") or line_total), 2
                    ),
                    "cgst_amount": round(float(raw.get("cgst_amount") or 0), 2),
                    "sgst_amount": round(float(raw.get("sgst_amount") or 0), 2),
                    "igst_amount": round(float(raw.get("igst_amount") or 0), 2),
                    "utgst_amount": round(float(raw.get("utgst_amount") or 0), 2),
                    "product_id": raw.get("product_id"),
                    "item_type": raw.get("item_type"),
                    "item_id": raw.get("item_id"),
                    "item_name": raw.get("item_name"),
                    "hsn_sac": raw.get("hsn_sac"),
                    "qty": raw.get("qty"),
                    "rate": raw.get("rate"),
                    "landed_cost_alloc": raw.get("landed_cost_alloc"),
                }
            )
        if not resolved_lines:
            raise ValueError("At least one purchase line with amount is required")
        paying = None
        if amount_paid > 0:
            if not paying_account_id:
                raise ValueError("Paying account is required when amount is paid")
            paying = self._account_repo.find_by_id(paying_account_id)
            if not paying:
                raise ValueError("Paying account not found")
        description = build_purchase_description(vendor_bill_number, resolved_lines)
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        gst_input_accounts = self.get_gst_input_accounts()
        voucher = self._domain.build_purchase_bill_voucher(
            voucher_number=old.voucher_number,
            voucher_date=v_date,
            description=description,
            vendor_account_id=vendor.id,
            vendor_account_name=vendor.account_name,
            expense_lines=resolved_lines,
            amount_paid=amount_paid,
            paying_account_id=paying.id if paying else None,
            paying_account_name=paying.account_name if paying else None,
            reference_order_id=old.reference_order_id,
            reference_service_id=reference_service_id
            if reference_service_id is not None
            else old.reference_service_id,
            reference_po_id=old.reference_po_id,
            reference_grn_id=old.reference_grn_id,
            gst_input_accounts=gst_input_accounts,
        )
        voucher.id = old.id
        return self._domain.update_voucher(voucher)

    def delete_purchase_bill(self, voucher_id: str) -> None:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old or old.voucher_type != VoucherType.PURCHASE_BILL:
            raise ValueError("Purchase bill not found")
        self._domain.reverse_and_delete_voucher(voucher_id)

    def create_purchase_return_voucher(
        self,
        vendor_account_id: str,
        expense_lines: list[dict],
        description: str,
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        voucher_date: Optional[date] = None,
        reference_grn_id: Optional[str] = None,
    ) -> Voucher:
        vendor = self._account_repo.find_by_id(vendor_account_id)
        if not vendor:
            raise ValueError("Vendor account not found")
        resolved_lines = []
        for raw in expense_lines:
            acct = self._account_repo.find_by_id(str(raw.get("expense_account_id") or ""))
            if not acct:
                raise ValueError("Expense account not found")
            amount = round(float(raw.get("amount") or 0), 2)
            if amount <= 0:
                continue
            resolved_lines.append(
                {
                    "expense_account_id": acct.id,
                    "expense_account_name": acct.account_name,
                    "amount": amount,
                }
            )
        refund = None
        if amount_refunded > 0:
            if not refund_account_id:
                raise ValueError("Refund account is required when refunding cash")
            refund = self._account_repo.find_by_id(refund_account_id)
            if not refund:
                raise ValueError("Refund account not found")
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_purchase_return_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            vendor_account_id=vendor.id,
            vendor_account_name=vendor.account_name,
            expense_lines=resolved_lines,
            amount_refunded=amount_refunded,
            refund_account_id=refund.id if refund else None,
            refund_account_name=refund.account_name if refund else None,
            reference_grn_id=reference_grn_id,
        )
        return self._domain.save_voucher(voucher)

    def create_sales_return_voucher(
        self,
        customer_account_id: str,
        return_amount: float,
        description: str,
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        voucher_date: Optional[date] = None,
        reference_dn_id: Optional[str] = None,
        source_invoice_id: Optional[str] = None,
    ) -> Voucher:
        customer = self._account_repo.find_by_id(customer_account_id)
        if not customer:
            raise ValueError("Customer account not found")
        sales = self.get_sales_account()
        if not sales:
            raise ValueError('No "Sales" revenue account found')
        refund = None
        if amount_refunded > 0:
            if not refund_account_id:
                raise ValueError("Refund account is required when refunding cash")
            refund = self._account_repo.find_by_id(refund_account_id)
            if not refund:
                raise ValueError("Refund account not found")
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_sales_return_voucher(
            voucher_number=voucher_number,
            voucher_date=v_date,
            description=description,
            customer_account_id=customer.id,
            customer_account_name=customer.account_name,
            sales_account_id=sales.id,
            sales_account_name=sales.account_name,
            return_amount=return_amount,
            amount_refunded=amount_refunded,
            refund_account_id=refund.id if refund else None,
            refund_account_name=refund.account_name if refund else None,
            reference_dn_id=reference_dn_id,
            source_invoice_id=source_invoice_id,
        )
        return self._domain.save_voucher(voucher)

    def get_account(self, account_id: str) -> Optional[Account]:
        return self._account_repo.find_by_id(account_id)

    def get_store_accounts(self) -> List[Account]:
        """Accounts flagged as store accounts (cash drawer, bank, etc.)."""
        return [a for a in self._account_repo.list_all() if a.is_store_account]
