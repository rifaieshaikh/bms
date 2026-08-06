from typing import List, Optional, TYPE_CHECKING

from vaybooks.bms.domain.finance.accounting.repository import AccountRepository
from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.parties.commission_agents.entities import (
    CommissionAgent,
    CommissionAgentInput,
)
from vaybooks.bms.domain.parties.commission_agents.repository import (
    CommissionAgentRepository,
)
from vaybooks.bms.domain.parties.commission_agents.services import (
    CommissionAgentDomainService,
)

if TYPE_CHECKING:
    from vaybooks.bms.application.parties.segments.service import PartySegmentAppService


class CommissionAgentAppService:
    def __init__(
        self,
        agent_repo: CommissionAgentRepository,
        account_repo: AccountRepository,
        segment_service: Optional["PartySegmentAppService"] = None,
    ):
        self._agent_repo = agent_repo
        self._agent_domain = CommissionAgentDomainService(agent_repo)
        self._accounting_domain = AccountingDomainService(account_repo, None)
        self._segments = segment_service

    def create_agent(self, agent_input: CommissionAgentInput) -> CommissionAgent:
        agent = self._agent_domain.create(agent_input)
        agent = self._apply_segment_names(agent)
        account_name = CommissionAgentDomainService.build_account_name(agent)
        self._accounting_domain.ensure_agent_account(agent.id, account_name)
        return agent

    def search_agents(
        self, query: str, *, location_filter: dict | None = None
    ) -> List[CommissionAgent]:
        if not query.strip():
            return self._agent_repo.list_all(location_filter=location_filter)
        return self._agent_repo.search(query, location_filter=location_filter)

    def get_agent_detail(self, agent_id: str) -> Optional[CommissionAgent]:
        if not agent_id:
            return None
        return self._agent_repo.find_by_id(str(agent_id))

    def get_agent(self, agent_id: str) -> Optional[CommissionAgent]:
        return self.get_agent_detail(agent_id)

    def update_agent(
        self, agent_id: str, agent_input: CommissionAgentInput
    ) -> CommissionAgent:
        agent = self._agent_domain.update(agent_id, agent_input)
        agent = self._apply_segment_names(agent)
        account_name = CommissionAgentDomainService.build_account_name(agent)
        self._accounting_domain.sync_agent_account(agent.id, account_name)
        return agent

    def list_all_agents(
        self, *, location_filter: dict | None = None
    ) -> List[CommissionAgent]:
        return self._agent_repo.list_all(location_filter=location_filter)

    def find_by_source_customer_id(
        self, customer_id: str
    ) -> Optional[CommissionAgent]:
        return self._agent_repo.find_by_source_customer_id(customer_id)

    def _apply_segment_names(self, agent: CommissionAgent) -> CommissionAgent:
        if self._segments:
            agent.segment_names = self._segments.names_for_ids(
                list(agent.segment_ids or [])
            )
        else:
            agent.segment_names = []
        return self._agent_repo.save(agent)
