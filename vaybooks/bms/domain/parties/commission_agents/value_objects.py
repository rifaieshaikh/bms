from dataclasses import dataclass


@dataclass(frozen=True)
class CommissionAgentAccountName:
    agent_name: str
    phone_number: str

    @property
    def formatted(self) -> str:
        return f"Agent - {self.agent_name} - {self.phone_number}"
