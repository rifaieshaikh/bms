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
    CUSTOMIZATION_INVOICE = "Customization Invoice"
    PURCHASE_EXPENSE = "Purchase Expense"
    PURCHASE_BILL = "Purchase Bill"
    PURCHASE_RETURN = "Purchase Return"
    PURCHASE_DEBIT_NOTE = "Purchase Debit Note"
    ADVANCE = "Advance"
    REFUND = "Refund"
    VENDOR_PAYMENT = "Vendor Payment"
    SALARY_PAYMENT = "Salary Payment"
    SALES_RETURN = "Sales Return"


class SalesOrderStatus(str, Enum):
    DRAFT = "Draft"
    CONFIRMED = "Confirmed"
    PARTIALLY_DELIVERED = "Partially Delivered"
    DELIVERED = "Delivered"
    CLOSED = "Closed"
    CANCELLED = "Cancelled"


class DeliveryNoteStatus(str, Enum):
    DRAFT = "Draft"
    DELIVERED = "Delivered"
    CANCELLED = "Cancelled"


class PurchaseOrderStatus(str, Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    PARTIALLY_RECEIVED = "Partially Received"
    RECEIVED = "Received"
    CLOSED = "Closed"
    CANCELLED = "Cancelled"


class GoodsReceiptStatus(str, Enum):
    DRAFT = "Draft"
    RECEIVED = "Received"
    CANCELLED = "Cancelled"


class StockMovementType(str, Enum):
    RECEIVE = "Receive"
    ISSUE = "Issue"
    ADJUST_IN = "Adjust In"
    ADJUST_OUT = "Adjust Out"
    SALE = "Sale"
    PURCHASE_RECEIVE = "Purchase Receive"
    PURCHASE_RETURN = "Purchase Return"
    SALES_RETURN = "Sales Return"


class StockReferenceType(str, Enum):
    MANUAL = "Manual"
    SALES_INVOICE = "Sales Invoice"
    PURCHASE = "Purchase"
    PURCHASE_RETURN = "Purchase Return"
    GRN = "GRN"
    DELIVERY_NOTE = "Delivery Note"
    SALES_RETURN = "Sales Return"


class PartyRegistrationType(str, Enum):
    REGISTERED = "Registered"
    UNREGISTERED = "Unregistered"
    COMPOSITION = "Composition"


VendorRegistrationType = PartyRegistrationType


class CatalogItemType(str, Enum):
    PRODUCT = "Product"
    SERVICE = "Service"
