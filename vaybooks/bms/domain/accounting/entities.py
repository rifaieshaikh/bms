from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType


@dataclass
class Account:
    account_name: str
    account_type: AccountType
    id: str = field(default_factory=lambda: uuid4().hex)
    linked_customer_id: Optional[str] = None
    linked_vendor_id: Optional[str] = None
    linked_worker_id: Optional[str] = None
    opening_balance: float = 0.0
    current_balance: float = 0.0
    is_store_account: bool = False
    is_salary_account: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class VoucherLine:
    account_id: str
    account_name: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    description: str = ""
    voucher_line_id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class Voucher:
    voucher_number: str
    voucher_type: VoucherType
    voucher_date: datetime
    description: str
    lines: List[VoucherLine]
    id: str = field(default_factory=lambda: uuid4().hex)
    reference_order_id: Optional[str] = None
    reference_invoice_id: Optional[str] = None
    reference_service_id: Optional[str] = None
    reference_po_id: Optional[str] = None
    reference_grn_id: Optional[str] = None
    reference_so_id: Optional[str] = None
    reference_dn_id: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def total_debit(self) -> float:
        return sum(line.debit_amount for line in self.lines)

    @property
    def total_credit(self) -> float:
        return sum(line.credit_amount for line in self.lines)

    @property
    def is_balanced(self) -> bool:
        return abs(self.total_debit - self.total_credit) < 0.01

    @property
    def cash_movement_amount(self) -> float:
        """Actual cash in/out for routed multi-line vouchers (receipt, refund, payments)."""
        if self.voucher_type == VoucherType.REFUND and len(self.lines) == 2:
            return self.lines[-1].credit_amount if self.lines else 0.0
        if self.voucher_type == VoucherType.SALES_INVOICE:
            for line in self.lines:
                if line.debit_amount > 0 and line.description == "Cash/Bank received":
                    return line.debit_amount
        routed = (
            VoucherType.ADVANCE,
            VoucherType.RECEIPT,
            VoucherType.REFUND,
            VoucherType.VENDOR_PAYMENT,
            VoucherType.SALARY_PAYMENT,
            VoucherType.PURCHASE_BILL,
        )
        if self.voucher_type == VoucherType.PURCHASE_BILL:
            for line in self.lines:
                if line.credit_amount > 0 and line.description == "Payment made":
                    return line.credit_amount
        if self.voucher_type in routed and self.lines and self.lines[0].debit_amount > 0:
            return self.lines[0].debit_amount
        if self.voucher_type == VoucherType.RECEIPT and self.lines:
            return self.lines[0].debit_amount
        return self.total_debit

    @property
    def is_cash_sales_invoice(self) -> bool:
        return self.voucher_type == VoucherType.SALES_INVOICE and any(
            line.debit_amount > 0 and line.description == "Cash/Bank received"
            for line in self.lines
        )

    @property
    def is_advance_refund(self) -> bool:
        return self.voucher_type == VoucherType.REFUND and len(self.lines) > 2
