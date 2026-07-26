from datetime import datetime

import pytest

from vaybooks.bms.application.parties.workers.service import WorkerAppService
from vaybooks.bms.domain.shared.enums import AccountType
from vaybooks.bms.domain.parties.workers.entities import (
    SOURCE_CUSTOMIZATION,
    SOURCE_STORE,
    Worker,
    WorkerActivityRef,
    normalize_activity_refs,
)
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

    def list_by_activity(
        self,
        activity_id: str,
        source: str = SOURCE_CUSTOMIZATION,
        active_only: bool = True,
    ):
        if not activity_id:
            return []
        workers = [
            w for w in self.store.values() if w.has_activity(activity_id, source)
        ]
        return [w for w in workers if w.is_active] if active_only else workers


def test_list_workers_by_activity_filters_active():
    repo = _FakeWorkerRepo()
    svc = WorkerAppService(repo, FakeAccountRepository())

    w1 = Worker(worker_name="Ravi", activity_refs=["a1"], is_active=True)
    w2 = Worker(worker_name="Ravi", activity_refs=["a1"], is_active=False)
    w3 = Worker(worker_name="Meena", activity_refs=["a2"], is_active=True)
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


def test_list_workers_by_activity_respects_source():
    repo = _FakeWorkerRepo()
    svc = WorkerAppService(repo, FakeAccountRepository())

    store_worker = Worker(
        worker_name="Asha",
        activity_refs=[WorkerActivityRef(activity_id="a1", source=SOURCE_STORE)],
    )
    boutique_worker = Worker(worker_name="Ravi", activity_refs=["a1"])
    store_worker.id, boutique_worker.id = "ws", "wb"
    repo.save(store_worker)
    repo.save(boutique_worker)

    assert [
        w.id for w in svc.list_workers_by_activity("a1", source=SOURCE_STORE)
    ] == ["ws"]
    assert [w.id for w in svc.list_workers_by_activity("a1")] == ["wb"]


def test_normalize_activity_refs_handles_legacy_shapes():
    refs = normalize_activity_refs(
        [
            "a1",  # legacy plain id → customization
            {"activity_id": "a2", "source": "store"},
            WorkerActivityRef(activity_id="a3", source="project"),
            {"activity_id": "a1", "source": "customization"},  # duplicate
            {"activity_id": "", "source": "store"},  # blank id dropped
            {"activity_id": "a4", "source": "bogus"},  # unknown source → customization
        ]
    )
    assert refs == [
        WorkerActivityRef(activity_id="a1", source=SOURCE_CUSTOMIZATION),
        WorkerActivityRef(activity_id="a2", source=SOURCE_STORE),
        WorkerActivityRef(activity_id="a3", source="project"),
        WorkerActivityRef(activity_id="a4", source=SOURCE_CUSTOMIZATION),
    ]


def test_worker_legacy_activity_ids_property():
    worker = Worker(
        worker_name="Ravi",
        activity_refs=[
            WorkerActivityRef(activity_id="a1", source=SOURCE_STORE),
            WorkerActivityRef(activity_id="a2", source=SOURCE_CUSTOMIZATION),
        ],
    )
    assert worker.activity_ids == ["a1", "a2"]
    assert worker.activity_ids_for_source(SOURCE_STORE) == ["a1"]
    assert worker.activity_ids_for_source(SOURCE_CUSTOMIZATION) == ["a2"]


def test_mongo_worker_doc_roundtrip_and_legacy_fallback():
    from types import SimpleNamespace

    from vaybooks.bms.infrastructure.repositories.parties.mongo_worker_repository import (
        MongoWorkerRepository,
    )

    repo = MongoWorkerRepository(SimpleNamespace(workers=None))

    worker = Worker(
        worker_name="Ravi",
        activity_refs=[
            WorkerActivityRef(activity_id="a1", source=SOURCE_STORE),
            WorkerActivityRef(activity_id="a2", source=SOURCE_CUSTOMIZATION),
        ],
    )
    doc = repo._to_doc(worker)
    assert doc["activity_refs"] == [
        {"activity_id": "a1", "source": "store"},
        {"activity_id": "a2", "source": "customization"},
    ]
    # Legacy flat list stays in sync for old indexes/queries.
    assert doc["activity_ids"] == ["a1", "a2"]
    restored = repo._from_doc(doc)
    assert restored.activity_refs == worker.activity_refs

    # Pre-migration doc: only activity_ids present → customization refs.
    legacy_doc = {
        "_id": "w1",
        "worker_name": "Meena",
        "activity_ids": ["a9"],
        "is_active": True,
    }
    legacy = repo._from_doc(legacy_doc)
    assert legacy.activity_refs == [
        WorkerActivityRef(activity_id="a9", source=SOURCE_CUSTOMIZATION)
    ]


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


class _FakeUsers:
    def __init__(self):
        self.created = []

    def create_user(self, **kwargs):
        from types import SimpleNamespace
        from uuid import uuid4

        user = SimpleNamespace(id=uuid4().hex, **kwargs)
        self.created.append(user)
        return user


def test_create_worker_with_login_links_user():
    worker_repo = _FakeWorkerRepo()
    users = _FakeUsers()
    svc = WorkerAppService(worker_repo, FakeAccountRepository(), user_service=users)

    worker = svc.create_worker(
        "Priya",
        ["a1"],
        create_login=True,
        username="priya",
        password="secret1",
        role_ids=["role-sales-rep"],
    )

    assert worker.linked_user_id
    assert users.created[0].username == "priya"
    assert users.created[0].display_name == "Priya"
    assert users.created[0].role_ids == ["role-sales-rep"]


def test_create_worker_with_login_requires_user_service():
    svc = WorkerAppService(_FakeWorkerRepo(), FakeAccountRepository())
    with pytest.raises(Exception, match="User service is not configured"):
        svc.create_worker(
            "Priya",
            ["a1"],
            create_login=True,
            username="priya",
            password="secret1",
        )

