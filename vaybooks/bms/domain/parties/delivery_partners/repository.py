from typing import List, Optional, Protocol

from vaybooks.bms.domain.parties.delivery_partners.entities import DeliveryPartner


class DeliveryPartnerRepository(Protocol):
    def save(self, partner: DeliveryPartner) -> DeliveryPartner: ...

    def find_by_id(self, partner_id: str) -> Optional[DeliveryPartner]: ...

    def find_by_phone(self, phone: str) -> Optional[DeliveryPartner]: ...

    def find_by_gstin(self, gstin: str) -> Optional[DeliveryPartner]: ...

    def search(
        self, query: str, location_filter: dict | None = None
    ) -> List[DeliveryPartner]: ...

    def list_all(
        self, location_filter: dict | None = None
    ) -> List[DeliveryPartner]: ...

    def list_active(
        self, location_filter: dict | None = None
    ) -> List[DeliveryPartner]: ...
