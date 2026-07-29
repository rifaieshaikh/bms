from typing import Optional

from vaybooks.bms.domain.parties.delivery_partners.entities import (
    DeliveryPartner,
    DeliveryPartnerInput,
)
from vaybooks.bms.domain.parties.delivery_partners.repository import (
    DeliveryPartnerRepository,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.party_location import require_location_ids
from vaybooks.bms.domain.shared.party_validation import normalize_party_fields


class DeliveryPartnerDomainService:
    def __init__(self, repo: DeliveryPartnerRepository):
        self._repo = repo

    def create(self, data: DeliveryPartnerInput) -> DeliveryPartner:
        normalized = self._validate_and_normalize(data)
        self._check_duplicates(normalized, exclude_id=None)
        partner = DeliveryPartner.from_input(normalized)
        return self._repo.save(partner)

    def update(self, partner_id: str, data: DeliveryPartnerInput) -> DeliveryPartner:
        partner = self._repo.find_by_id(partner_id)
        if not partner:
            raise ValidationError("Delivery partner not found")
        normalized = self._validate_and_normalize(data)
        self._check_duplicates(normalized, exclude_id=partner_id)
        partner.apply_input(normalized)
        return self._repo.save(partner)

    def _validate_and_normalize(self, data: DeliveryPartnerInput) -> DeliveryPartnerInput:
        party = normalize_party_fields(
            name=data.partner_name,
            phone_number=data.phone_number,
            alternate_phone_number=data.alternate_phone_number,
            email=data.email,
            contact_person="",
            address_line1=data.address_line1,
            address_line2=data.address_line2,
            city=data.city,
            state_code=data.state_code,
            pincode=data.pincode,
            country=data.country,
            gstin=data.gstin,
            pan=data.pan,
            registration_type=PartyRegistrationType.UNREGISTERED,
            msme_number="",
        )
        return DeliveryPartnerInput(
            partner_name=party.name,
            phone_number=party.phone_number,
            legal_display_name=(data.legal_display_name or party.name).strip(),
            alternate_phone_number=party.alternate_phone_number,
            email=party.email,
            address_line1=party.address_line1,
            address_line2=party.address_line2,
            city=party.city,
            state_code=party.state_code,
            pincode=party.pincode,
            country=party.country,
            gstin=party.gstin,
            pan=party.pan,
            default_expense_ledger_id=data.default_expense_ledger_id.strip(),
            payment_terms=data.payment_terms.strip(),
            is_active=bool(data.is_active),
            notes=data.notes,
            location_ids=require_location_ids(data.location_ids),
        )

    def _check_duplicates(
        self, data: DeliveryPartnerInput, exclude_id: Optional[str]
    ) -> None:
        existing_phone = self._repo.find_by_phone(data.phone_number)
        if existing_phone and existing_phone.id != exclude_id:
            raise ValidationError(
                f"A delivery partner with phone {data.phone_number} already exists."
            )
        if data.gstin:
            existing_gstin = self._repo.find_by_gstin(data.gstin)
            if existing_gstin and existing_gstin.id != exclude_id:
                raise ValidationError(
                    f"A delivery partner with GSTIN {data.gstin} already exists."
                )

    @staticmethod
    def build_account_name(partner: DeliveryPartner) -> str:
        return f"{partner.display_name} ({partner.phone_number}) — Delivery Partner"
