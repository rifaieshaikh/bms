from datetime import datetime

import pytest

from vaybooks.bms.application.parties.workers.service import WorkerAppService
from vaybooks.bms.domain.shared.enums import AccountType
from vaybooks.bms.domain.parties.workers.entities import Worker
from tests.conftest import FakeAccountRepository


class _FakeWorkerRepo:
    def __init__(self):
        self.store: dict[str, Worker] = {}

    def save(self, worker: Worker) -> Worker:
        self.store[worker.id] = worker
        return worker

    def find_by_id(self, worker_id: str):
        return self.store.get(worker_id)

    def list_all(self, active_only: bool = True):
        workers = list(self.store.values())
        return [w for w in workers if w.is_active] if active_only else workers

    def list_by_activity(self, activity_id: str, active_only: bool = True):
        if not activity_id:
            return []
        workers = [
            w for w in self.store.values() if activity_id in (w.activity_ids or [])
        ]
        return [w for w in workers if w.is_active] if active_only else workers


def test_list_workers_by_activity_filters_active():
    repo = _FakeWorkerRepo()
    svc = WorkerAppService(repo, FakeAccountRepository())

    w1 = Worker(worker_name="Ravi", activity_ids=["a1"], is_active=True)
    w2 = Worker(worker_name="Ravi", activity_ids=["a1"], is_active=False)
    w3 = Worker(worker_name="Meena", activity_ids=["a2"], is_active=True)
    # Make deterministic ids in case of debug output
    w1.id, w2.id, w3.id = "w1", "w2", "w3"
    w1.created_at = w2.created_at = w3.created_at = datetime.utcnow()
    repo.save(w1)
    repo.save(w2)
    repo.save(w3)

    assert [w.id for w in svc.list_workers_by_activity("a1")] == ["w1"]
    assert {w.id for w in svc.list_workers_by_activity("a1", active_only=False)} == {
        "w1",
        "w2",
    }


def test_create_worker_requires_name():
    repo = _FakeWorkerRepo()
    svc = WorkerAppService(repo, FakeAccountRepository())
    with pytest.raises(Exception):
        svc.create_worker("  ", ["a1"])


def test_create_worker_creates_salary_account():
    worker_repo = _FakeWorkerRepo()
    account_repo = FakeAccountRepository()
    svc = WorkerAppService(worker_repo, account_repo)

    worker = svc.create_worker("Ravi", ["a1"])

    account = account_repo.find_worker_account(worker.id)
    assert account is not None
    assert account.account_name == "Salary - Ravi"
    assert account.is_salary_account is True
    assert account.account_type == AccountType.LIABILITY
    assert account.linked_worker_id == worker.id


def test_update_worker_renames_salary_account():
    worker_repo = _FakeWorkerRepo()
    account_repo = FakeAccountRepository()
    svc = WorkerAppService(worker_repo, account_repo)

    worker = svc.create_worker("Ravi", ["a1"])
    svc.update_worker(worker.id, "Ravi Kumar", ["a1"], True)

    account = account_repo.find_worker_account(worker.id)
    assert account.account_name == "Salary - Ravi Kumar"

