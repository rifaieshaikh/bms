from typing import List, Optional

from vaybooks.bms.domain.accounting.repository import AccountRepository
from vaybooks.bms.domain.accounting.services import AccountingDomainService
from vaybooks.bms.domain.vendors.entities import Vendor
from vaybooks.bms.domain.vendors.repository import VendorRepository
from vaybooks.bms.domain.vendors.services import VendorDomainService


class VendorAppService:
    def __init__(
        self,
        vendor_repo: VendorRepository,
        account_repo: AccountRepository,
    ):
        self._vendor_repo = vendor_repo
        self._vendor_domain = VendorDomainService(vendor_repo)
        self._accounting_domain = AccountingDomainService(account_repo, None)

    def create_vendor(
        self,
        vendor_name: str,
        phone_number: str,
        alternate_phone_number: Optional[str] = None,
        address: str = "",
        notes: str = "",
    ) -> Vendor:
        vendor = self._vendor_domain.find_or_create(
            vendor_name=vendor_name,
            phone_number=phone_number,
            alternate_phone_number=alternate_phone_number,
            address=address,
            notes=notes,
        )
        account_name = VendorDomainService.build_account_name(vendor)
        self._accounting_domain.ensure_vendor_account(vendor.id, account_name)
        return vendor

    def search_vendors(self, query: str) -> List[Vendor]:
        if not query.strip():
            return self._vendor_repo.list_all()
        return self._vendor_repo.search(query)

    def get_vendor_detail(self, vendor_id: str) -> Optional[Vendor]:
        return self._vendor_repo.find_by_id(vendor_id)

    def update_vendor(
        self,
        vendor_id: str,
        vendor_name: str,
        phone_number: str,
        alternate_phone_number: Optional[str] = None,
        address: str = "",
        notes: str = "",
    ) -> Vendor:
        vendor = self._vendor_repo.find_by_id(vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        vendor.update(
            vendor_name=vendor_name.strip(),
            phone_number=phone_number.strip(),
            alternate_phone_number=alternate_phone_number,
            address=address,
            notes=notes,
        )
        return self._vendor_repo.save(vendor)

    def list_all_vendors(self) -> List[Vendor]:
        return self._vendor_repo.list_all()
