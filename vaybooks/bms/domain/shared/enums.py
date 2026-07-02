from enum import Enum


class OrderStatus(str, Enum):
    DRAFT = "Draft"
    IN_PROGRESS = "In Progress"
    READY_FOR_DELIVERY = "Ready For Delivery"
    INVOICE_GENERATED = "Invoice Generated"
    DELIVERED = "Delivered"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class ActivityStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    SKIPPED = "Skipped"


class ActivityType(str, Enum):
    IN_HOUSE = "In House"
    OUTSOURCED = "Outsourced"
    MATERIAL = "Material"
    OTHER = "Other"


class ActivityCategory(str, Enum):
    IN_HOUSE_SERVICE = "In House Service"
    IN_HOUSE_MATERIAL = "In House Material"
    OUTSOURCED_SERVICE = "Outsourced Service"
    OUTSOURCED_MATERIAL = "Outsourced Material"


class ExpenseSource(str, Enum):
    IN_HOUSE = "In House"
    OUTSOURCED = "Outsourced"
    MATERIAL = "Material"
    OTHER = "Other"


class CustomizationItemStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class AccountType(str, Enum):
    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    REVENUE = "Revenue"
    EXPENSE = "Expense"


class VoucherType(str, Enum):
    RECEIPT = "Receipt"
    PAYMENT = "Payment"
    JOURNAL = "Journal"
    SALES_INVOICE = "Sales Invoice"
    PURCHASE_EXPENSE = "Purchase Expense"
    ADVANCE = "Advance"
    REFUND = "Refund"
    VENDOR_PAYMENT = "Vendor Payment"
    SALARY_PAYMENT = "Salary Payment"
