from typing import Iterable, List, Optional

from vaybooks.bms.domain.finance.accounting.repository import AccountRepository
from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.party_location import require_location_ids
from vaybooks.bms.domain.parties.workers.entities import (
    SOURCE_CUSTOMIZATION,
    Worker,
    normalize_activity_refs,
)
from vaybooks.bms.domain.parties.workers.repository import WorkerRepository
from vaybooks.bms.domain.parties.workers.services import WorkerDomainService


class WorkerAppService:
    def __init__(
        self,
        worker_repo: WorkerRepository,
        account_repo: AccountRepository,
        user_service=None,
    ):
        self._repo = worker_repo
        self._accounting_domain = AccountingDomainService(account_repo, None)
        self._users = user_service

    def list_workers(
        self,
        active_only: bool = True,
        *,
        location_filter: dict | None = None,
    ) -> List[Worker]:
        return self._repo.list_all(
            active_only=active_only, location_filter=location_filter
        )

    def list_workers_by_activity(
        self,
        activity_id: str,
        source: str = SOURCE_CUSTOMIZATION,
        active_only: bool = True,
    ) -> List[Worker]:
        return self._repo.list_by_activity(
            activity_id, source=source, active_only=active_only
        )

    def get_worker(self, worker_id: str) -> Optional[Worker]:
        return self._repo.find_by_id(worker_id)

    def list_commission_enabled_workers(
        self,
        active_only: bool = True,
        *,
        location_filter: dict | None = None,
    ) -> List[Worker]:
        if hasattr(self._repo, "list_commission_enabled"):
            return self._repo.list_commission_enabled(
                active_only=active_only, location_filter=location_filter
            )
        return [
            w
            for w in self.list_workers(
                active_only=active_only, location_filter=location_filter
            )
            if getattr(w, "commission_enabled", False)
        ]

    def create_worker(
        self,
        worker_name: str,
        activity_refs: Iterable,
        default_hourly_rate: Optional[float] = None,
        *,
        create_login: bool = False,
        username: str = "",
        password: str = "",
        role_ids: Optional[List[str]] = None,
        location_ids: Optional[List[str]] = None,
        commission_enabled: bool = False,
        commission_profile=None,
    ) -> Worker:
        name = (worker_name or "").strip()
        if not name:
            raise ValidationError("Employee name is required")
        party_location_ids = require_location_ids(location_ids)

        linked_user_id = ""
        if create_login:
            linked_user_id = self._create_login_user(
                display_name=name,
                username=username,
                password=password,
                role_ids=role_ids,
                location_ids=party_location_ids,
            )

        worker = Worker(
            worker_name=name,
            activity_refs=normalize_activity_refs(activity_refs),
            default_hourly_rate=float(default_hourly_rate or 0.0),
            linked_user_id=linked_user_id,
            location_ids=party_location_ids,
            commission_enabled=bool(commission_enabled),
            commission_profile=commission_profile,
        )
        saved = self._repo.save(worker)
        account_name = WorkerDomainService.build_salary_account_name(saved)
        self._accounting_domain.sync_worker_salary_account(saved.id, account_name)
        return saved

    def update_worker(
        self,
        worker_id: str,
        worker_name: str,
        activity_refs: Iterable,
        is_active: bool = True,
        default_hourly_rate: Optional[float] = None,
        *,
        create_login: bool = False,
        username: str = "",
        password: str = "",
        role_ids: Optional[List[str]] = None,
        location_ids: Optional[List[str]] = None,
        commission_enabled: bool | None = None,
        commission_profile=None,
    ) -> Worker:
        worker = self._repo.find_by_id(worker_id)
        if not worker:
            raise ValueError("Employee not found")
        name = (worker_name or "").strip()
        if not name:
            raise ValidationError("Employee name is required")
        party_location_ids = require_location_ids(
            location_ids if location_ids is not None else worker.location_ids
        )
        rate = (
            worker.default_hourly_rate
            if default_hourly_rate is None
            else float(default_hourly_rate or 0.0)
        )

        linked_user_id = worker.linked_user_id
        if create_login:
            if worker.linked_user_id:
                raise ValidationError("This employee already has a system login")
            linked_user_id = self._create_login_user(
                display_name=name,
                username=username,
                password=password,
                role_ids=role_ids,
                location_ids=party_location_ids,
            )

        worker.update(
            worker_name=name,
            activity_refs=normalize_activity_refs(activity_refs),
            is_active=is_active,
            default_hourly_rate=rate,
            linked_user_id=linked_user_id,
            location_ids=party_location_ids,
            commission_enabled=commission_enabled,
            commission_profile=commission_profile,
        )
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

    def _create_login_user(
        self,
        *,
        display_name: str,
        username: str,
        password: str,
        role_ids: Optional[List[str]],
        location_ids: Optional[List[str]],
    ) -> str:
        if self._users is None:
            raise ValidationError("User service is not configured")
        user = self._users.create_user(
            username=username,
            display_name=display_name,
            password=password,
            role_ids=list(role_ids or []),
            location_ids=list(location_ids or []),
        )
        return user.id
