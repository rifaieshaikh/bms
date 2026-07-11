"""MongoDB integration tests for ProductCategory repository."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from vaybooks.bms.domain.inventory.entities import ProductCategory
from vaybooks.bms.infrastructure.db.connection import get_database_from_uri
from vaybooks.bms.infrastructure.repositories.mongo_inventory_repository import (
    MongoProductCategoryRepository,
)

BMS_ROOT = Path(__file__).resolve().parents[2]


def _read_secrets() -> dict[str, str]:
    secrets_path = BMS_ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}
    try:
        import tomllib

        return {k: str(v) for k, v in tomllib.loads(secrets_path.read_text(encoding="utf-8")).items()}
    except Exception:
        return {}


def _mongo_db():
    secrets = _read_secrets()
    uri = os.environ.get("MONGODB_URI") or secrets.get("MONGODB_URI")
    if not uri:
        pytest.skip("MONGODB_URI not set")
    db_name = secrets.get("MONGODB_DATABASE") or os.environ.get(
        "MONGODB_DATABASE", "zahcci_customization"
    )
    return get_database_from_uri(uri, db_name)


@pytest.fixture
def category_repo():
    db = _mongo_db()
    db.product_categories.delete_many({"name": {"$regex": "^E2E Cat "}})
    repo = MongoProductCategoryRepository(db)
    yield repo
    db.product_categories.delete_many({"name": {"$regex": "^E2E Cat "}})


def _unique_name() -> str:
    return f"E2E Cat {uuid.uuid4().hex[:8]}"


def test_save_and_find_by_id(category_repo):
    name = _unique_name()
    saved = category_repo.save(ProductCategory(name=name, description="desc"))
    loaded = category_repo.find_by_id(saved.id)
    assert loaded is not None
    assert loaded.name == name
    assert loaded.description == "desc"


def test_find_by_parent_and_name_root(category_repo):
    name = _unique_name()
    saved = category_repo.save(ProductCategory(name=name))
    found = category_repo.find_by_parent_and_name(None, name)
    assert found is not None
    assert found.id == saved.id


def test_find_by_parent_and_name_child(category_repo):
    root_name = _unique_name()
    child_name = _unique_name()
    root = category_repo.save(ProductCategory(name=root_name))
    child = category_repo.save(
        ProductCategory(name=child_name, parent_id=root.id)
    )
    found = category_repo.find_by_parent_and_name(root.id, child_name)
    assert found is not None
    assert found.id == child.id


def test_list_children_root_vs_child(category_repo):
    root_name = _unique_name()
    child_name = _unique_name()
    root = category_repo.save(ProductCategory(name=root_name))
    category_repo.save(ProductCategory(name=child_name, parent_id=root.id))
    roots = category_repo.list_children(None)
    assert any(c.id == root.id for c in roots)
    direct = category_repo.list_children(root.id)
    assert len(direct) == 1
    assert direct[0].name == child_name


def test_list_all_active_only(category_repo):
    active_name = _unique_name()
    inactive_name = _unique_name()
    category_repo.save(ProductCategory(name=active_name, is_active=True))
    category_repo.save(ProductCategory(name=inactive_name, is_active=False))
    active = category_repo.list_all(active_only=True)
    all_cats = category_repo.list_all(active_only=False)
    active_names = {c.name for c in active}
    all_names = {c.name for c in all_cats}
    assert active_name in active_names
    assert inactive_name not in active_names
    assert inactive_name in all_names


def test_delete_removes_document(category_repo):
    name = _unique_name()
    saved = category_repo.save(ProductCategory(name=name))
    category_repo.delete(saved.id)
    assert category_repo.find_by_id(saved.id) is None
