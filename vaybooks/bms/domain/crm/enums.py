"""CRM enumerations and default catalog keys."""

from __future__ import annotations

from enum import Enum


class CrmRole(str, Enum):
    SALES_REPRESENTATIVE = "Sales Representative"
    SALES_MANAGER = "Sales Manager"
    CRM_ADMINISTRATOR = "CRM Administrator"
    ACCOUNTS_COLLECTION = "Accounts/Collection"


class LeadPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class LeadStatus(str, Enum):
    NEW = "New"
    CONTACTED = "Contacted"
    QUALIFIED = "Qualified"
    FOLLOW_UP_REQUIRED = "Follow-up Required"
    INTERESTED = "Interested"
    NOT_INTERESTED = "Not Interested"
    CONVERTED = "Converted"
    LOST = "Lost"
    ON_HOLD = "On Hold"


class EnquiryStatus(str, Enum):
    OPEN = "Open"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    QUOTATION_REQUIRED = "Quotation Required"
    QUOTATION_SENT = "Quotation Sent"
    NEGOTIATION = "Negotiation"
    WON = "Won"
    LOST = "Lost"
    CLOSED = "Closed"
    ON_HOLD = "On Hold"


class ActivityStatus(str, Enum):
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    MISSED = "Missed"
    REVERSED = "Reversed"


class ActivityOrigin(str, Enum):
    MANUAL = "Manual"
    AUTOMATIC = "Automatic"


class NotificationKind(str, Enum):
    ACTIVITY_DUE_TODAY = "activity_due_today"
    UPCOMING_VISIT = "upcoming_visit"
    OVERDUE_FOLLOW_UP = "overdue_follow_up"
    LEAD_ASSIGNED = "lead_assigned"
    ENQUIRY_REASSIGNED = "enquiry_reassigned"
    PAYMENT_PROMISE = "payment_promise"
    HIGH_PRIORITY_IDLE = "high_priority_idle"
    PAYMENT_REMINDER_DUE = "payment_reminder_due"


class ImportBatchStatus(str, Enum):
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"


class LeadImportDuplicatePolicy(str, Enum):
    SKIP = "skip"
    UPDATE = "update"
    FAIL = "fail"
    IMPORT_AS_SEPARATE = "import_as_separate"
    LINK_TO_CUSTOMER = "link_to_customer"


# Default catalog keys (seeded in migration; configurable via settings)
DEFAULT_LEAD_SOURCES = (
    "Walk-in",
    "Phone",
    "Website",
    "Referral",
    "Campaign",
    "Sales representative",
    "Existing customer referral",
    "Imported",
    "Other",
)

DEFAULT_LEAD_STATUSES = tuple(s.value for s in LeadStatus)

DEFAULT_ENQUIRY_STATUSES = tuple(s.value for s in EnquiryStatus)

DEFAULT_ACTIVITY_TYPES = (
    "Sales Representative Visit",
    "Called",
    "Contacted for Order",
    "Contacted for Credit",
    "General Follow-up",
    "Meeting",
    "WhatsApp Message",
    "Email",
    "Note",
    "Enquiry Created",
    "Quotation Created",
    "Quotation Sent",
    "Order Placed",
    "Invoice Created",
    "Payment Received",
    "Follow-up Scheduled",
    "Lead Assigned",
    "Lead Converted",
    "Lead Lost",
    "Payment Reminder",
)

# Activity types that typically require an outcome when completed
DEFAULT_OUTCOME_REQUIRED_TYPES = (
    "Sales Representative Visit",
    "Called",
    "Contacted for Order",
    "Contacted for Credit",
    "Meeting",
    "General Follow-up",
)

DEFAULT_ACTIVITY_OUTCOMES = (
    "Interested",
    "Order Expected",
    "Follow-up Required",
    "Not Interested",
    "Customer Unavailable",
    "Payment Promised",
    "Payment Received",
    "Dispute Raised",
    "No Response",
    "Completed",
    "Other",
)

DEFAULT_LOST_REASONS = (
    "Price",
    "Competitor",
    "No budget",
    "Timing",
    "No response",
    "Not a fit",
    "Other",
)

# Canonical activity type keys for automatic events
AUTO_ACTIVITY_TYPE_KEYS = {
    "enquiry_created": "Enquiry Created",
    "quotation_created": "Quotation Created",
    "quotation_sent": "Quotation Sent",
    "order_placed": "Order Placed",
    "invoice_created": "Invoice Created",
    "payment_received": "Payment Received",
    "lead_assigned": "Lead Assigned",
    "lead_converted": "Lead Converted",
    "lead_lost": "Lead Lost",
}

CRM_SETTINGS_ID = "default"

CRM_REPORT_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("customers_with_orders", "Customers with Orders", "engagement"),
    ("customers_with_payments", "Customers with Payments", "engagement"),
    ("customers_without_activity", "Customers Without Activity", "engagement"),
    ("customers_called", "Customers Called", "engagement"),
    ("customers_visited", "Customers Visited", "engagement"),
    ("customers_not_ordered_recently", "Customers Not Ordered Recently", "engagement"),
    ("customers_never_contacted", "Customers Never Contacted", "engagement"),
    ("customers_requiring_follow_up", "Customers Requiring Follow-up", "engagement"),
    ("lead_conversion_funnel", "Lead Conversion Funnel", "conversion"),
    ("lead_conversion_by_source", "Lead Conversion by Source", "conversion"),
    ("lead_conversion_by_sales_representative", "Lead Conversion by Sales Representative", "conversion"),
    ("enquiry_conversion_report", "Enquiry Conversion Report", "conversion"),
    ("lost_leads_and_enquiries", "Lost Leads and Enquiries", "conversion"),
    ("order_generated_after_follow_up", "Order Generated After Follow-up", "conversion"),
    ("dormant_customer_reactivation", "Dormant Customer Reactivation", "conversion"),
    ("customers_contacted_for_credit", "Customers Contacted for Credit", "collection"),
    ("payment_promise_report", "Payment Promise Report", "collection"),
    ("payments_received_after_follow_up", "Payments Received After Follow-up", "collection"),
    ("overdue_collection_follow_ups", "Overdue Collection Follow-ups", "collection"),
    ("sales_representative_activity_summary", "Sales Representative Activity Summary", "rep"),
    ("scheduled_vs_completed_activities", "Scheduled vs Completed Activities", "rep"),
    ("sales_representative_visit_productivity", "Sales Representative Visit Productivity", "rep"),
    ("follow_up_effectiveness", "Follow-up Effectiveness", "rep"),
    ("high_value_leads_without_follow_up", "High-Value Leads Without Follow-up", "management"),
    ("high_value_customers_not_contacted_recently", "High-Value Customers Not Contacted Recently", "management"),
    ("customers_with_outstanding_balance_and_no_collection_activity", "Customers with Outstanding Balance and No Collection Activity", "management"),
    ("customers_with_frequent_enquiries_but_no_orders", "Customers with Frequent Enquiries but No Orders", "management"),
    ("customers_with_declining_order_frequency", "Customers with Declining Order Frequency", "management"),
    ("top_areas_by_leads_orders_and_collections", "Top Areas by Leads, Orders and Collections", "management"),
    ("upcoming_expected_orders", "Upcoming Expected Orders", "management"),
    ("upcoming_payment_promises", "Upcoming Payment Promises", "management"),
    ("overdue_activities_by_priority", "Overdue Activities by Priority", "management"),
    ("unassigned_leads_and_enquiries", "Unassigned Leads and Enquiries", "management"),
    ("duplicate_or_potentially_duplicate_leads", "Duplicate or Potentially Duplicate Leads", "management"),
)
