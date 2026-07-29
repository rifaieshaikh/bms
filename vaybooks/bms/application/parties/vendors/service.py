from typing import List, Optional, TYPE_CHECKING

from vaybooks.bms.domain.finance.accounting.repository import AccountRepository
from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.parties.vendors.entities import Vendor, VendorInput
from vaybooks.bms.domain.parties.vendors.repository import VendorRepository
from vaybooks.bms.domain.parties.vendors.services import VendorDomainService

if TYPE_CHECKING:
    from vaybooks.bms.application.parties.segments.service import PartySegmentAppService


class VendorAppService:
    def __init__(
        self,
        vendor_repo: VendorRepository,
        account_repo: AccountRepository,
        segment_service: Optional["PartySegmentAppService"] = None,
    ):
        self._vendor_repo = vendor_repo
        self._vendor_domain = VendorDomainService(vendor_repo)
        self._accounting_domain = AccountingDomainService(account_repo, None)
        self._segments = segment_service

    def create_vendor(self, vendor_input: VendorInput) -> Vendor:
        vendor = self._vendor_domain.create(vendor_input)
        vendor = self._apply_segment_names(vendor)
        account_name = VendorDomainService.build_account_name(vendor)
        self._accounting_domain.ensure_vendor_account(vendor.id, account_name)
        return vendor

    def search_vendors(
        self, query: str, *, location_filter: dict | None = None
    ) -> List[Vendor]:
        if not query.strip():
            return self._vendor_repo.list_all(location_filter=location_filter)
        return self._vendor_repo.search(query, location_filter=location_filter)

    def get_vendor_detail(self, vendor_id: str) -> Optional[Vendor]:
        if not vendor_id:
            return None
        return self._vendor_repo.find_by_id(str(vendor_id))

    def update_vendor(self, vendor_id: str, vendor_input: VendorInput) -> Vendor:
        vendor = self._vendor_domain.update(vendor_id, vendor_input)
        return self._apply_segment_names(vendor)

    def list_all_vendors(
        self, *, location_filter: dict | None = None
    ) -> List[Vendor]:
        return self._vendor_repo.list_all(location_filter=location_filter)

    def _apply_segment_names(self, vendor: Vendor) -> Vendor:
        if self._segments:
            vendor.segment_names = self._segments.names_for_ids(
                list(vendor.segment_ids or [])
            )
        else:
            vendor.segment_names = []
        return self._vendor_repo.save(vendor)
