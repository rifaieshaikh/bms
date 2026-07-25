from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.identity.entities import Role, User
from vaybooks.bms.domain.shared.date_utils import utc_now


class MongoUserRepository:
    def __init__(self, db: Database):
        self._collection = db.users

    def _to_doc(self, user: User) -> dict:
        return {
            "_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "password_hash": user.password_hash,
            "role_ids": list(user.role_ids or []),
            "active": user.active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    def _from_doc(self, doc: dict) -> User:
        return User(
            id=doc["_id"],
            username=doc.get("username", ""),
            display_name=doc.get("display_name", ""),
            password_hash=doc.get("password_hash", ""),
            role_ids=list(doc.get("role_ids") or []),
            active=bool(doc.get("active", True)),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, user: User) -> User:
        user.updated_at = utc_now()
        self._collection.replace_one({"_id": user.id}, self._to_doc(user), upsert=True)
        return user

    def find_by_id(self, user_id: str) -> Optional[User]:
        doc = self._collection.find_one({"_id": user_id})
        return self._from_doc(doc) if doc else None

    def find_by_username(self, username: str) -> Optional[User]:
        doc = self._collection.find_one({"username": (username or "").strip()})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[User]:
        return [self._from_doc(d) for d in self._collection.find().sort("username", 1)]

    def delete(self, user_id: str) -> None:
        self._collection.delete_one({"_id": user_id})


class MongoRoleRepository:
    def __init__(self, db: Database):
        self._collection = db.roles

    def _to_doc(self, role: Role) -> dict:
        return {
            "_id": role.id,
            "name": role.name,
            "permission_keys": list(role.permission_keys or []),
            "description": role.description,
            "is_system": bool(role.is_system),
            "created_at": role.created_at,
            "updated_at": role.updated_at,
        }

    def _from_doc(self, doc: dict) -> Role:
        return Role(
            id=doc["_id"],
            name=doc.get("name", ""),
            permission_keys=list(doc.get("permission_keys") or []),
            description=doc.get("description", ""),
            is_system=bool(doc.get("is_system", False)),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, role: Role) -> Role:
        role.updated_at = utc_now()
        self._collection.replace_one({"_id": role.id}, self._to_doc(role), upsert=True)
        return role

    def find_by_id(self, role_id: str) -> Optional[Role]:
        doc = self._collection.find_one({"_id": role_id})
        return self._from_doc(doc) if doc else None

    def find_by_name(self, name: str) -> Optional[Role]:
        doc = self._collection.find_one({"name": (name or "").strip()})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[Role]:
        return [self._from_doc(d) for d in self._collection.find().sort("name", 1)]

    def delete(self, role_id: str) -> None:
        self._collection.delete_one({"_id": role_id})
