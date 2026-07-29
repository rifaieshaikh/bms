from typing import List, Optional, TYPE_CHECKING, Tuple

from vaybooks.bms.domain.finance.accounting.repository import AccountRepository
from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.parties.commission_agents.entities import CommissionAgentInput
from vaybooks.bms.domain.parties.customers.entities import Customer, CustomerInput
from vaybooks.bms.domain.parties.customers.repository import CustomerRepository
from vaybooks.bms.domain.parties.customers.services import CustomerDomainService
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCommissionAgentError,
    ValidationError,
)

if TYPE_CHECKING:
    from vaybooks.bms.application.parties.commission_agents.service import (
        CommissionAgentAppService,
    )
    from vaybooks.bms.application.parties.segments.service import PartySegmentAppService
    from vaybooks.bms.application.settings.business.service import BusinessAppService


class CustomerAppService:
    def __init__(
        self,
        customer_repo: CustomerRepository,
        account_repo: AccountRepository,
        segment_service: Optional["PartySegmentAppService"] = None,
        business_service: Optional["BusinessAppService"] = None,
        commission_agent_service: Optional["CommissionAgentAppService"] = None,
    ):
        self._customer_repo = customer_repo
        self._customer_domain = CustomerDomainService(customer_repo)
        self._accounting_domain = AccountingDomainService(account_repo, None)
        self._segments = segment_service
        self._business = business_service
        self._commission_agents = commission_agent_service

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
        return self._sync_commission_agent(customer)

    def search_customers(
        self, query: str, *, location_filter: dict | None = None
    ) -> List[Customer]:
        if not query.strip():
            return self._customer_repo.list_all(location_filter=location_filter)
        return self._customer_repo.search(query, location_filter=location_filter)

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
        return self._sync_commission_agent(customer)

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

    def list_all_customers(
        self, *, location_filter: dict | None = None
    ) -> List[Customer]:
        return self._customer_repo.list_all(location_filter=location_filter)

    def _apply_segment_names(self, customer: Customer) -> Customer:
        if self._segments:
            customer.segment_names = self._segments.names_for_ids(
                list(customer.segment_ids or [])
            )
        else:
            customer.segment_names = []
        return self._customer_repo.save(customer)

    def _sync_commission_agent(self, customer: Customer) -> Customer:
        """Create/link a commission agent party when the customer flag is on."""
        if not customer.is_commission_agent:
            return customer
        if not self._commission_agents:
            return customer
        if customer.commission_agent_id:
            existing = self._commission_agents.get_agent_detail(
                customer.commission_agent_id
            )
            if existing:
                return customer

        linked = self._commission_agents.find_by_source_customer_id(customer.id)
        if linked:
            customer.commission_agent_id = linked.id
            customer.updated_at = utc_now()
            return self._customer_repo.save(customer)

        agent_input = CommissionAgentInput(
            agent_name=customer.customer_name or customer.phone_number or "Agent",
            phone_number=customer.phone_number or "",
            alternate_phone_number=customer.alternate_phone_number,
            email=customer.email,
            contact_person=customer.contact_person,
            address_line1=customer.address_line1,
            address_line2=customer.address_line2,
            city=customer.city,
            state_code=customer.state_code,
            pincode=customer.pincode,
            country=customer.country,
            gstin=customer.gstin,
            pan=customer.pan,
            registration_type=customer.registration_type,
            msme_number=customer.msme_number,
            notes=customer.notes,
            source_customer_id=customer.id,
            location_ids=list(customer.location_ids or []),
        )
        try:
            agent = self._commission_agents.create_agent(agent_input)
        except DuplicateCommissionAgentError as exc:
            agent = self._commission_agents.get_agent_detail(exc.existing_agent_id)
            if not agent:
                raise
            if not agent.source_customer_id:
                agent.source_customer_id = customer.id
                self._commission_agents._agent_repo.save(agent)
        customer.commission_agent_id = agent.id
        customer.updated_at = utc_now()
        return self._customer_repo.save(customer)
