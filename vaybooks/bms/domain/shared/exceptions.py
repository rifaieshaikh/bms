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


class DuplicateWorkerAccountError(DomainError):
    """Worker salary account already exists."""


class OrderNotReadyError(DomainError):
    """Order is not ready for the requested operation."""


class InvoiceExistsError(DomainError):
    """Invoice already exists for this order."""


class DuplicateVendorError(DomainError):
    """Vendor already exists (phone or GSTIN)."""

    def __init__(self, message: str, existing_vendor_id: str):
        super().__init__(message)
        self.existing_vendor_id = existing_vendor_id


class DuplicateCustomerError(DomainError):
    """Customer already exists (phone or GSTIN)."""

    def __init__(self, message: str, existing_customer_id: str):
        super().__init__(message)
        self.existing_customer_id = existing_customer_id
