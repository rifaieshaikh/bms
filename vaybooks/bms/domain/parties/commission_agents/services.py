from typing import Optional

from vaybooks.bms.domain.parties.commission_agents.entities import (
    CommissionAgent,
    CommissionAgentInput,
)
from vaybooks.bms.domain.parties.commission_agents.repository import (
    CommissionAgentRepository,
)
from vaybooks.bms.domain.parties.commission_agents.value_objects import (
    CommissionAgentAccountName,
)
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCommissionAgentError,
    ValidationError,
)
from vaybooks.bms.domain.shared.party_location import require_location_ids
from vaybooks.bms.domain.shared.party_validation import (
    normalize_banking_fields,
    normalize_party_fields,
)

_COMMISSION_TYPES = {"percentage", "flat"}


class CommissionAgentDomainService:
    def __init__(self, agent_repo: CommissionAgentRepository):
        self._agent_repo = agent_repo

    def create(self, agent_input: CommissionAgentInput) -> CommissionAgent:
        normalized = self._validate_and_normalize(agent_input)
        self._check_duplicates(normalized, exclude_agent_id=None)
        agent = CommissionAgent.from_input(normalized)
        return self._agent_repo.save(agent)

    def update(
        self, agent_id: str, agent_input: CommissionAgentInput
    ) -> CommissionAgent:
        agent = self._agent_repo.find_by_id(agent_id)
        if not agent:
            raise ValidationError("Commission agent not found")
        normalized = self._validate_and_normalize(agent_input)
        self._check_duplicates(normalized, exclude_agent_id=agent_id)
        agent.apply_input(normalized)
        return self._agent_repo.save(agent)

    def _validate_and_normalize(
        self, agent_input: CommissionAgentInput
    ) -> CommissionAgentInput:
        party = normalize_party_fields(
            name=agent_input.agent_name,
            phone_number=agent_input.phone_number,
            alternate_phone_number=agent_input.alternate_phone_number,
            email=agent_input.email,
            contact_person=agent_input.contact_person,
            address_line1=agent_input.address_line1,
            address_line2=agent_input.address_line2,
            city=agent_input.city,
            state_code=agent_input.state_code,
            pincode=agent_input.pincode,
            country=agent_input.country,
            gstin=agent_input.gstin,
            pan=agent_input.pan,
            registration_type=agent_input.registration_type,
            msme_number=agent_input.msme_number,
        )
        banking = normalize_banking_fields(
            bank_account_holder=agent_input.bank_account_holder,
            bank_account_number=agent_input.bank_account_number,
            bank_ifsc=agent_input.bank_ifsc,
            bank_name=agent_input.bank_name,
        )
        commission_type = (
            agent_input.default_commission_type or "percentage"
        ).strip().lower()
        if commission_type not in _COMMISSION_TYPES:
            raise ValidationError(
                "Default commission type must be percentage or flat"
            )
        rate = round(float(agent_input.default_commission_rate or 0), 2)
        if rate < 0:
            raise ValidationError("Default commission rate cannot be negative")
        if commission_type == "percentage" and rate > 100:
            raise ValidationError("Default commission percentage cannot exceed 100")

        return CommissionAgentInput(
            agent_name=party.name,
            phone_number=party.phone_number,
            alternate_phone_number=party.alternate_phone_number,
            email=party.email,
            contact_person=party.contact_person,
            address_line1=party.address_line1,
            address_line2=party.address_line2,
            city=party.city,
            state_code=party.state_code,
            pincode=party.pincode,
            country=party.country,
            gstin=party.gstin,
            pan=party.pan,
            registration_type=party.registration_type,
            msme_number=party.msme_number,
            bank_account_holder=banking.bank_account_holder,
            bank_account_number=banking.bank_account_number,
            bank_ifsc=banking.bank_ifsc,
            bank_name=banking.bank_name,
            notes=agent_input.notes,
            default_commission_type=commission_type,
            default_commission_rate=rate,
            segment_ids=list(agent_input.segment_ids or []),
            location_ids=require_location_ids(agent_input.location_ids),
            source_customer_id=(agent_input.source_customer_id or "").strip(),
        )

    def _check_duplicates(
        self, agent_input: CommissionAgentInput, exclude_agent_id: Optional[str]
    ) -> None:
        existing_phone = self._agent_repo.find_by_phone(agent_input.phone_number)
        if existing_phone and existing_phone.id != exclude_agent_id:
            raise DuplicateCommissionAgentError(
                f"A commission agent with phone {agent_input.phone_number} already exists.",
                existing_phone.id,
            )
        if agent_input.gstin:
            existing_gstin = self._agent_repo.find_by_gstin(agent_input.gstin)
            if existing_gstin and existing_gstin.id != exclude_agent_id:
                raise DuplicateCommissionAgentError(
                    f"A commission agent with GSTIN {agent_input.gstin} already exists.",
                    existing_gstin.id,
                )

    @staticmethod
    def build_account_name(agent: CommissionAgent) -> str:
        return CommissionAgentAccountName(
            agent_name=agent.agent_name,
            phone_number=agent.phone_number,
        ).formatted
