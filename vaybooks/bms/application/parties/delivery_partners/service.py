from typing import List, Optional

from vaybooks.bms.domain.finance.accounting.repository import AccountRepository
from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.parties.delivery_partners.entities import (
    DeliveryPartner,
    DeliveryPartnerInput,
)
from vaybooks.bms.domain.parties.delivery_partners.repository import (
    DeliveryPartnerRepository,
)
from vaybooks.bms.domain.parties.delivery_partners.services import (
    DeliveryPartnerDomainService,
)


class DeliveryPartnerAppService:
    def __init__(
        self,
        partner_repo: DeliveryPartnerRepository,
        account_repo: AccountRepository,
    ):
        self._repo = partner_repo
        self._domain = DeliveryPartnerDomainService(partner_repo)
        self._accounting = AccountingDomainService(account_repo, None)

    def create_partner(self, data: DeliveryPartnerInput) -> DeliveryPartner:
        partner = self._domain.create(data)
        account_name = DeliveryPartnerDomainService.build_account_name(partner)
        self._accounting.ensure_delivery_partner_account(partner.id, account_name)
        return partner

    def update_partner(
        self, partner_id: str, data: DeliveryPartnerInput
    ) -> DeliveryPartner:
        return self._domain.update(partner_id, data)

    def get_partner(self, partner_id: str) -> Optional[DeliveryPartner]:
        if not partner_id:
            return None
        return self._repo.find_by_id(str(partner_id))

    def list_all_partners(
        self, *, location_filter: dict | None = None
    ) -> List[DeliveryPartner]:
        return self._repo.list_all(location_filter=location_filter)

    def list_active_partners(
        self, *, location_filter: dict | None = None
    ) -> List[DeliveryPartner]:
        return self._repo.list_active(location_filter=location_filter)

    def search_partners(
        self, query: str, *, location_filter: dict | None = None
    ) -> List[DeliveryPartner]:
        if not (query or "").strip():
            return self._repo.list_all(location_filter=location_filter)
        return self._repo.search(query, location_filter=location_filter)

    def get_partner_account_id(self, partner_id: str) -> Optional[str]:
        account = self._accounting.get_delivery_partner_account(partner_id)
        return account.id if account else None
