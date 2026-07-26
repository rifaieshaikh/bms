"""Registry of scheduler jobs, preserving domain execution order."""

from __future__ import annotations

from typing import Dict, List, Optional

from vaybooks.bms.application.schedulers.protocol import JobDefinition, SchedulerJob
from vaybooks.bms.domain.schedulers.entities import DOMAIN_ORDER


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: Dict[str, SchedulerJob] = {}
        self._definitions: Dict[str, JobDefinition] = {}
        self._order: List[str] = []

    def register(self, job: SchedulerJob, definition: JobDefinition) -> None:
        job_id = definition.job_id
        if job_id not in self._jobs:
            self._order.append(job_id)
        self._jobs[job_id] = job
        self._definitions[job_id] = definition

    def get(self, job_id: str) -> Optional[SchedulerJob]:
        return self._jobs.get(job_id)

    def definition(self, job_id: str) -> Optional[JobDefinition]:
        return self._definitions.get(job_id)

    def job_ids(self) -> List[str]:
        return list(self._order)

    def definitions(self) -> List[JobDefinition]:
        """All definitions ordered by domain, then registration order."""
        rank = {domain: index for index, domain in enumerate(DOMAIN_ORDER)}
        return sorted(
            (self._definitions[jid] for jid in self._order),
            key=lambda d: (rank.get(d.domain, len(rank)), self._order.index(d.job_id)),
        )

    def definitions_for_domain(self, domain: str) -> List[JobDefinition]:
        return [d for d in self.definitions() if d.domain == domain]

    def ordered_job_ids(self) -> List[str]:
        return [d.job_id for d in self.definitions()]
