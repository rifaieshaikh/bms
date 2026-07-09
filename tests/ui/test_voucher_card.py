from datetime import datetime

from vaybooks.bms.domain.accounting.entities import Voucher, VoucherLine
from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.voucher_card import (
    invoice_gross_amount,
    voucher_amount_color,
    voucher_display_amount,
    voucher_receiving_account,
    voucher_type_label,
)


def _voucher(vtype: VoucherType, lines: list[VoucherLine]) -> Voucher:
    return Voucher(
        voucher_number="VCH-001",
        voucher_type=vtype,
        voucher_date=datetime(2026, 6, 1),
        description="Test",
        lines=lines,
    )


def test_voucher_display_amount_uses_total_debit_for_receipt():
    voucher = _voucher(
        VoucherType.RECEIPT,
        [
            VoucherLine("a1", "Cash", debit_amount=500.0),
            VoucherLine("a2", "Customer", credit_amount=500.0),
        ],
    )
    assert voucher_display_amount(voucher) == 500.0


def test_voucher_display_amount_uses_first_line_for_vendor_payment():
    voucher = _voucher(
        VoucherType.VENDOR_PAYMENT,
        [
            VoucherLine("a1", "Expense", debit_amount=250.0),
            VoucherLine("a2", "Vendor", credit_amount=250.0),
        ],
    )
    assert voucher_display_amount(voucher) == 250.0


def test_invoice_gross_amount_uses_max_credit_line():
    voucher = _voucher(
        VoucherType.SALES_INVOICE,
        [
            VoucherLine("a1", "Customer", debit_amount=1000.0),
            VoucherLine("a2", "Sales", credit_amount=1000.0),
        ],
    )
    assert invoice_gross_amount(voucher) == 1000.0


def test_voucher_type_label_for_salary_payment():
    voucher = _voucher(VoucherType.SALARY_PAYMENT, [])
    assert voucher_type_label(voucher) == "Salary"
    assert voucher_type_label(voucher, short=True) == "Salary"


def test_voucher_type_label_short_vendor_payment():
    voucher = _voucher(VoucherType.VENDOR_PAYMENT, [])
    assert voucher_type_label(voucher) == "Vendor Payment"
    assert voucher_type_label(voucher, short=True) == "Vendor"


def test_voucher_receiving_account_for_receipt():
    voucher = _voucher(
        VoucherType.RECEIPT,
        [
            VoucherLine("a1", "Cash", debit_amount=500.0),
            VoucherLine("a2", "Customer", credit_amount=500.0),
        ],
    )
    assert voucher_receiving_account(voucher) == "Cash"


def test_voucher_amount_color_for_receipt_and_refund():
    assert voucher_amount_color(VoucherType.RECEIPT) == "green"
    assert voucher_amount_color(VoucherType.REFUND) == "red"
