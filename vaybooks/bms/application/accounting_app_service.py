from datetime import date, datetime
from typing import List, Optional

from vaybooks.bms.domain.accounting.entities import Account, Voucher, VoucherLine
from vaybooks.bms.domain.accounting.repository import AccountRepository, CounterRepository, VoucherRepository
from vaybooks.bms.domain.accounting.services import AccountingDomainService
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType


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

    # Accounts resolved by name/type elsewhere (invoice & discount posting). Their
    # name and type are locked so renaming/retyping can't silently break posting.
    PROTECTED_ACCOUNT_NAMES = {"sales", "customization", "discount allowed"}

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

    def create_receipt(
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
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())

        voucher = self._domain.build_receipt_voucher(
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

    def update_receipt(
        self,
        voucher_id: str,
        receiving_account_id: str,
        customer_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old:
            raise ValueError("Receipt not found")
        receiving = self._account_repo.find_by_id(receiving_account_id)
        customer = self._account_repo.find_by_id(customer_account_id)
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_receipt_voucher(
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

    def get_sales_account(self) -> Optional[Account]:
        for account in self._account_repo.list_all():
            if account.account_name.strip().lower() == "sales":
                return account
        return None

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
        voucher_type: VoucherType = VoucherType.SALES_INVOICE,
    ) -> Voucher:
        customer = self._account_repo.find_by_id(customer_account_id)
        income = self._account_repo.find_by_id(income_account_id)
        discount = (
            self._account_repo.find_by_id(discount_account_id)
            if discount_account_id
            else None
        )
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
            voucher_type=voucher_type or old.voucher_type,
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
    ) -> Voucher:
        customer = self._account_repo.find_by_id(customer_account_id)
        store = self._account_repo.find_by_id(store_account_id)
        voucher_number = self._counter_repo.next("voucher_number")
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_refund_voucher(
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

    def update_refund(
        self,
        voucher_id: str,
        customer_account_id: str,
        store_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old:
            raise ValueError("Refund not found")
        customer = self._account_repo.find_by_id(customer_account_id)
        store = self._account_repo.find_by_id(store_account_id)
        v_date = datetime.combine(voucher_date or date.today(), datetime.min.time())
        voucher = self._domain.build_refund_voucher(
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

    def get_discount_account(self) -> Optional[Account]:
        for account in self._account_repo.list_all():
            if account.account_name.strip().lower() == "discount allowed":
                return account
        return None

    def void_voucher(self, voucher_id: str) -> None:
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

    def get_account(self, account_id: str) -> Optional[Account]:
        return self._account_repo.find_by_id(account_id)

    def get_store_accounts(self) -> List[Account]:
        """Accounts flagged as store accounts (cash drawer, bank, etc.)."""
        return [a for a in self._account_repo.list_all() if a.is_store_account]
