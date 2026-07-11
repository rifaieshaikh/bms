from typing import List, Optional

from vaybooks.bms.domain.accounting.repository import AccountRepository
from vaybooks.bms.domain.accounting.services import AccountingDomainService
from vaybooks.bms.domain.vendors.entities import Vendor, VendorInput
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

    def create_vendor(self, vendor_input: VendorInput) -> Vendor:
        vendor = self._vendor_domain.create(vendor_input)
        account_name = VendorDomainService.build_account_name(vendor)
        self._accounting_domain.ensure_vendor_account(vendor.id, account_name)
        return vendor

    def search_vendors(self, query: str) -> List[Vendor]:
        if not query.strip():
            return self._vendor_repo.list_all()
        return self._vendor_repo.search(query)

    def get_vendor_detail(self, vendor_id: str) -> Optional[Vendor]:
        if not vendor_id:
            return None
        return self._vendor_repo.find_by_id(str(vendor_id))

    def update_vendor(self, vendor_id: str, vendor_input: VendorInput) -> Vendor:
        return self._vendor_domain.update(vendor_id, vendor_input)

    def list_all_vendors(self) -> List[Vendor]:
        return self._vendor_repo.list_all()
