class DomainError(Exception):
    """Base domain exception."""


class ValidationError(DomainError):
    """Validation failed."""


class BillNumberExistsError(DomainError):
    """Bill number already exists globally."""


class UnbalancedVoucherError(DomainError):
    """Voucher debit and credit do not match."""


class IncompleteTimeEntriesError(DomainError):
    """Time entries are incomplete for activity completion."""


class ActivityInUseError(DomainError):
    """Activity is referenced by an order and cannot be deactivated."""


class DuplicateCustomerAccountError(DomainError):
    """Customer account already exists."""


class DuplicateVendorAccountError(DomainError):
    """Vendor account already exists."""


class OrderNotReadyError(DomainError):
    """Order is not ready for the requested operation."""


class InvoiceExistsError(DomainError):
    """Invoice already exists for this order."""
