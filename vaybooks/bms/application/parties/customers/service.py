from typing import List, Optional, TYPE_CHECKING, Tuple

from vaybooks.bms.domain.finance.accounting.repository import AccountRepository
from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.parties.customers.entities import Customer, CustomerInput
from vaybooks.bms.domain.parties.customers.repository import CustomerRepository
from vaybooks.bms.domain.parties.customers.services import CustomerDomainService
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError

if TYPE_CHECKING:
    from vaybooks.bms.application.parties.segments.service import PartySegmentAppService
    from vaybooks.bms.application.settings.business.service import BusinessAppService


class CustomerAppService:
    def __init__(
        self,
        customer_repo: CustomerRepository,
        account_repo: AccountRepository,
        segment_service: Optional["PartySegmentAppService"] = None,
        business_service: Optional["BusinessAppService"] = None,
    ):
        self._customer_repo = customer_repo
        self._customer_domain = CustomerDomainService(customer_repo)
        self._accounting_domain = AccountingDomainService(account_repo, None)
        self._segments = segment_service
        self._business = business_service

    def identity_policy(self) -> Tuple[bool, bool]:
        """Return ``(require_name, require_phone)`` from business settings."""
        if self._business is None:
            return True, True
        profile = self._business.get_profile()
        return (
            bool(getattr(profile, "require_customer_name", True)),
            bool(getattr(profile, "require_customer_phone", True)),
        )

    def create_customer(self, customer_input: CustomerInput) -> Customer:
        require_name, require_phone = self.identity_policy()
        customer = self._customer_domain.create(
            customer_input,
            require_name=require_name,
            require_phone=require_phone,
        )
        customer = self._apply_segment_names(customer)
        account_name = CustomerDomainService.build_account_name(customer)
        self._accounting_domain.ensure_customer_account(customer.id, account_name)
        return customer

    def search_customers(self, query: str) -> List[Customer]:
        if not query.strip():
            return self._customer_repo.list_all()
        return self._customer_repo.search(query)

    def get_customer_detail(self, customer_id: str) -> Optional[Customer]:
        return self._customer_repo.find_by_id(customer_id)

    def update_customer(
        self, customer_id: str, customer_input: CustomerInput
    ) -> Customer:
        require_name, require_phone = self.identity_policy()
        customer = self._customer_domain.update(
            customer_id,
            customer_input,
            require_name=require_name,
            require_phone=require_phone,
        )
        customer = self._apply_segment_names(customer)
        account_name = CustomerDomainService.build_account_name(customer)
        self._accounting_domain.sync_customer_account(customer.id, account_name)
        return customer

    def set_blacklisted(
        self, customer_id: str, blacklisted: bool, reason: str = ""
    ) -> Customer:
        customer = self._customer_repo.find_by_id(customer_id)
        if not customer:
            raise ValidationError("Customer not found")
        customer.is_blacklisted = blacklisted
        customer.blacklist_reason = reason.strip() if blacklisted else ""
        customer.blacklisted_at = utc_now() if blacklisted else None
        customer.updated_at = utc_now()
        return self._customer_repo.save(customer)

    def find_or_create_customer(
        self,
        customer_name: str,
        phone_number: str,
        **kwargs,
    ) -> Customer:
        require_name, require_phone = self.identity_policy()
        customer = self._customer_domain.find_or_create(
            customer_name=customer_name,
            phone_number=phone_number,
            require_name=require_name,
            require_phone=require_phone,
            **kwargs,
        )
        account_name = CustomerDomainService.build_account_name(customer)
        self._accounting_domain.ensure_customer_account(customer.id, account_name)
        return customer

    def lookup_customer_by_phone(self, phone_number: str) -> Optional[Customer]:
        return self._customer_repo.find_by_phone(phone_number)

    def list_all_customers(self) -> List[Customer]:
        return self._customer_repo.list_all()

    def _apply_segment_names(self, customer: Customer) -> Customer:
        if self._segments:
            customer.segment_names = self._segments.names_for_ids(
                list(customer.segment_ids or [])
            )
        else:
            customer.segment_names = []
        return self._customer_repo.save(customer)
