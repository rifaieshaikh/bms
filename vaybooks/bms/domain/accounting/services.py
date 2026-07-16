from typing import List, Optional

from vaybooks.bms.domain.accounting.entities import Account, Voucher, VoucherLine
from vaybooks.bms.domain.accounting.repository import AccountRepository, VoucherRepository
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCustomerAccountError,
    DuplicateVendorAccountError,
    DuplicateWorkerAccountError,
    UnbalancedVoucherError,
    ValidationError,
)


ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME = "Advance From Customers"


class AccountingDomainService:
    def __init__(
        self,
        account_repo: AccountRepository,
        voucher_repo: VoucherRepository,
    ):
        self._account_repo = account_repo
        self._voucher_repo = voucher_repo

    def create_customer_account(
        self,
        customer_id: str,
        account_name: str,
    ) -> Account:
        existing = self._account_repo.find_customer_account(customer_id)
        if existing:
            raise DuplicateCustomerAccountError(
                f"Customer account already exists for customer {customer_id}"
            )
        account = Account(
            account_name=account_name,
            account_type=AccountType.ASSET,
            linked_customer_id=customer_id,
        )
        return self._account_repo.save(account)

    def ensure_customer_account(
        self,
        customer_id: str,
        account_name: str,
    ) -> Account:
        existing = self._account_repo.find_customer_account(customer_id)
        if existing:
            return existing
        return self.create_customer_account(customer_id, account_name)

    def sync_customer_account(
        self,
        customer_id: str,
        account_name: str,
    ) -> Account:
        account = self.ensure_customer_account(customer_id, account_name)
        if account.account_name != account_name:
            account.account_name = account_name
            return self._account_repo.save(account)
        return account

    def get_advance_from_customers_account(self) -> Account:
        account = self._account_repo.find_by_name(ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME)
        if not account:
            raise ValidationError(
                f'No "{ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME}" account found. '
                "Restart the app to seed defaults or create the account in Accounts."
            )
        return account

    def create_vendor_account(
        self,
        vendor_id: str,
        account_name: str,
    ) -> Account:
        existing = self._account_repo.find_vendor_account(vendor_id)
        if existing:
            raise DuplicateVendorAccountError(
                f"Vendor account already exists for vendor {vendor_id}"
            )
        account = Account(
            account_name=account_name,
            account_type=AccountType.LIABILITY,
            linked_vendor_id=vendor_id,
        )
        return self._account_repo.save(account)

    def ensure_vendor_account(
        self,
        vendor_id: str,
        account_name: str,
    ) -> Account:
        existing = self._account_repo.find_vendor_account(vendor_id)
        if existing:
            return existing
        return self.create_vendor_account(vendor_id, account_name)

    def create_worker_salary_account(
        self,
        worker_id: str,
        account_name: str,
    ) -> Account:
        existing = self._account_repo.find_worker_account(worker_id)
        if existing:
            raise DuplicateWorkerAccountError(
                f"Salary account already exists for worker {worker_id}"
            )
        account = Account(
            account_name=account_name,
            account_type=AccountType.LIABILITY,
            linked_worker_id=worker_id,
            is_salary_account=True,
        )
        return self._account_repo.save(account)

    def ensure_worker_salary_account(
        self,
        worker_id: str,
        account_name: str,
    ) -> Account:
        existing = self._account_repo.find_worker_account(worker_id)
        if existing:
            return existing
        return self.create_worker_salary_account(worker_id, account_name)

    def sync_worker_salary_account(
        self,
        worker_id: str,
        account_name: str,
    ) -> Account:
        account = self.ensure_worker_salary_account(worker_id, account_name)
        if account.account_name != account_name:
            account.account_name = account_name
            return self._account_repo.save(account)
        return account

    def validate_voucher(self, voucher: Voucher) -> None:
        if not voucher.lines:
            raise ValidationError("Voucher must have at least one line")
        if not voucher.is_balanced:
            raise UnbalancedVoucherError(
                f"Voucher is not balanced: debit={voucher.total_debit}, "
                f"credit={voucher.total_credit}"
            )

    def save_voucher(self, voucher: Voucher) -> Voucher:
        self.validate_voucher(voucher)
        saved = self._voucher_repo.save(voucher)
        for line in voucher.lines:
            self._account_repo.update_balance(
                line.account_id,
                debit=line.debit_amount,
                credit=line.credit_amount,
            )
        return saved

    def update_voucher(self, voucher: Voucher) -> Voucher:
        """Replace an existing voucher, reversing its previous balance impact."""
        self.validate_voucher(voucher)
        old = self._voucher_repo.find_by_id(voucher.id)
        if old:
            for line in old.lines:
                self._account_repo.update_balance(
                    line.account_id,
                    debit=-line.debit_amount,
                    credit=-line.credit_amount,
                )
        saved = self._voucher_repo.save(voucher)
        for line in voucher.lines:
            self._account_repo.update_balance(
                line.account_id,
                debit=line.debit_amount,
                credit=line.credit_amount,
            )
        return saved

    def build_advance_receipt_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        receiving_account_id: str,
        receiving_account_name: str,
        customer_account_id: str,
        customer_account_name: str,
        advance_account_id: str,
        advance_account_name: str,
        amount: float,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        """Order advance: route Cash -> Customer -> Advance From Customers."""
        if amount <= 0:
            raise ValidationError("Advance amount must be positive")
        lines = [
            VoucherLine(
                account_id=receiving_account_id,
                account_name=receiving_account_name,
                debit_amount=amount,
                credit_amount=0,
                description="Cash/Bank received",
            ),
            VoucherLine(
                account_id=customer_account_id,
                account_name=customer_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Payment received",
            ),
            VoucherLine(
                account_id=customer_account_id,
                account_name=customer_account_name,
                debit_amount=amount,
                credit_amount=0,
                description="Reclassify as advance",
            ),
            VoucherLine(
                account_id=advance_account_id,
                account_name=advance_account_name,
                debit_amount=0,
                credit_amount=amount,
                description=description,
            ),
        ]
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.ADVANCE,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
            reference_order_id=reference_order_id,
        )

    def build_customer_payment_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        receiving_account_id: str,
        receiving_account_name: str,
        customer_account_id: str,
        customer_account_name: str,
        amount: float,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        """Customer payment against balance: Dr Cash/Bank, Cr Customer."""
        if amount <= 0:
            raise ValidationError("Payment amount must be positive")
        lines = [
            VoucherLine(
                account_id=receiving_account_id,
                account_name=receiving_account_name,
                debit_amount=amount,
                credit_amount=0,
                description="Cash/Bank received",
            ),
            VoucherLine(
                account_id=customer_account_id,
                account_name=customer_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Payment received",
            ),
        ]
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.RECEIPT,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
            reference_order_id=reference_order_id,
        )

    def build_vendor_payment_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        vendor_account_id: str,
        vendor_account_name: str,
        expense_account_id: str,
        expense_account_name: str,
        paying_account_id: str,
        paying_account_name: str,
        amount: float,
        reference_order_id: Optional[str] = None,
        reference_service_id: Optional[str] = None,
    ) -> Voucher:
        """Book a purchase and settle it against a vendor in one voucher.

        Four lines route the value Cash -> Vendor -> Material Purchased:
          Dr Expense (purchase booked)   Cr Vendor (payable raised)
          Dr Vendor  (payable settled)   Cr Cash/Bank (cash out)
        The vendor account nets to zero but its ledger shows both movements.
        """
        if amount <= 0:
            raise ValidationError("Vendor payment amount must be positive")
        lines = [
            VoucherLine(
                account_id=expense_account_id,
                account_name=expense_account_name,
                debit_amount=amount,
                credit_amount=0,
                description="Purchase from vendor",
            ),
            VoucherLine(
                account_id=vendor_account_id,
                account_name=vendor_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Payable to vendor",
            ),
            VoucherLine(
                account_id=vendor_account_id,
                account_name=vendor_account_name,
                debit_amount=amount,
                credit_amount=0,
                description="Payable settled",
            ),
            VoucherLine(
                account_id=paying_account_id,
                account_name=paying_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Payment made",
            ),
        ]
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.VENDOR_PAYMENT,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
            reference_order_id=reference_order_id,
            reference_service_id=reference_service_id,
        )

    def build_purchase_bill_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        vendor_account_id: str,
        vendor_account_name: str,
        expense_lines: list[dict],
        amount_paid: float = 0.0,
        paying_account_id: Optional[str] = None,
        paying_account_name: Optional[str] = None,
        reference_order_id: Optional[str] = None,
        reference_service_id: Optional[str] = None,
        reference_po_id: Optional[str] = None,
        reference_grn_id: Optional[str] = None,
        gst_input_accounts: Optional[dict] = None,
    ) -> Voucher:
        if not expense_lines:
            raise ValidationError("At least one purchase line is required")
        voucher_lines: List[VoucherLine] = []
        total_vendor_credit = 0.0
        cgst_total = sgst_total = igst_total = utgst_total = 0.0

        for raw in expense_lines:
            line_total = round(
                float(raw.get("line_total") or raw.get("amount") or 0), 2
            )
            if line_total <= 0:
                continue
            taxable = round(float(raw.get("taxable_amount") or line_total), 2)
            cgst = round(float(raw.get("cgst_amount") or 0), 2)
            sgst = round(float(raw.get("sgst_amount") or 0), 2)
            igst = round(float(raw.get("igst_amount") or 0), 2)
            utgst = round(float(raw.get("utgst_amount") or 0), 2)
            has_gst = (cgst + sgst + igst + utgst) > 0
            expense_debit = taxable if has_gst else line_total

            voucher_lines.append(
                VoucherLine(
                    account_id=str(raw["expense_account_id"]),
                    account_name=str(raw.get("expense_account_name") or ""),
                    debit_amount=expense_debit,
                    credit_amount=0,
                    description="Purchase expense",
                )
            )
            cgst_total += cgst
            sgst_total += sgst
            igst_total += igst
            utgst_total += utgst
            total_vendor_credit += line_total

        total_vendor_credit = round(total_vendor_credit, 2)
        if total_vendor_credit <= 0:
            raise ValidationError("Purchase total must be positive")

        gst_accounts = gst_input_accounts or {}
        if cgst_total > 0 and gst_accounts.get("cgst"):
            voucher_lines.append(
                VoucherLine(
                    account_id=gst_accounts["cgst"]["id"],
                    account_name=gst_accounts["cgst"]["name"],
                    debit_amount=round(cgst_total, 2),
                    credit_amount=0,
                    description="CGST input",
                )
            )
        if sgst_total > 0 and gst_accounts.get("sgst"):
            voucher_lines.append(
                VoucherLine(
                    account_id=gst_accounts["sgst"]["id"],
                    account_name=gst_accounts["sgst"]["name"],
                    debit_amount=round(sgst_total, 2),
                    credit_amount=0,
                    description="SGST input",
                )
            )
        if igst_total > 0 and gst_accounts.get("igst"):
            voucher_lines.append(
                VoucherLine(
                    account_id=gst_accounts["igst"]["id"],
                    account_name=gst_accounts["igst"]["name"],
                    debit_amount=round(igst_total, 2),
                    credit_amount=0,
                    description="IGST input",
                )
            )
        if utgst_total > 0 and gst_accounts.get("utgst"):
            voucher_lines.append(
                VoucherLine(
                    account_id=gst_accounts["utgst"]["id"],
                    account_name=gst_accounts["utgst"]["name"],
                    debit_amount=round(utgst_total, 2),
                    credit_amount=0,
                    description="UTGST input",
                )
            )

        voucher_lines.append(
            VoucherLine(
                account_id=vendor_account_id,
                account_name=vendor_account_name,
                debit_amount=0,
                credit_amount=total_vendor_credit,
                description="Payable to vendor",
            )
        )
        amount_paid = round(max(amount_paid, 0.0), 2)
        if amount_paid > total_vendor_credit + 0.01:
            raise ValidationError("Amount paid cannot exceed bill total")
        if amount_paid > 0:
            if not paying_account_id:
                raise ValidationError("Paying account is required when amount is paid")
            voucher_lines.append(
                VoucherLine(
                    account_id=vendor_account_id,
                    account_name=vendor_account_name,
                    debit_amount=amount_paid,
                    credit_amount=0,
                    description="Payable settled",
                )
            )
            voucher_lines.append(
                VoucherLine(
                    account_id=paying_account_id,
                    account_name=paying_account_name or "",
                    debit_amount=0,
                    credit_amount=amount_paid,
                    description="Payment made",
                )
            )
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.PURCHASE_BILL,
            voucher_date=voucher_date,
            description=description,
            lines=voucher_lines,
            reference_order_id=reference_order_id,
            reference_service_id=reference_service_id,
            reference_po_id=reference_po_id,
            reference_grn_id=reference_grn_id,
        )

    def build_purchase_return_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        vendor_account_id: str,
        vendor_account_name: str,
        expense_lines: list[dict],
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        refund_account_name: Optional[str] = None,
        reference_grn_id: Optional[str] = None,
    ) -> Voucher:
        if not expense_lines:
            raise ValidationError("At least one return line is required")
        total = 0.0
        voucher_lines: List[VoucherLine] = []
        for raw in expense_lines:
            amount = round(float(raw.get("amount") or 0), 2)
            if amount <= 0:
                continue
            total += amount
            voucher_lines.append(
                VoucherLine(
                    account_id=str(raw["expense_account_id"]),
                    account_name=str(raw.get("expense_account_name") or ""),
                    debit_amount=0,
                    credit_amount=amount,
                    description="Purchase return",
                )
            )
        total = round(total, 2)
        if total <= 0:
            raise ValidationError("Return total must be positive")
        voucher_lines.append(
            VoucherLine(
                account_id=vendor_account_id,
                account_name=vendor_account_name,
                debit_amount=total,
                credit_amount=0,
                description="Vendor debit note",
            )
        )
        amount_refunded = round(max(amount_refunded, 0.0), 2)
        if amount_refunded > total + 0.01:
            raise ValidationError("Refund cannot exceed return total")
        if amount_refunded > 0:
            if not refund_account_id:
                raise ValidationError("Refund account is required when refunding cash")
            voucher_lines.append(
                VoucherLine(
                    account_id=vendor_account_id,
                    account_name=vendor_account_name,
                    debit_amount=0,
                    credit_amount=amount_refunded,
                    description="Debit note settled",
                )
            )
            voucher_lines.append(
                VoucherLine(
                    account_id=refund_account_id,
                    account_name=refund_account_name or "",
                    debit_amount=amount_refunded,
                    credit_amount=0,
                    description="Cash/Bank refund",
                )
            )
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.PURCHASE_DEBIT_NOTE,
            voucher_date=voucher_date,
            description=description,
            lines=voucher_lines,
            reference_grn_id=reference_grn_id,
        )

    def build_salary_payment_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        salary_account_id: str,
        salary_account_name: str,
        expense_account_id: str,
        expense_account_name: str,
        paying_account_id: str,
        paying_account_name: str,
        amount: float,
    ) -> Voucher:
        """Route salary through a person's account in one voucher.

        Four lines move value Cash -> Salary Account -> Salary Expense:
          Dr Salary Expense (expense booked)   Cr Salary Account (payable raised)
          Dr Salary Account (payable settled)  Cr Cash/Bank (cash out)
        The salary account nets to zero but its ledger shows both movements.
        """
        if amount <= 0:
            raise ValidationError("Salary amount must be positive")
        lines = [
            VoucherLine(
                account_id=expense_account_id,
                account_name=expense_account_name,
                debit_amount=amount,
                credit_amount=0,
                description="Salary expense",
            ),
            VoucherLine(
                account_id=salary_account_id,
                account_name=salary_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Salary payable",
            ),
            VoucherLine(
                account_id=salary_account_id,
                account_name=salary_account_name,
                debit_amount=amount,
                credit_amount=0,
                description="Salary payable settled",
            ),
            VoucherLine(
                account_id=paying_account_id,
                account_name=paying_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Salary paid",
            ),
        ]
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.SALARY_PAYMENT,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
        )

    def build_sales_invoice_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        customer_account_id: str,
        customer_account_name: str,
        income_account_id: str,
        income_account_name: str,
        amount: float,
        reference_order_id: Optional[str] = None,
        reference_invoice_id: Optional[str] = None,
        discount_amount: float = 0.0,
        discount_account_id: Optional[str] = None,
        discount_account_name: Optional[str] = None,
        advance_account_id: Optional[str] = None,
        advance_account_name: Optional[str] = None,
        advance_applied: float = 0.0,
        voucher_type=None,
    ) -> Voucher:
        from vaybooks.bms.domain.shared.enums import VoucherType

        if voucher_type is None:
            voucher_type = VoucherType.SALES_INVOICE
        # `amount` is the gross invoice value (credited to income in full).
        if amount <= 0:
            raise ValidationError("Invoice amount must be positive")
        discount_amount = round(discount_amount or 0.0, 2)
        if discount_amount < 0:
            raise ValidationError("Discount cannot be negative")
        if discount_amount >= amount:
            raise ValidationError("Discount cannot equal or exceed the invoice amount")
        if discount_amount > 0 and not discount_account_id:
            raise ValidationError("A discount account is required to post a discount")

        net_amount = round(amount - discount_amount, 2)
        advance_applied = round(max(advance_applied or 0.0, 0.0), 2)
        if advance_applied > net_amount:
            raise ValidationError("Advance applied cannot exceed the net invoice amount")
        if advance_applied > 0 and not advance_account_id:
            raise ValidationError(
                f'An "{ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME}" account is required to apply advance'
            )

        lines = [
            VoucherLine(
                account_id=customer_account_id,
                account_name=customer_account_name,
                debit_amount=amount,
                credit_amount=0,
                description=description,
            ),
            VoucherLine(
                account_id=income_account_id,
                account_name=income_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Sales invoice",
            ),
        ]
        if advance_applied > 0:
            lines.extend(
                [
                    VoucherLine(
                        account_id=advance_account_id,
                        account_name=advance_account_name or ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME,
                        debit_amount=advance_applied,
                        credit_amount=0,
                        description="Advance applied",
                    ),
                    VoucherLine(
                        account_id=customer_account_id,
                        account_name=customer_account_name,
                        debit_amount=0,
                        credit_amount=advance_applied,
                        description="Advance applied",
                    ),
                ]
            )
        if discount_amount > 0:
            lines.extend(
                [
                    VoucherLine(
                        account_id=discount_account_id,
                        account_name=discount_account_name or "Discount Allowed",
                        debit_amount=discount_amount,
                        credit_amount=0,
                        description="Discount allowed",
                    ),
                    VoucherLine(
                        account_id=customer_account_id,
                        account_name=customer_account_name,
                        debit_amount=0,
                        credit_amount=discount_amount,
                        description="Discount allowed",
                    ),
                ]
            )
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=voucher_type,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
            reference_order_id=reference_order_id,
            reference_invoice_id=reference_invoice_id,
        )

    def build_cash_sales_invoice_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        customer_account_id: str,
        customer_account_name: str,
        sales_account_id: str,
        sales_account_name: str,
        store_account_id: str,
        store_account_name: str,
        gross_amount: float,
        discount_amount: float = 0.0,
        amount_received: float = 0.0,
        discount_account_id: Optional[str] = None,
        discount_account_name: Optional[str] = None,
        reference_so_id: Optional[str] = None,
        reference_dn_id: Optional[str] = None,
        sales_lines: Optional[list[dict]] = None,
        gst_output_accounts: Optional[dict] = None,
    ) -> Voucher:
        """Cash sale: book revenue, optional GST output, discount, and payment."""
        from vaybooks.bms.domain.shared.enums import VoucherType

        discount_amount = round(discount_amount or 0.0, 2)
        amount_received = round(amount_received, 2)
        if amount_received < 0:
            raise ValidationError("Amount received cannot be negative")
        if discount_amount > 0 and not discount_account_id:
            raise ValidationError("A discount account is required to post a discount")

        if sales_lines:
            taxable_total = round(
                sum(float(raw.get("taxable_amount") or 0) for raw in sales_lines), 2
            )
            cgst_total = round(
                sum(float(raw.get("cgst_amount") or 0) for raw in sales_lines), 2
            )
            sgst_total = round(
                sum(float(raw.get("sgst_amount") or 0) for raw in sales_lines), 2
            )
            igst_total = round(
                sum(float(raw.get("igst_amount") or 0) for raw in sales_lines), 2
            )
            utgst_total = round(
                sum(float(raw.get("utgst_amount") or 0) for raw in sales_lines), 2
            )
            grand_total = round(
                sum(float(raw.get("line_total") or 0) for raw in sales_lines), 2
            )
            if grand_total <= 0:
                raise ValidationError("Invoice amount must be positive")
            if discount_amount > 0:
                raise ValidationError(
                    "Invoice discount must be applied to line taxable before posting"
                )
            net_amount = grand_total
            if amount_received > net_amount:
                raise ValidationError("Amount received cannot exceed net due")

            lines = [
                VoucherLine(
                    account_id=customer_account_id,
                    account_name=customer_account_name,
                    debit_amount=grand_total,
                    credit_amount=0,
                    description=description,
                ),
                VoucherLine(
                    account_id=sales_account_id,
                    account_name=sales_account_name,
                    debit_amount=0,
                    credit_amount=taxable_total,
                    description="Sales invoice",
                ),
            ]
            gst_accounts = gst_output_accounts or {}
            gst_totals = [
                ("cgst", cgst_total, "CGST"),
                ("sgst", sgst_total, "SGST"),
                ("igst", igst_total, "IGST"),
                ("utgst", utgst_total, "UTGST"),
            ]
            for key, total, label in gst_totals:
                if total <= 0:
                    continue
                account = gst_accounts.get(key)
                if not account:
                    raise ValidationError(
                        f'"{label} Output" account not found — it is required '
                        f"to post ₹{total:,.2f} of {label}. Create the account "
                        "or restart the app to seed it."
                    )
                lines.append(
                    VoucherLine(
                        account_id=account["id"],
                        account_name=account["name"],
                        debit_amount=0,
                        credit_amount=total,
                        description=f"{label} output",
                    )
                )
        else:
            gross_amount = round(gross_amount, 2)
            if gross_amount <= 0:
                raise ValidationError("Invoice amount must be positive")
            if discount_amount < 0:
                raise ValidationError("Discount cannot be negative")
            if discount_amount >= gross_amount:
                raise ValidationError("Discount cannot equal or exceed the invoice amount")
            net_amount = round(gross_amount - discount_amount, 2)
            if amount_received > net_amount:
                raise ValidationError("Amount received cannot exceed net due")

            lines = [
                VoucherLine(
                    account_id=customer_account_id,
                    account_name=customer_account_name,
                    debit_amount=gross_amount,
                    credit_amount=0,
                    description=description,
                ),
                VoucherLine(
                    account_id=sales_account_id,
                    account_name=sales_account_name,
                    debit_amount=0,
                    credit_amount=gross_amount,
                    description="Sales invoice",
                ),
            ]
            if discount_amount > 0:
                lines.extend(
                    [
                        VoucherLine(
                            account_id=discount_account_id,
                            account_name=discount_account_name or "Discount Allowed",
                            debit_amount=discount_amount,
                            credit_amount=0,
                            description="Discount allowed",
                        ),
                        VoucherLine(
                            account_id=customer_account_id,
                            account_name=customer_account_name,
                            debit_amount=0,
                            credit_amount=discount_amount,
                            description="Discount allowed",
                        ),
                    ]
                )

        if amount_received > 0:
            lines.extend(
                [
                    VoucherLine(
                        account_id=store_account_id,
                        account_name=store_account_name,
                        debit_amount=amount_received,
                        credit_amount=0,
                        description="Cash/Bank received",
                    ),
                    VoucherLine(
                        account_id=customer_account_id,
                        account_name=customer_account_name,
                        debit_amount=0,
                        credit_amount=amount_received,
                        description="Payment received",
                    ),
                ]
            )
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.SALES_INVOICE,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
            reference_so_id=reference_so_id,
            reference_dn_id=reference_dn_id,
        )

    def build_sales_return_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        customer_account_id: str,
        customer_account_name: str,
        sales_account_id: str,
        sales_account_name: str,
        return_amount: float,
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        refund_account_name: Optional[str] = None,
        reference_dn_id: Optional[str] = None,
        source_invoice_id: Optional[str] = None,
    ) -> Voucher:
        return_amount = round(return_amount, 2)
        if return_amount <= 0:
            raise ValidationError("Return total must be positive")
        amount_refunded = round(max(amount_refunded, 0.0), 2)
        if amount_refunded > return_amount + 0.01:
            raise ValidationError("Refund cannot exceed return total")
        lines = [
            VoucherLine(
                account_id=sales_account_id,
                account_name=sales_account_name,
                debit_amount=return_amount,
                credit_amount=0,
                description="Sales return",
            ),
            VoucherLine(
                account_id=customer_account_id,
                account_name=customer_account_name,
                debit_amount=0,
                credit_amount=return_amount,
                description="Customer credit note",
            ),
        ]
        if amount_refunded > 0:
            if not refund_account_id:
                raise ValidationError("Refund account is required when refunding cash")
            lines.extend(
                [
                    VoucherLine(
                        account_id=customer_account_id,
                        account_name=customer_account_name,
                        debit_amount=amount_refunded,
                        credit_amount=0,
                        description="Credit note settled",
                    ),
                    VoucherLine(
                        account_id=refund_account_id,
                        account_name=refund_account_name or "",
                        debit_amount=0,
                        credit_amount=amount_refunded,
                        description="Cash/Bank refund",
                    ),
                ]
            )
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.SALES_RETURN,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
            reference_invoice_id=source_invoice_id,
            reference_dn_id=reference_dn_id,
        )

    def build_advance_refund_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        advance_account_id: str,
        advance_account_name: str,
        customer_account_id: str,
        customer_account_name: str,
        store_account_id: str,
        store_account_name: str,
        amount: float,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        """Refund unused advance: Advance -> Customer -> Cash."""
        if amount <= 0:
            raise ValidationError("Refund amount must be positive")
        lines = [
            VoucherLine(
                account_id=advance_account_id,
                account_name=advance_account_name,
                debit_amount=amount,
                credit_amount=0,
                description=description,
            ),
            VoucherLine(
                account_id=customer_account_id,
                account_name=customer_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Advance released",
            ),
            VoucherLine(
                account_id=customer_account_id,
                account_name=customer_account_name,
                debit_amount=amount,
                credit_amount=0,
                description="Refund payable",
            ),
            VoucherLine(
                account_id=store_account_id,
                account_name=store_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Refund paid",
            ),
        ]
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.REFUND,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
            reference_order_id=reference_order_id,
        )

    def build_customer_payment_refund_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        customer_account_id: str,
        customer_account_name: str,
        store_account_id: str,
        store_account_name: str,
        amount: float,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        """Refund a customer payment: Dr Customer, Cr Cash/Bank."""
        if amount <= 0:
            raise ValidationError("Refund amount must be positive")
        lines = [
            VoucherLine(
                account_id=customer_account_id,
                account_name=customer_account_name,
                debit_amount=amount,
                credit_amount=0,
                description=description,
            ),
            VoucherLine(
                account_id=store_account_id,
                account_name=store_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Refund paid",
            ),
        ]
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.REFUND,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
            reference_order_id=reference_order_id,
        )

    def build_release_advance_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        advance_account_id: str,
        advance_account_name: str,
        customer_account_id: str,
        customer_account_name: str,
        amount: float,
        reference_order_id: Optional[str] = None,
    ) -> Voucher:
        """Move unapplied order advance to customer credit on order close."""
        if amount <= 0:
            raise ValidationError("Release amount must be positive")
        lines = [
            VoucherLine(
                account_id=advance_account_id,
                account_name=advance_account_name,
                debit_amount=amount,
                credit_amount=0,
                description="Advance released to customer",
            ),
            VoucherLine(
                account_id=customer_account_id,
                account_name=customer_account_name,
                debit_amount=0,
                credit_amount=amount,
                description="Advance released to customer",
            ),
        ]
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.JOURNAL,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
            reference_order_id=reference_order_id,
        )

    def reverse_and_delete_voucher(self, voucher_id: str) -> None:
        """Remove a voucher and undo its impact on account balances."""
        old = self._voucher_repo.find_by_id(voucher_id)
        if not old:
            return
        for line in old.lines:
            self._account_repo.update_balance(
                line.account_id,
                debit=-line.debit_amount,
                credit=-line.credit_amount,
            )
        self._voucher_repo.delete(voucher_id)

    def build_journal_voucher(
        self,
        voucher_number: str,
        voucher_date,
        description: str,
        lines: List[VoucherLine],
    ) -> Voucher:
        return Voucher(
            voucher_number=voucher_number,
            voucher_type=VoucherType.JOURNAL,
            voucher_date=voucher_date,
            description=description,
            lines=lines,
        )

    def get_trial_balance(self) -> List[dict]:
        accounts = self._account_repo.list_all(active_only=False)
        return [
            {
                "account_name": a.account_name,
                "account_type": a.account_type.value,
                "debit": max(a.current_balance, 0),
                "credit": abs(min(a.current_balance, 0)),
            }
            for a in accounts
        ]
