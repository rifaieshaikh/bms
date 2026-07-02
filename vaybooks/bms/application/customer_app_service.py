from typing import List, Optional

from vaybooks.bms.domain.accounting.repository import AccountRepository
from vaybooks.bms.domain.accounting.services import AccountingDomainService
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.customers.repository import CustomerRepository
from vaybooks.bms.domain.customers.services import CustomerDomainService


class CustomerAppService:
    def __init__(
        self,
        customer_repo: CustomerRepository,
        account_repo: AccountRepository,
    ):
        self._customer_repo = customer_repo
        self._customer_domain = CustomerDomainService(customer_repo)
        self._accounting_domain = AccountingDomainService(account_repo, None)

    def create_customer(
        self,
        customer_name: str,
        phone_number: str,
        alternate_phone_number: Optional[str] = None,
        address: str = "",
        notes: str = "",
    ) -> Customer:
        customer = self._customer_domain.find_or_create(
            customer_name=customer_name,
            phone_number=phone_number,
            alternate_phone_number=alternate_phone_number,
            address=address,
            notes=notes,
        )
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
        self,
        customer_id: str,
        customer_name: str,
        phone_number: str,
        alternate_phone_number: Optional[str] = None,
        address: str = "",
        notes: str = "",
    ) -> Customer:
        customer = self._customer_repo.find_by_id(customer_id)
        if not customer:
            raise ValueError("Customer not found")
        customer.update(
            customer_name=customer_name.strip(),
            phone_number=phone_number.strip(),
            alternate_phone_number=alternate_phone_number,
            address=address,
            notes=notes,
        )
        return self._customer_repo.save(customer)

    def find_or_create_customer(
        self,
        customer_name: str,
        phone_number: str,
        **kwargs,
    ) -> Customer:
        return self.create_customer(customer_name, phone_number, **kwargs)

    def list_all_customers(self) -> List[Customer]:
        return self._customer_repo.list_all()
