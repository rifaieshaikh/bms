from typing import List, Optional

from vaybooks.bms.domain.accounting.repository import AccountRepository
from vaybooks.bms.domain.accounting.services import AccountingDomainService
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.workers.entities import Worker
from vaybooks.bms.domain.workers.repository import WorkerRepository
from vaybooks.bms.domain.workers.services import WorkerDomainService


class WorkerAppService:
    def __init__(
        self,
        worker_repo: WorkerRepository,
        account_repo: AccountRepository,
    ):
        self._repo = worker_repo
        self._accounting_domain = AccountingDomainService(account_repo, None)

    def list_workers(self, active_only: bool = True) -> List[Worker]:
        return self._repo.list_all(active_only=active_only)

    def list_workers_by_activity(self, activity_id: str, active_only: bool = True) -> List[Worker]:
        return self._repo.list_by_activity(activity_id, active_only=active_only)

    def get_worker(self, worker_id: str) -> Optional[Worker]:
        return self._repo.find_by_id(worker_id)

    def create_worker(self, worker_name: str, activity_ids: List[str]) -> Worker:
        name = (worker_name or "").strip()
        if not name:
            raise ValidationError("Employee name is required")
        worker = Worker(worker_name=name, activity_ids=list(activity_ids or []))
        saved = self._repo.save(worker)
        account_name = WorkerDomainService.build_salary_account_name(saved)
        self._accounting_domain.sync_worker_salary_account(saved.id, account_name)
        return saved

    def update_worker(
        self,
        worker_id: str,
        worker_name: str,
        activity_ids: List[str],
        is_active: bool = True,
    ) -> Worker:
        worker = self._repo.find_by_id(worker_id)
        if not worker:
            raise ValueError("Employee not found")
        name = (worker_name or "").strip()
        if not name:
            raise ValidationError("Employee name is required")
        worker.update(worker_name=name, activity_ids=list(activity_ids or []), is_active=is_active)
        saved = self._repo.save(worker)
        self._accounting_domain.sync_worker_salary_account(
            saved.id,
            WorkerDomainService.build_salary_account_name(saved),
        )
        return saved

    def deactivate_worker(self, worker_id: str) -> Worker:
        worker = self._repo.find_by_id(worker_id)
        if not worker:
            raise ValueError("Employee not found")
        worker.is_active = False
        return self._repo.save(worker)
