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


class SalesReturnStatus(str, Enum):
    PENDING = "Pending Approval"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    GOODS_RECEIVED = "Goods Received"
    REFUND_PROCESSED = "Refund Processed"
    CLOSED = "Closed"


class DeliveryNoteStatus(str, Enum):
    DRAFT = "Draft"
    DELIVERED = "Delivered"
    CANCELLED = "Cancelled"


class EstimateStatus(str, Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"


class QuotationStatus(str, Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    CONVERTED = "Converted"
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


class PersonType(str, Enum):
    MEN = "Men"
    WOMEN = "Women"
    BOY_CHILD = "Boy Child"
    GIRL_CHILD = "Girl Child"
    INFANT = "Infant"


class MeasurementFieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    SELECT = "select"


class MeasurementSection(str, Enum):
    META = "Meta"
    HEAD = "Head"
    TORSO = "Torso"
    ARMS = "Arms"
    LOWER = "Lower"
    LENGTHS = "Lengths"


class AttachmentCategory(str, Enum):
    REFERENCE = "reference"
    DESIGN = "design"
    PATTERN = "pattern"
    FILE_OUT = "file_out"


class FitPreference(str, Enum):
    SLIM = "Slim"
    REGULAR = "Regular"
    COMFORT = "Comfort"


class ProjectStatus(str, Enum):
    DRAFT = "Draft"
    PLANNED = "Planned"
    ACTIVE = "Active"
    ON_HOLD = "On Hold"
    PHYSICALLY_COMPLETED = "Physically Completed"
    DLP = "DLP"
    FINANCIALLY_CLOSED = "Financially Closed"
    CANCELLED = "Cancelled"


class ProjectPartyRole(str, Enum):
    CUSTOMER = "Customer"
    VENDOR = "Vendor"
    SUBCONTRACTOR = "Subcontractor"
    OTHER = "Other"


class ProjectAppRole(str, Enum):
    """Application roles for project accounting (doc §2)."""

    OWNER = "Owner"
    ESTIMATOR = "Estimator"
    COMMERCIAL_APPROVER = "Commercial Approver"
    PROJECT_MANAGER = "Project Manager"
    SITE_ENGINEER = "Site Engineer"
    PROCUREMENT = "Procurement"
    STOREKEEPER = "Storekeeper"
    ACCOUNTANT = "Accountant"
    SUBCONTRACT_MANAGER = "Subcontract Manager"
    AUDITOR = "Auditor"


class ProjectBillingMode(str, Enum):
    FIXED = "Fixed"
    TIME_AND_MATERIAL = "Time and Material"
    RUNNING_ACCOUNT = "Running Account"
    MILESTONE = "Milestone"
    UNIT_BOQ = "Unit/BOQ"
    COST_PLUS = "Cost Plus"
    HYBRID = "Hybrid"


class PlaceOfSupplyMode(str, Enum):
    BILL_TO_STATE = "BillToState"
    SITE_STATE = "SiteState"
    MANUAL = "Manual"


class ProjectDocumentCategory(str, Enum):
    CONTRACT = "Contract"
    DRAWING = "Drawing"
    PHOTO = "Photo"
    PERMIT = "Permit"
    CORRESPONDENCE = "Correspondence"
    QUOTATION = "Quotation"
    WORK_ORDER = "WorkOrder"
    PROFORMA = "Proforma"
    RA_BILL = "RABill"
    TAX_INVOICE = "TaxInvoice"
    CREDIT_NOTE = "CreditNote"
    RECEIPT = "Receipt"
    OTHER = "Other"


class ProjectActivityStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    SKIPPED = "Skipped"


class ProjectExpenseSource(str, Enum):
    IN_HOUSE = "In House"
    OUTSOURCED = "Outsourced"
    MATERIAL = "Material"
    OTHER = "Other"


class ProjectCostCategory(str, Enum):
    MATERIAL = "Material"
    LABOUR = "Labour"
    SUBCON = "Subcon"
    EQUIPMENT = "Equipment"
    SITE_OH = "Site OH"
    HO_OH = "HO OH"
    CONTINGENCY = "Contingency"
    OTHER = "Other"


class ProjectMeasurementStatus(str, Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    ENGINEER_VERIFIED = "Engineer Verified"
    CUSTOMER_CERTIFIED = "Customer Certified"
    DISPUTED = "Disputed"
    REJECTED = "Rejected"


class ProjectRABillStatus(str, Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    CLAIMED = "Claimed"
    PARTIALLY_CERTIFIED = "Partially Certified"
    CERTIFIED = "Certified"
    INVOICED = "Invoiced"
    CANCELLED = "Cancelled"


class ProjectBoqItemType(str, Enum):
    SECTION = "Section"
    ITEM = "Item"


class ProjectProformaStatus(str, Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    CONVERTED = "Converted"
    CANCELLED = "Cancelled"


class ProjectVariationStatus(str, Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    INTERNALLY_APPROVED = "Internally Approved"
    CUSTOMER_APPROVED = "Customer Approved"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    WITHDRAWN = "Withdrawn"


class ProjectQuotationStatus(str, Enum):
    DRAFT = "Draft"
    PENDING_APPROVAL = "Pending Approval"
    APPROVED = "Approved"
    SENT = "Sent"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    CONVERTED = "Converted"
    CANCELLED = "Cancelled"
    SUPERSEDED = "Superseded"


class ProjectEnquiryStatus(str, Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    ESTIMATING = "Estimating"
    QUOTED = "Quoted"
    WON = "Won"
    LOST = "Lost"
    CANCELLED = "Cancelled"


class ProjectBudgetStatus(str, Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    APPROVED = "Approved"


class ProjectDprStatus(str, Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    APPROVED = "Approved"


class ProjectMaterialRequestStatus(str, Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    APPROVED = "Approved"
    ORDERED = "Ordered"
    CANCELLED = "Cancelled"


class ProjectRfqStatus(str, Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    COMPARED = "Compared"
    AWARDED = "Awarded"
    CANCELLED = "Cancelled"


class ProjectStockMovementType(str, Enum):
    RECEIPT = "Receipt"
    ISSUE = "Issue"
    CONSUME = "Consume"
    RETURN = "Return"
    TRANSFER = "Transfer"


class ProjectMaterialOwnership(str, Enum):
    CONTRACTOR = "Contractor"
    CUSTOMER = "Customer"


class ProjectSubcontractStatus(str, Enum):
    DRAFT = "Draft"
    ACTIVE = "Active"
    MEASURED = "Measured"
    SETTLED = "Settled"
    CANCELLED = "Cancelled"


class ProjectPettyCashStatus(str, Enum):
    OPEN = "Open"
    SETTLEMENT_PENDING = "Settlement Pending"
    SETTLED = "Settled"
    CANCELLED = "Cancelled"


class ProjectRecognitionMethod(str, Enum):
    COST = "Cost"
    PERCENT_COMPLETE = "Percent Complete"
    BILLING = "Billing"


class ProjectRecognitionStatus(str, Enum):
    DRAFT = "Draft"
    APPROVED = "Approved"
    POSTED = "Posted"


class ProjectQualityIssueType(str, Enum):
    SNAG = "Snag"
    REWORK = "Rework"
    NCR = "NCR"


class ProjectQualityIssueStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class ProjectWbsNodeType(str, Enum):
    SITE = "Site"
    ZONE = "Zone"
    BLOCK = "Block"
    FLOOR = "Floor"
    PHASE = "Phase"
    WORK_PACKAGE = "Work Package"
    ACTIVITY = "Activity"
    TASK = "Task"


class ProjectArchetype(str, Enum):
    STRUCTURAL = "Structural"
    FULL_CONSTRUCTION = "Full Construction"
    ARCHITECTURAL = "Architectural"
    INTERIOR = "Interior"
    TRUSS = "Truss"
    ALUMINIUM = "Aluminium Fabrication"
    CUSTOM = "Custom"


class ProjectScaleProfile(str, Enum):
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"


class ProjectReconcileStatus(str, Enum):
    DRAFT = "Draft"
    APPROVED = "Approved"
